"""Offline tests for VERICON Shopify own-store read-only connector."""

import json
import os

import pytest

import shopify_read as s


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body or {}
    def json(self):
        return self._body


@pytest.fixture()
def cred():
    return s.Config(client_id="fake-id", client_secret="fake-not-real")


@pytest.fixture()
def records():
    return {
        "data": {
            "shop": {"currencyCode": "TRY"},
            "productVariants": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": [{
                    "id": "gid://shopify/ProductVariant/1",
                    "sku": "VERICON-TEST-001",
                    "price": "100.00",
                    "product": {"status": "DRAFT"},
                    "inventoryItem": {
                        "id": "gid://shopify/InventoryItem/1",
                        "tracked": True,
                        "inventoryLevels": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [{
                                "location": {"id": "gid://shopify/Location/1", "name": "Test"},
                                "updatedAt": "2026-11-03T06:50:20Z",
                                "quantities": [
                                    {"name": "on_hand", "quantity": 10},
                                    {"name": "available", "quantity": 10},
                                    {"name": "committed", "quantity": 0},
                                ]
                            }]
                        }
                    }
                }]
            }
        }
    }


def install_fake_requests(monkeypatch, stock_response):
    seen = []

    def post(url, *, data=None, json=None, headers=None, timeout=None):
        seen.append({"url": url, "data": data, "json": json, "headers": headers, "timeout": timeout})
        if url.endswith("/oauth/access_token"):
            return FakeResponse(body={"access_token": "NON_REAL_TEST_TOKEN",
                                      "scope": "read_products,read_inventory,read_locations",
                                      "expires_in": 86399})
        assert url.endswith("/admin/api/2026-10/graphql.json")
        return FakeResponse(body=stock_response)

    monkeypatch.setattr(s.requests, "post", post)
    return seen


def test_get_token_only_approved_store_and_read_scopes(cred, monkeypatch):
    seen = install_fake_requests(monkeypatch, {"data": {}})
    assert s.get_access_token(cred) == "NON_REAL_TEST_TOKEN"
    assert seen[0]["url"] == "https://hudys3-p0.myshopify.com/admin/oauth/access_token"
    assert seen[0]["data"]["grant_type"] == "client_credentials"
    with pytest.raises(ValueError, match="approved store"):
        s.get_access_token(s.Config("id", "secret", "evil.myshopify.com"))


def test_installed_store_verification_is_not_user_ownership(cred, monkeypatch):
    seen = []
    def post(url, *, data=None, json=None, headers=None, timeout=None):
        seen.append(url)
        if url.endswith('/oauth/access_token'):
            return FakeResponse(body={"access_token":"FAKE", "scope":"read_products,read_inventory,read_locations"})
        return FakeResponse(body={"data":{"shop":{"myshopifyDomain":"hudys3-p0.myshopify.com"}}})
    monkeypatch.setattr(s.requests, "post", post)
    result = s.verify_installed_store(cred)
    assert result == {"store":s.STORE,"app_access_verified":True,"user_ownership_verified":False}
    assert len(seen) == 2
    def wrong(url, *, data=None, json=None, headers=None, timeout=None):
        if url.endswith('/oauth/access_token'):
            return FakeResponse(body={"access_token":"FAKE", "scope":"read_products,read_inventory,read_locations"})
        return FakeResponse(body={"data":{"shop":{"myshopifyDomain":"other.myshopify.com"}}})
    monkeypatch.setattr(s.requests, "post", wrong)
    with pytest.raises(ValueError, match="mismatch"):
        s.verify_installed_store(cred)


def test_missing_read_scope_blocks_access(cred, monkeypatch):
    monkeypatch.setattr(s.requests, "post",
        lambda *args, **kwargs: FakeResponse(body={"access_token": "token", "scope": "read_products"}))
    with pytest.raises(ValueError, match="scopes"):
        s.get_access_token(cred)


def test_exact_sku_stock_read_only(cred, monkeypatch, records):
    seen = install_fake_requests(monkeypatch, records)
    result = s.read_stock(cred, "VERICON-TEST-001")
    assert result["catalog_price"] == "100.00"
    assert result["catalog_currency"] == "TRY"
    assert result["product_status"] == "DRAFT"
    assert result["total_on_hand"] == 10
    assert result["locations"][0]["available"] == 10
    assert result["locations"][0]["committed"] == 0
    assert result["sku"] == "VERICON-TEST-001"
    assert seen[1]["json"]["variables"]["search"] == "sku:VERICON-TEST-001"
    assert "mutation" not in seen[1]["json"]["query"].lower()
    assert seen[1]["headers"]["X-Shopify-Access-Token"] == "NON_REAL_TEST_TOKEN"
    assert "NON_REAL_TEST_TOKEN" not in json.dumps(result)


def test_empty_or_wrong_sku_blocks(cred, monkeypatch, records):
    records["data"]["productVariants"]["nodes"][0]["sku"] = "OTHER"
    install_fake_requests(monkeypatch, records)
    with pytest.raises(ValueError, match="not found"):
        s.read_stock(cred, "VERICON-TEST-001")


def test_duplicate_sku_blocks(cred, monkeypatch, records):
    nodes = records["data"]["productVariants"]["nodes"]
    nodes.append(nodes[0].copy())
    install_fake_requests(monkeypatch, records)
    with pytest.raises(ValueError, match="multiple"):
        s.read_stock(cred, "VERICON-TEST-001")


def test_untracked_and_pagination_block(cred, monkeypatch, records):
    nodes = records["data"]["productVariants"]["nodes"]
    nodes[0]["inventoryItem"]["tracked"] = False
    install_fake_requests(monkeypatch, records)
    with pytest.raises(ValueError, match="disabled"):
        s.read_stock(cred, "VERICON-TEST-001")
    nodes[0]["inventoryItem"]["tracked"] = True
    nodes[0]["inventoryItem"]["inventoryLevels"]["pageInfo"]["hasNextPage"] = True
    with pytest.raises(ValueError, match="pagination"):
        s.read_stock(cred, "VERICON-TEST-001")


def test_sql_injection_equivalent_sku_rejected_before_token(cred, monkeypatch):
    def never(*args, **kwargs):
        raise AssertionError("Should not perform network calls")
    monkeypatch.setattr(s.requests, "post", never)
    with pytest.raises(ValueError, match="Invalid SKU"):
        s.read_stock(cred, "' OR 1=1")


def test_graphql_error_not_silently_accepted(cred, monkeypatch):
    install_fake_requests(monkeypatch, {"errors": [{"message": "Access denied"}]})
    with pytest.raises(ValueError, match="GraphQL errors"):
        s.read_stock(cred, "VERICON-TEST-001")


def test_private_config_permissions(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "PRIVATE", tmp_path / "private")
    monkeypatch.setattr(s, "CONFIG_FILE", tmp_path / "private" / "shopify_setup.json")
    s.save_setup("fake-id", "fake-secret")
    config = s.load_setup()
    assert config.store == s.STORE
    assert oct(s.CONFIG_FILE.stat().st_mode & 0o777) == "0o600"
    assert oct(s.PRIVATE.stat().st_mode & 0o777) == "0o700"
    with pytest.raises(FileExistsError):
        s.save_setup("again", "again")
    s.CONFIG_FILE.chmod(0o644)
    with pytest.raises(PermissionError, match="0600"):
        s.load_setup()


def test_controlled_comparison_one_location(cred, monkeypatch, records):
    install_fake_requests(monkeypatch, records)
    monkeypatch.setattr(s, "load_setup", lambda: cred)
    import qbo_oauth
    monkeypatch.setattr(qbo_oauth, "load_saved_setup", lambda: object())
    monkeypatch.setattr(qbo_oauth, "read_home_currency", lambda config: "USD")
    from datetime import datetime, timezone
    monkeypatch.setattr(qbo_oauth, "read_inventory_item_by_sku", lambda cfg, sku: {
        "query_time_utc": datetime.now(timezone.utc).isoformat(),
        "items": [{"Sku": "VERICON-TEST-001", "Type": "Inventory",
                   "TrackQtyOnHand": True, "QtyOnHand": 7, "UnitPrice": 100}]
    })
    res = s.check_both("VERICON-TEST-001")
    assert res["delta_shopify_minus_qbo"] == "3"
    assert res["status"] == "REVIEW_STOCK_BASIS_UNVERIFIED"
    assert res["read_gap_seconds"] <= 30
    assert res["catalog_price_check"]["status"] == "BLOCKED_PRICE_CURRENCY_MISMATCH"
    assert res["catalog_price_check"]["shopify_catalog_currency"] == "TRY"
    assert res["catalog_price_check"]["quickbooks_home_currency"] == "USD"
    assert res["shopify_quantity_basis"] == "available"
    assert res["shopify_available"] == "10"
    assert res["data_origin"] == "live_shopify_and_quickbooks_sandbox_api_queries"


def test_committed_stock_does_not_create_false_shortage():
    from inventory_compare import compare
    qbo = {"Sku": "VERICON-TEST-001", "Type": "Inventory", "TrackQtyOnHand": True, "QtyOnHand": 7}
    result = compare({"shopify": {"sku": "VERICON-TEST-001", "onHand": 12,
                                  "available": 7}, "quickbooks": qbo, "testMode": True})
    assert result["status"] == "TEST_MATCH"
    assert result["delta_shopify_minus_qbo"] == "0"
    assert result["shopify_on_hand"] == "12"
    assert result["shopify_available"] == "7"

def test_missing_available_blocks_comparison():
    from inventory_compare import compare
    qbo = {"Sku": "VERICON-TEST-001", "Type": "Inventory", "TrackQtyOnHand": True, "QtyOnHand": 7}
    with pytest.raises(ValueError, match="shopify.available"):
        compare({"shopify": {"sku": "VERICON-TEST-001", "onHand": 10},
                 "quickbooks": qbo, "testMode": True})


def test_stale_cross_api_read_is_blocked(cred, monkeypatch, records):
    from datetime import datetime, timezone
    install_fake_requests(monkeypatch, records)
    monkeypatch.setattr(s, "load_setup", lambda: cred)
    import qbo_oauth
    monkeypatch.setattr(qbo_oauth, "load_saved_setup", lambda: object())
    monkeypatch.setattr(qbo_oauth, "read_home_currency", lambda config: "USD")
    monkeypatch.setattr(qbo_oauth, "read_inventory_item_by_sku", lambda cfg, sku: {
        "query_time_utc": "2024-01-01T00:00:00+00:00",
        "items": [{"Sku": "VERICON-TEST-001", "Type": "Inventory",
                   "TrackQtyOnHand": True, "QtyOnHand": 7}]
    })
    res = s.check_both("VERICON-TEST-001")
    assert res["status"] == "BLOCKED_SNAPSHOT_TIME_GAP"
    assert "delta_shopify_minus_qbo" not in res


def test_batch_is_bounded_and_deduplicated_before_api(monkeypatch):
    def no_network(sku):
        raise AssertionError("Validation must happen before API calls")
    monkeypatch.setattr(s, "check_both", no_network)
    for values in (["VERICON-TEST-001"], ["VERICON-TEST-001"] * 2,
                   ["VERICON-TEST-001", "' OR 1=1"],
                   [f"TEST-{i:02d}" for i in range(6)]):
        with pytest.raises(ValueError):
            s.check_many(values)


def test_batch_pairs_by_sku_without_cross_match(monkeypatch):
    seen = []
    expected = {"SKU-1": "2", "SKU-2": "-4"}
    def controlled(sku):
        seen.append(sku)
        return {"sku": sku, "status": "TEST_DIFFERENCE",
                "delta_shopify_minus_qbo": expected[sku]}
    monkeypatch.setattr(s, "check_both", controlled)
    result = s.check_many(["SKU-2", "SKU-1"])
    assert seen == ["SKU-2", "SKU-1"]
    assert result["status"] == "TEST_BATCH_COMPLETE"
    assert result["checked"] == 2 and result["blocked"] == 0
    assert [r["delta_shopify_minus_qbo"] for r in result["results"]] == ["-4", "2"]


def test_batch_missing_source_is_blocked_not_false_difference(monkeypatch):
    def controlled(sku):
        if sku == "MISSING-SKU":
            raise ValueError("Shopify SKU not found or matches multiple variants")
        return {"sku": sku, "status": "TEST_MATCH", "delta_shopify_minus_qbo": "0"}
    monkeypatch.setattr(s, "check_both", controlled)
    result = s.check_many(["VERICON-TEST-001", "MISSING-SKU"])
    assert result["status"] == "TEST_BATCH_PARTIAL_BLOCKED"
    assert result["checked"] == 1 and result["blocked"] == 1
    assert result["results"][1] == {"sku": "MISSING-SKU", "status": "BLOCKED_ITEM_READ"}
    assert "delta_shopify_minus_qbo" not in result["results"][1]


def test_batch_rejects_wrong_sku_return_from_internal_check(monkeypatch):
    monkeypatch.setattr(s, "check_both", lambda sku: {"sku": "WRONG-SKU", "status": "TEST_MATCH"})
    result = s.check_many(["SKU-1", "SKU-2"])
    assert result["blocked"] == 2
    assert all(item["status"] == "BLOCKED_SKU_RESULT_MISMATCH" for item in result["results"])


def test_shopify_source_has_no_graphql_mutation_calls():
    import ast
    from pathlib import Path
    tree = ast.parse(Path(s.__file__).read_text(encoding="utf-8"))
    outbound = set()
    for fn in tree.body:
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for call in ast.walk(fn):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                continue
            if isinstance(call.func.value, ast.Name) and call.func.value.id == "requests":
                outbound.add((fn.name, call.func.attr))
    assert outbound == {("get_access_token", "post"), ("verify_installed_store", "post"), ("read_stock", "post"), ("read_owner_proof", "post"), ("verify_tenant_store", "post"), ("read_tenant_owner_proof", "post"),
                        ("read_shopify_test_order", "post"),
                        ("read_shopify_test_orders", "post")}
    assert s.STOCK_QUERY.lstrip().startswith("query ")
    assert "mutation" not in s.STOCK_QUERY.lower()
    assert s.PILOT_ORDER_QUERY.lstrip().startswith("query ")
    assert "mutation" not in s.PILOT_ORDER_QUERY.lower()
    assert "customer" not in s.PILOT_ORDER_QUERY.lower()


def test_bounded_test_order_batch_blocks_pagination_and_non_test(monkeypatch):
    monkeypatch.setattr(FakeResponse, "raise_for_status", lambda self: None, raising=False)
    monkeypatch.setattr(s, "load_setup", lambda: object())
    monkeypatch.setattr(s, "get_access_token", lambda _: "FAKE")
    base={"data":{"orders":{"pageInfo":{"hasNextPage":False},
            "nodes":[{"id":"gid://shopify/Order/123","name":"#1001","test":True}]}}}
    payload=[base]
    def request(*args, **kwargs):
        assert kwargs["json"]["query"] == s.BATCH_ORDER_QUERY
        assert "mutation" not in kwargs["json"]["query"].lower()
        return FakeResponse(body=payload[0])
    monkeypatch.setattr(s.requests,"post",request)
    assert len(s.read_shopify_test_orders()) == 1
    payload[0]={"data":{"orders":{"pageInfo":{"hasNextPage":True},
                                    "nodes":base["data"]["orders"]["nodes"]}}}
    with pytest.raises(ValueError,match="pagination"):
        s.read_shopify_test_orders()
    payload[0]={"data":{"orders":{"pageInfo":{"hasNextPage":False},
                                    "nodes":[{"id":"gid://shopify/Order/123","test":False}]}}}
    with pytest.raises(ValueError,match="non-test"):
        s.read_shopify_test_orders()
    payload[0]={"data":{"orders":{"pageInfo":{"hasNextPage":False},
                                    "nodes":base["data"]["orders"]["nodes"] * 2}}}
    with pytest.raises(ValueError,match="Duplicate"):
        s.read_shopify_test_orders()


def test_price_guards_currency_draft_and_unverified_policy():
    original = {"catalog_price": "100.00", "catalog_currency": "TRY", "product_status": "ACTIVE"}
    item = {"UnitPrice": 100}
    assert s.price_evidence(original, item, "USD")["status"] == "BLOCKED_PRICE_CURRENCY_MISMATCH"
    assert s.price_evidence(original, item, None)["status"] == "BLOCKED_QBO_CURRENCY_UNKNOWN"
    assert s.price_evidence(original, {"UnitPrice": None}, "TRY")["status"] == "BLOCKED_PRICE_FIELDS_MISSING"
    assert s.price_evidence({**original, "product_status": "DRAFT"}, item, "TRY")["status"] == "BLOCKED_PRODUCT_NOT_ACTIVE"
    assert s.price_evidence(original, item, "TRY")["status"] == "BLOCKED_PRICE_POLICY_UNVERIFIED"
    assert "price_delta" not in s.price_evidence(original, item, "USD")


def test_graphql_price_query_uses_read_only_shop_currency(cred, monkeypatch, records):
    calls=install_fake_requests(monkeypatch,records)
    s.read_stock(cred,"VERICON-TEST-001")
    query=calls[1]["json"]["query"]
    assert "shop { currencyCode }" in query
    assert "price" in query
    assert "mutation" not in query.lower()


def test_shopify_tenant_credentials_isolated_from_pilot(tmp_path, monkeypatch):
    import uuid
    monkeypatch.setattr(s, "PRIVATE", tmp_path / "private")
    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    store_a, store_b = "tenant-a.myshopify.com", "tenant-b.myshopify.com"
    s.save_tenant_setup(first, store_a, "TEST_ID_A", "TEST_SECRET_A")
    with pytest.raises(ValueError, match="unavailable"):
        s.load_tenant_setup(second, store_a)
    with pytest.raises(ValueError, match="unavailable"):
        s.load_tenant_setup(first, store_b)
    s.save_tenant_setup(second, store_b, "TEST_ID_B", "TEST_SECRET_B")
    assert s.load_tenant_setup(first, store_a).client_id == "TEST_ID_A"
    assert s.load_tenant_setup(second, store_b).client_id == "TEST_ID_B"
    assert not (s.PRIVATE / "shopify_setup.json").exists()


def test_shopify_tenant_credentials_fail_closed_on_tampering(tmp_path, monkeypatch):
    import uuid
    monkeypatch.setattr(s, "PRIVATE", tmp_path / "private")
    user = str(uuid.uuid4())
    store = "tenant-a.myshopify.com"
    s.save_tenant_setup(user, store, "FAKE_ID", "FAKE_SECRET")
    with pytest.raises(FileExistsError):
        s.save_tenant_setup(user, store, "REPLACEMENT", "REPLACEMENT")
    path = s._tenant_setup_path(user, store)
    data = json.loads(path.read_text());data["store"] = "other.myshopify.com"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="identity mismatch"):
        s.load_tenant_setup(user, store)


def test_verify_tenant_store_uses_only_tenant_domain(tmp_path, monkeypatch):
    import uuid
    monkeypatch.setattr(s, "PRIVATE", tmp_path / "private")
    owner=str(uuid.uuid4()); store="tenant-b.myshopify.com"
    s.save_tenant_setup(owner,store,"TEST_B_ID","TEST_B_SECRET")
    urls=[]
    def fake_post(url, *, data=None, json=None, headers=None, timeout=None):
        urls.append(url)
        assert store in url and s.STORE not in url
        if url.endswith("/oauth/access_token"):
            assert data["client_id"] == "TEST_B_ID"
            return FakeResponse(body={"access_token":"FAKE_B_TOKEN","scope":"read_products,read_inventory,read_locations"})
        assert headers["X-Shopify-Access-Token"] == "FAKE_B_TOKEN"
        return FakeResponse(body={"data":{"shop":{"myshopifyDomain":store}}})
    monkeypatch.setattr(s.requests,"post",fake_post)
    assert s.verify_tenant_store(owner,store)["app_access_verified"] is True
    assert len(urls)==2
    with pytest.raises(ValueError,match="unavailable"):
        s.verify_tenant_store(str(uuid.uuid4()),store)


def test_verify_tenant_store_rejects_wrong_shop_identity(tmp_path, monkeypatch):
    import uuid
    monkeypatch.setattr(s,"PRIVATE",tmp_path / "private")
    owner=str(uuid.uuid4());store="tenant-b.myshopify.com"
    s.save_tenant_setup(owner,store,"TEST_ID","TEST_SECRET")
    def fake_post(url, *, data=None, json=None, headers=None, timeout=None):
        if url.endswith("/oauth/access_token"):
            return FakeResponse(body={"access_token":"FAKE","scope":"read_products,read_inventory,read_locations"})
        return FakeResponse(body={"data":{"shop":{"myshopifyDomain":s.STORE}}})
    monkeypatch.setattr(s.requests,"post",fake_post)
    with pytest.raises(ValueError,match="identity mismatch"):
        s.verify_tenant_store(owner,store)


def test_second_customer_cannot_bind_same_shopify_store(tmp_path, monkeypatch):
    import uuid
    monkeypatch.setattr(s, "PRIVATE", tmp_path / "private")
    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    store = "tenant-a.myshopify.com"
    s.save_tenant_setup(first, store, "TEST_ID_A", "TEST_SECRET_A")
    with pytest.raises(ValueError, match="already linked"):
        s.save_tenant_setup(second, store, "TEST_ID_B", "TEST_SECRET_B")
    assert s.load_tenant_setup(first, store).client_id == "TEST_ID_A"
    with pytest.raises(ValueError, match="unavailable"):
        s.load_tenant_setup(second, store)
    s.save_tenant_setup(second, "tenant-b.myshopify.com", "TEST_ID_B", "TEST_SECRET_B")
    assert s.load_tenant_setup(second, "tenant-b.myshopify.com").client_id == "TEST_ID_B"
