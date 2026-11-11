#!/usr/bin/env python3
"""VERICON Shopify read-only server-to-server connector (owned store pilot).

Requires a Shopify Dev Dashboard app installed on the SAME organization store.
Uses client_credentials (24h token), with only the scopes needed for stock reads.
No Shopify writes, no web listener, no token/secret in logs.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
PRIVATE = ROOT / "private"
CONFIG_FILE = PRIVATE / "shopify_setup.json"
STORE = "hudys3-p0.myshopify.com"
API_VERSION = "2026-10"
PILOT_ORDER_QUERY = '''query { orders(first: 2, query: "name:#1001") {
  nodes {
    id name test displayFinancialStatus
    refunds {
      id order { id } totalRefundedSet { shopMoney { amount currencyCode } }
      transactions(first: 20) { pageInfo { hasNextPage } nodes {
        id kind status test amountSet { shopMoney { amount currencyCode } }
      } }
    }
    transactions(first: 10) { id kind status test amountSet { shopMoney { amount currencyCode } } }
    subtotalPriceSet { shopMoney { amount currencyCode } }
    totalTaxSet { shopMoney { amount currencyCode } }
    totalPriceSet { shopMoney { amount currencyCode } }
    lineItems(first: 5) { nodes {
      sku quantity
      originalUnitPriceSet { shopMoney { amount currencyCode } }
      discountedTotalSet { shopMoney { amount currencyCode } }
    } }
    shippingLines(first: 5) { nodes {
      title discountedPriceSet { shopMoney { amount currencyCode } }
    } }
  }
} }'''
BATCH_ORDER_QUERY = PILOT_ORDER_QUERY.replace(
    'orders(first: 2, query: "name:#1001") {',
    'orders(first: 5, sortKey: CREATED_AT, reverse: true) { pageInfo { hasNextPage }')
REQUIRED_SCOPES = frozenset(("read_products", "read_inventory", "read_locations"))
SKU_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")

STOCK_QUERY = """
query VericonSkuInventory($search: String!) {
  shop { currencyCode }
  productVariants(first: 10, query: $search) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id sku price
      product { status }
      inventoryItem {
        id tracked
        inventoryLevels(first: 20) {
          pageInfo { hasNextPage endCursor }
          nodes {
            location { id name }
            updatedAt
            quantities(names: ["on_hand", "available", "committed"]) { name quantity }
          }
        }
      }
    }
  }
}
"""


@dataclass(frozen=True)
class Config:
    client_id: str
    client_secret: str
    store: str = STORE


def _ensure_private() -> None:
    PRIVATE.mkdir(parents=True, mode=0o700, exist_ok=True)
    if stat.S_IMODE(PRIVATE.stat().st_mode) != 0o700 or PRIVATE.is_symlink():
        raise PermissionError("private/ must be an ordinary directory with mode 0700")


def _atomic_save(path: Path, data: dict) -> None:
    _ensure_private()
    fd, name = tempfile.mkstemp(prefix=".shopify-", dir=PRIVATE)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def save_setup(client_id: str, client_secret: str) -> None:
    if not client_id or not client_secret:
        raise ValueError("Missing Shopify credentials")
    if CONFIG_FILE.exists():
        raise FileExistsError("Shopify credentials already exist; will not overwrite them")
    _atomic_save(CONFIG_FILE, {"client_id": client_id,
                               "client_secret": client_secret,
                               "store": STORE})


def load_setup() -> Config:
    _ensure_private()
    if CONFIG_FILE.is_symlink() or not CONFIG_FILE.is_file():
        raise ValueError("Shopify private setup is not configured")
    if stat.S_IMODE(CONFIG_FILE.stat().st_mode) != 0o600:
        raise PermissionError("Shopify credential file must be mode 0600")
    raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    if raw.get("store") != STORE:
        raise ValueError("Shopify store does not match approved pilot store")
    if not raw.get("client_id") or not raw.get("client_secret"):
        raise ValueError("Shopify credentials are incomplete")
    return Config(client_id=raw["client_id"], client_secret=raw["client_secret"])


def _tenant_setup_path(user_id: str, store: str) -> Path:
    """Isolated future Shopify tenant credentials; never fall back to pilot."""
    import uuid
    user_id = str(uuid.UUID(user_id))
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,61}\.myshopify\.com", store):
        raise ValueError("Invalid Shopify canonical store domain")
    _ensure_private()
    folder = PRIVATE / "shopify_tenants"
    folder.mkdir(mode=0o700, exist_ok=True)
    if folder.is_symlink() or stat.S_IMODE(folder.stat().st_mode) != 0o700:
        raise PermissionError("Shopify tenant directory unsafe")
    return folder / (user_id + "_" + store + ".json")


def save_tenant_setup(user_id: str, store: str, client_id: str, client_secret: str) -> None:
    if not client_id or not client_secret:
        raise ValueError("Missing Shopify tenant credentials")
    path = _tenant_setup_path(user_id, store)
    if path.exists() or path.is_symlink():
        raise FileExistsError("Shopify tenant credentials already exist")
    _atomic_save(path, {"user_id": str(__import__("uuid").UUID(user_id)),
                        "store": store, "client_id": client_id, "client_secret": client_secret})


def load_tenant_setup(user_id: str, store: str) -> Config:
    path = _tenant_setup_path(user_id, store)
    if not path.is_file() or path.is_symlink() or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ValueError("Shopify tenant credentials unavailable")
    record = json.loads(path.read_text())
    if record.get("user_id") != str(__import__("uuid").UUID(user_id)) or record.get("store") != store:
        raise ValueError("Shopify tenant identity mismatch")
    if not record.get("client_id") or not record.get("client_secret"):
        raise ValueError("Shopify tenant credentials incomplete")
    return Config(client_id=record["client_id"], client_secret=record["client_secret"], store=store)


def verify_tenant_store(user_id: str, store: str) -> dict:
    """Read-only independent tenant connection check; never fall back to pilot."""
    config = load_tenant_setup(user_id, store)
    if config.store != store:
        raise ValueError("Tenant store mismatch")
    response = requests.post(
        f"https://{store}/admin/oauth/access_token",
        data={"grant_type": "client_credentials", "client_id": config.client_id,
              "client_secret": config.client_secret},
        headers={"Accept": "application/json"}, timeout=20)
    if response.status_code != 200:
        raise ValueError("Tenant Shopify token refused")
    body = response.json()
    scopes = frozenset(x.strip() for x in str(body.get("scope", "")).split(","))
    if not REQUIRED_SCOPES.issubset(scopes) or not body.get("access_token"):
        raise ValueError("Tenant Shopify read permissions missing")
    identity = requests.post(
        f"https://{store}/admin/api/{API_VERSION}/graphql.json",
        json={"query": "query { shop { myshopifyDomain } }"},
        headers={"X-Shopify-Access-Token": str(body["access_token"]),
                 "Content-Type": "application/json"}, timeout=20)
    if identity.status_code != 200:
        raise ValueError("Tenant Shopify identity read refused")
    result = identity.json()
    if result.get("errors") or ((result.get("data") or {}).get("shop") or {}).get("myshopifyDomain") != store:
        raise ValueError("Tenant Shopify identity mismatch")
    return {"store": store, "app_access_verified": True, "user_ownership_verified": False}


def read_tenant_owner_proof(user_id: str, store: str) -> str | None:
    """Read the store-owned challenge without writing Shopify data."""
    config = load_tenant_setup(user_id, store)
    token_response = requests.post(f"https://{store}/admin/oauth/access_token",
        data={"grant_type":"client_credentials","client_id":config.client_id,"client_secret":config.client_secret},
        timeout=20)
    if token_response.status_code != 200:
        raise ValueError("Tenant token unavailable")
    token_data = token_response.json()
    scopes = set(str(token_data.get("scope", "")).split(","))
    if not REQUIRED_SCOPES.issubset(scopes) or not token_data.get("access_token"):
        raise ValueError("Tenant token lacks permissions")
    response = requests.post(f"https://{store}/admin/api/{API_VERSION}/graphql.json",
        json={"query":'query { shop { myshopifyDomain metafield(namespace:"vericon",key:"owner_proof") { value } } }'},
        headers={"X-Shopify-Access-Token":token_data["access_token"]}, timeout=20)
    if response.status_code != 200:
        raise ValueError("Tenant proof read unavailable")
    data = response.json()
    if data.get("errors") or ((data.get("data") or {}).get("shop") or {}).get("myshopifyDomain") != store:
        raise ValueError("Tenant proof shop mismatch")
    return ((((data.get("data") or {}).get("shop") or {}).get("metafield") or {}).get("value"))


def get_access_token(config: Config) -> str:
    if config.store != STORE:
        raise ValueError("Shopify store is not the approved store")
    r = requests.post(
        f"https://{STORE}/admin/oauth/access_token",
        data={"grant_type": "client_credentials",
              "client_id": config.client_id,
              "client_secret": config.client_secret},
        headers={"Accept": "application/json"},
        timeout=20,
    )
    if r.status_code != 200:
        raise ValueError(f"Shopify client credentials refused (HTTP {r.status_code})")
    body = r.json()
    scopes = frozenset(s.strip() for s in str(body.get("scope", "")).split(","))
    if not REQUIRED_SCOPES.issubset(scopes):
        raise ValueError("Shopify app lacks the required read-only scopes")
    if not body.get("access_token"):
        raise ValueError("Shopify response missing access token")
    return str(body["access_token"])


def verify_installed_store(config: Config) -> dict:
    """Verify the app token targets the approved shop; not customer ownership proof."""
    token = get_access_token(config)
    response = requests.post(
        f"https://{STORE}/admin/api/{API_VERSION}/graphql.json",
        json={"query": "query { shop { myshopifyDomain } }"},
        headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"},
        timeout=25,
    )
    if response.status_code != 200:
        raise ValueError(f"Shopify store verification refused (HTTP {response.status_code})")
    body = response.json()
    if body.get("errors") or (body.get("data") or {}).get("shop", {}).get("myshopifyDomain") != STORE:
        raise ValueError("Shopify store identity mismatch or unverified")
    return {"store": STORE, "app_access_verified": True, "user_ownership_verified": False}


def read_owner_proof(config: Config) -> str | None:
    """Read only the shop-level VERICON challenge, never mutate the shop."""
    token = get_access_token(config)
    response = requests.post(f"https://{STORE}/admin/api/{API_VERSION}/graphql.json",
        json={"query": 'query { shop { myshopifyDomain metafield(namespace:"vericon",key:"owner_proof") { value } } }'},
        headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"}, timeout=20)
    if response.status_code != 200:
        raise ValueError("Shopify read failed")
    data = response.json()
    if data.get("errors"):
        raise ValueError("Shopify GraphQL error")
    shop = (data.get("data") or {}).get("shop") or {}
    if shop.get("myshopifyDomain") != STORE:
        raise ValueError("Shopify identity mismatch")
    return (shop.get("metafield") or {}).get("value")


def read_stock(config: Config, sku: str) -> dict:
    if not SKU_PATTERN.fullmatch(sku):
        raise ValueError("Invalid SKU; refusing unsafe inventory query")
    token = get_access_token(config)
    response = requests.post(
        f"https://{STORE}/admin/api/{API_VERSION}/graphql.json",
        json={"query": STOCK_QUERY, "variables": {"search": f"sku:{sku}"}},
        headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"},
        timeout=25,
    )
    if response.status_code != 200:
        raise ValueError(f"Shopify inventory query refused (HTTP {response.status_code})")
    body = response.json()
    if body.get("errors"):
        raise ValueError("Shopify returned GraphQL errors; inventory not verified")
    data = body.get("data") or {}
    currency = (data.get("shop") or {}).get("currencyCode")
    if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("Shopify default currency absent or invalid")
    conn = data.get("productVariants")
    if not isinstance(conn, dict):
        raise ValueError("Malformed Shopify response")
    if conn.get("pageInfo", {}).get("hasNextPage"):
        raise ValueError("Too many variant search results; refusing ambiguous match")
    matches = [row for row in (conn.get("nodes") or []) if row.get("sku") == sku]
    if len(matches) != 1:
        raise ValueError("Shopify SKU not found or matches multiple variants")
    inventory = matches[0].get("inventoryItem") or {}
    if inventory.get("tracked") is not True:
        raise ValueError("Shopify SKU inventory tracking disabled")
    levels = inventory.get("inventoryLevels") or {}
    if levels.get("pageInfo", {}).get("hasNextPage"):
        raise ValueError("More than 20 locations; pagination not yet supported")
    locations = []
    for node in (levels.get("nodes") or []):
        quantities = {e["name"]: e["quantity"] for e in (node.get("quantities") or [])}
        if not all(name in quantities for name in ("on_hand", "available", "committed")):
            raise ValueError("Missing Shopify inventory quantity states")
        if any(not isinstance(quantities[name], int) or isinstance(quantities[name], bool)
               for name in ("on_hand", "available", "committed")):
            raise ValueError("Invalid Shopify quantity type")
        location = node.get("location") or {}
        if not location.get("id"):
            raise ValueError("Shopify location missing")
        locations.append({"location_id": location["id"], "location_name": location.get("name"),
                          "updated_at": node.get("updatedAt"),
                          "on_hand": quantities["on_hand"],
                          "available": quantities["available"],
                          "committed": quantities["committed"]})
    if not locations:
        raise ValueError("Shopify item has no inventory location")
    return {"source": "shopify", "sku": sku, "tracked": True,
            "query_time_utc": datetime.now(timezone.utc).isoformat(),
            "locations": locations, "total_on_hand": sum(row["on_hand"] for row in locations),
            "catalog_price": matches[0].get("price"), "catalog_currency": currency,
            "product_status": (matches[0].get("product") or {}).get("status")}


def price_evidence(shop: dict, qbo_item: dict, qbo_currency: str | None) -> dict:
    """Record price context and fail closed. No FX rate or approved pricing policy."""
    result = {"shopify_catalog_price": shop.get("catalog_price"),
              "shopify_catalog_currency": shop.get("catalog_currency"),
              "quickbooks_unit_price": qbo_item.get("UnitPrice"),
              "quickbooks_home_currency": qbo_currency,
              "shopify_product_status": shop.get("product_status")}
    if qbo_currency is None:
        result["status"] = "BLOCKED_QBO_CURRENCY_UNKNOWN"
    elif not shop.get("catalog_currency") or not isinstance(shop.get("catalog_price"), str) or qbo_item.get("UnitPrice") is None:
        result["status"] = "BLOCKED_PRICE_FIELDS_MISSING"
    elif shop["catalog_currency"] != qbo_currency:
        result["status"] = "BLOCKED_PRICE_CURRENCY_MISMATCH"
    elif shop.get("product_status") != "ACTIVE":
        result["status"] = "BLOCKED_PRODUCT_NOT_ACTIVE"
    else:
        # Catalog list price and QBO default UnitPrice may follow different policies.
        result["status"] = "BLOCKED_PRICE_POLICY_UNVERIFIED"
    return result


def check_both(sku: str) -> dict:
    from qbo_oauth import load_saved_setup, read_inventory_item_by_sku, read_home_currency
    from inventory_compare import compare

    shop = read_stock(load_setup(), sku)
    qbo_result = read_inventory_item_by_sku(load_saved_setup(), sku)
    matches = [item for item in qbo_result["items"] if item.get("Sku") == sku]
    if len(matches) != 1:
        raise ValueError("QuickBooks SKU missing or ambiguous")
    if len(shop["locations"]) != 1:
        return {"status": "BLOCKED_MULTIPLE_LOCATIONS", "sku": sku,
                "location_count": len(shop["locations"])}
    # Sequential API reads are not an atomic snapshot. Block large gaps.
    try:
        shop_time = datetime.fromisoformat(shop["query_time_utc"].replace("Z", "+00:00"))
        qbo_time = datetime.fromisoformat(qbo_result["query_time_utc"].replace("Z", "+00:00"))
        if shop_time.utcoffset() is None or qbo_time.utcoffset() is None:
            raise ValueError("Timezone missing")
        read_gap_seconds = abs((qbo_time - shop_time).total_seconds())
    except (ValueError, TypeError, KeyError):
        return {"status": "BLOCKED_INVALID_SNAPSHOT_TIMES", "sku": sku}
    if read_gap_seconds > 30:
        return {"status": "BLOCKED_SNAPSHOT_TIME_GAP", "sku": sku,
                "read_gap_seconds": round(read_gap_seconds, 3)}
    result = compare({"shopify": {"sku": sku, "onHand": shop["locations"][0]["on_hand"],
                                   "available": shop["locations"][0]["available"]},
                      "quickbooks": matches[0], "testMode": True})
    result["quickbooks_query_time_utc"] = qbo_result.get("query_time_utc")
    result["shopify_query_time_utc"] = shop.get("query_time_utc")
    result["shopify_location_id"] = shop["locations"][0]["location_id"]
    result["read_gap_seconds"] = round(read_gap_seconds, 3)
    try:
        home_currency = read_home_currency(load_saved_setup())
    except (ValueError, PermissionError, requests.RequestException):
        home_currency = None
    result["catalog_price_check"] = price_evidence(shop, matches[0], home_currency)
    result["data_origin"] = "live_shopify_and_quickbooks_sandbox_api_queries"
    result["note"] = ("Controlled sandbox comparison only; snapshot times, location coverage, "
                      "and accounting stock meaning require review. Not a real customer loss.")
    return result


def check_many(skus: list[str]) -> dict:
    # Bounded, explicitly selected test SKUs only. Never discover or modify products.
    if not 2 <= len(skus) <= 5:
        raise ValueError("Batch must contain 2 to 5 explicitly selected SKUs")
    if any(not SKU_PATTERN.fullmatch(sku) for sku in skus):
        raise ValueError("Batch contains an invalid SKU")
    if len(set(skus)) != len(skus):
        raise ValueError("Batch contains duplicate SKUs")

    results = []
    for sku in skus:
        try:
            result = check_both(sku)
        except (ValueError, PermissionError, requests.RequestException):
            # A failed lookup is not an inventory discrepancy. Do not leak API internals.
            result = {"sku": sku, "status": "BLOCKED_ITEM_READ"}
        if result.get("sku") != sku:
            result = {"sku": sku, "status": "BLOCKED_SKU_RESULT_MISMATCH"}
        results.append(result)
    blocked = sum(item["status"].startswith("BLOCKED_") for item in results)
    return {"status": "TEST_BATCH_PARTIAL_BLOCKED" if blocked else "TEST_BATCH_COMPLETE",
            "requested": len(skus), "checked": len(skus) - blocked, "blocked": blocked,
            "results": results}


def read_shopify_test_orders() -> list[dict]:
    """Read at most five recent test orders; block an incomplete result window."""
    token = get_access_token(load_setup())
    response = requests.post(
        f"https://{STORE}/admin/api/{API_VERSION}/graphql.json",
        json={"query": BATCH_ORDER_QUERY},
        headers={"X-Shopify-Access-Token": token}, timeout=20)
    response.raise_for_status()
    body = response.json()
    if body.get("errors"):
        raise ValueError("Shopify order batch query denied")
    conn = (body.get("data") or {}).get("orders")
    if not isinstance(conn, dict) or not isinstance(conn.get("nodes"), list):
        raise ValueError("Shopify order batch incomplete")
    if (conn.get("pageInfo") or {}).get("hasNextPage") is not False:
        raise ValueError("Shopify order batch pagination not verified")
    nodes = conn["nodes"]
    if len(nodes) > 5 or any(not isinstance(o, dict) or o.get("test") is not True
                             for o in nodes):
        raise ValueError("Unverified or non-test Shopify orders")
    ids = [str(o.get("id") or "") for o in nodes]
    if any(not x.startswith("gid://shopify/Order/") for x in ids) or len(set(ids)) != len(ids):
        raise ValueError("Duplicate or invalid Shopify orders")
    return nodes


def read_shopify_test_order() -> dict:
    """Read only pilot order #1001, without customer information or writes."""
    token = get_access_token(load_setup())
    response = requests.post(
        f"https://{STORE}/admin/api/{API_VERSION}/graphql.json",
        json={"query": PILOT_ORDER_QUERY}, headers={"X-Shopify-Access-Token": token}, timeout=20)
    response.raise_for_status()
    body = response.json()
    if body.get("errors"):
        raise ValueError("Shopify order read denied")
    nodes = ((body.get("data") or {}).get("orders") or {}).get("nodes") or []
    if len(nodes) != 1 or nodes[0].get("name") != "#1001":
        raise ValueError("Pilot order missing or ambiguous")
    return nodes[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="VERICON Shopify read-only pilot")
    cmd = parser.add_subparsers(dest="cmd", required=True)
    cmd.add_parser("setup", help="Enter keys privately in an interactive terminal")
    cmd.add_parser("status", help="Check local config presence, without revealing keys")
    read = cmd.add_parser("stock", help="Read Shopify inventory by exact SKU")
    read.add_argument("--sku", default="VERICON-TEST-001")
    check = cmd.add_parser("check", help="One-shot Shopify + QBO controlled inventory comparison")
    check.add_argument("--sku", default="VERICON-TEST-001")
    batch = cmd.add_parser("check-many", help="One-shot read-only comparison of 2 to 5 explicitly selected test SKUs")
    batch.add_argument("--sku", action="append", required=True)
    args = parser.parse_args()

    if args.cmd == "setup":
        import sys
        if not sys.stdin.isatty():
            raise ValueError("Interactive terminal required for private credentials")
        print("Shopify Dev Dashboard app must already be installed on this owned trial store.")
        client_id = input("Shopify Client ID: ").strip()
        client_secret = getpass.getpass("Shopify Client Secret (hidden): ").strip()
        save_setup(client_id, client_secret)
        print("Shopify credentials saved privately. No token printed.")
        return

    if args.cmd == "status":
        try:
            load_setup()
            print(json.dumps({"configured": True, "shop": STORE}))
        except (ValueError, PermissionError):
            print(json.dumps({"configured": False, "shop": STORE}))
        return

    if args.cmd == "stock":
        print(json.dumps(read_stock(load_setup(), args.sku), ensure_ascii=False))
    elif args.cmd == "check-many":
        result = check_many(args.sku)
        print(json.dumps(result, ensure_ascii=False))
        if result["blocked"]:
            raise SystemExit(2)
    else:
        print(json.dumps(check_both(args.sku), ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, PermissionError, FileExistsError, requests.RequestException) as exc:
        raise SystemExit(f"BLOCKED: {exc}") from None
