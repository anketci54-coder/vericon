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
            "productVariants": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": [{
                    "id": "gid://shopify/ProductVariant/1",
                    "sku": "VERICON-TEST-001",
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


def test_missing_read_scope_blocks_access(cred, monkeypatch):
    monkeypatch.setattr(s.requests, "post",
        lambda *args, **kwargs: FakeResponse(body={"access_token": "token", "scope": "read_products"}))
    with pytest.raises(ValueError, match="scopes"):
        s.get_access_token(cred)


def test_exact_sku_stock_read_only(cred, monkeypatch, records):
    seen = install_fake_requests(monkeypatch, records)
    result = s.read_stock(cred, "VERICON-TEST-001")
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
    from datetime import datetime, timezone
    monkeypatch.setattr(qbo_oauth, "read_inventory_item", lambda cfg, name: {
        "query_time_utc": datetime.now(timezone.utc).isoformat(),
        "items": [{"Sku": "VERICON-TEST-001", "Type": "Inventory",
                   "TrackQtyOnHand": True, "QtyOnHand": 7}]
    })
    res = s.check_both("VERICON-TEST-001")
    assert res["delta_shopify_minus_qbo"] == "3"
    assert res["status"] == "TEST_DIFFERENCE"
    assert res["read_gap_seconds"] <= 30
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
    monkeypatch.setattr(qbo_oauth, "read_inventory_item", lambda cfg, name: {
        "query_time_utc": "2024-01-01T00:00:00+00:00",
        "items": [{"Sku": "VERICON-TEST-001", "Type": "Inventory",
                   "TrackQtyOnHand": True, "QtyOnHand": 7}]
    })
    res = s.check_both("VERICON-TEST-001")
    assert res["status"] == "BLOCKED_SNAPSHOT_TIME_GAP"
    assert "delta_shopify_minus_qbo" not in res
