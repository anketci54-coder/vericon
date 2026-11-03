"""Offline, no-secret tests for QBO sandbox OAuth and Item read."""

import json
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import qbo_oauth as q


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


@pytest.fixture
def cfg(tmp_path):
    return q.Config(
        client_id="test-public-id",
        client_secret="test-not-real-secret",
        redirect_uri="https://example.test/oauth/quickbooks/callback",
        private_dir=tmp_path / "private",
        expected_realm="12345",
    )


def test_authorization_state_rejects_forgery_and_replay(cfg):
    url = q.create_authorization_url(cfg)
    parsed = parse_qs(urlparse(url).query)
    assert parsed["scope"] == [q.SCOPE]
    assert parsed["redirect_uri"] == [cfg.redirect_uri]
    state = parsed["state"][0]
    with pytest.raises(ValueError, match="mismatch"):
        q.check_state(cfg, "incorrect")
    q.check_state(cfg, state)
    with pytest.raises(ValueError, match="Missing"):
        q.check_state(cfg, state)


def test_oauth_exchanges_code_and_encrypts_tokens(cfg, monkeypatch):
    url = q.create_authorization_url(cfg)
    state = parse_qs(urlparse(url).query)["state"][0]
    seen = {}

    def post(url, *, auth, data, headers, timeout):
        seen.update(url=url, auth=auth, data=data)
        return FakeResponse({"access_token": "AT_NONREAL", "refresh_token": "RT_NONREAL", "expires_in": 3600})

    monkeypatch.setattr(q.requests, "post", post)
    q.complete_authorization(cfg, state=state, code="testcode", realm="12345")
    assert seen["data"]["grant_type"] == "authorization_code"
    assert seen["url"] == q.TOKEN_URL
    stored = (cfg.private_dir / "qbo_tokens.enc").read_bytes()
    assert b"AT_NONREAL" not in stored and b"RT_NONREAL" not in stored
    assert oct((cfg.private_dir / "qbo_tokens.enc").stat().st_mode & 0o777) == "0o600"
    assert q.load_tokens(cfg)["realm"] == "12345"
    assert (cfg.private_dir / "qbo.key").stat().st_mode & 0o077 == 0


def test_wrong_sandbox_realm_blocks_token_exchange(cfg, monkeypatch):
    state = parse_qs(urlparse(q.create_authorization_url(cfg)).query)["state"][0]
    def must_not_call(*args, **kwargs):
        raise AssertionError("Should not request OAuth tokens for wrong company")
    monkeypatch.setattr(q.requests, "post", must_not_call)
    with pytest.raises(ValueError, match="Wrong"):
        q.complete_authorization(cfg, state=state, code="code", realm="456")


def test_expired_token_refreshes_and_rotates_refresh_token(cfg, monkeypatch):
    q._save_tokens(cfg, {"access_token": "OLD_ACCESS", "refresh_token": "OLD_REFRESH", "expires_in": 0}, "12345")
    called = []

    def post(url, *, auth, data, headers, timeout):
        called.append(data.copy())
        return FakeResponse({"access_token": "NEW_ACCESS", "refresh_token": "NEW_REFRESH", "expires_in": 3600})

    monkeypatch.setattr(q.requests, "post", post)
    assert q.get_access_token(cfg) == ("NEW_ACCESS", "12345")
    assert called[0]["refresh_token"] == "OLD_REFRESH"
    assert q.load_tokens(cfg)["refresh_token"] == "NEW_REFRESH"


def test_read_item_is_read_only_and_sanitized(cfg, monkeypatch):
    q._save_tokens(cfg, {"access_token": "AT_NONREAL", "refresh_token": "RT_NONREAL", "expires_in": 3600}, "12345")
    seen = {}

    def get(url, *, params, headers, timeout):
        seen.update(url=url, params=params, headers=headers)
        return FakeResponse({"QueryResponse": {"Item": [{
            "Id": "19", "Name": "VERICON TEST", "Sku": "VERICON-TEST-001",
            "Type": "Inventory", "TrackQtyOnHand": True, "QtyOnHand": 7,
            "UnitPrice": 100, "private_extra": "not displayed",
        }]}})

    monkeypatch.setattr(q.requests, "get", get)
    result = q.read_inventory_item(cfg, "VERICON TEST")
    assert len(result["items"]) == 1
    assert result["items"][0]["QtyOnHand"] == 7
    assert "private_extra" not in json.dumps(result)
    assert seen["url"].startswith(q.SANDBOX_API)
    assert seen["params"]["query"] == "SELECT * FROM Item WHERE Name = 'VERICON TEST'"
    with pytest.raises(ValueError, match="Invalid"):
        q.read_inventory_item(cfg, "X' OR Name != 'X")


def test_api_error_does_not_reveal_response_body(cfg, monkeypatch):
    q._save_tokens(cfg, {"access_token": "AT_NONREAL", "refresh_token": "RT_NONREAL", "expires_in": 3600}, "12345")
    monkeypatch.setattr(q.requests, "get", lambda *args, **kwargs: FakeResponse({"token": "SECRET"}, status=401))
    with pytest.raises(ValueError, match="HTTP 401") as err:
        q.read_inventory_item(cfg, "VERICON TEST")
    assert "SECRET" not in str(err.value)


def test_qbo_fault_is_blocked(cfg, monkeypatch):
    q._save_tokens(cfg, {"access_token": "A", "refresh_token": "B", "expires_in": 3600}, "12345")
    monkeypatch.setattr(q.requests, "get", lambda *args, **kwargs: FakeResponse({"Fault": {"type": "ValidationFault"}}))
    with pytest.raises(ValueError, match="fault"):
        q.read_inventory_item(cfg, "VERICON TEST")


def test_sandbox_loopback_redirect_is_supported(monkeypatch, tmp_path):
    monkeypatch.setenv("VERICON_QBO_CLIENT_ID", "fake-id")
    monkeypatch.setenv("VERICON_QBO_CLIENT_SECRET", "fake-secret")
    monkeypatch.setenv("VERICON_QBO_REDIRECT_URI", "http://localhost:8782/oauth/quickbooks/callback")
    monkeypatch.setenv("VERICON_QBO_PRIVATE_DIR", str(tmp_path / "private"))
    assert q.Config.from_env().redirect_uri.startswith("http://localhost:8782/")


def test_saved_setup_permissions_and_values(monkeypatch, tmp_path):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    setup = private / "qbo_setup.json"
    setup.write_text(json.dumps({
        "VERICON_QBO_CLIENT_ID": "TEST_ID",
        "VERICON_QBO_CLIENT_SECRET": "TEST_SECRET",
        "VERICON_QBO_REDIRECT_URI": "http://localhost:8782/oauth/quickbooks/callback",
        "VERICON_QBO_EXPECTED_REALM": "12345",
    }), encoding="utf-8")
    setup.chmod(0o600)
    monkeypatch.setattr(q, "BASE_DIR", tmp_path)
    result = q.load_saved_setup()
    assert result.expected_realm == "12345"
    assert result.private_dir == private
    setup.chmod(0o644)
    with pytest.raises(PermissionError, match="unsafe"):
        q.load_saved_setup()
    setup.chmod(0o600)
    private.chmod(0o755)
    with pytest.raises(PermissionError, match="unsafe"):
        q.load_saved_setup()
