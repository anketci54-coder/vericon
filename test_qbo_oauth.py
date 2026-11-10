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


def test_supabase_auth_me_validates_signature_and_identity(monkeypatch):
    """Isolated signing key only; no access to a customer tenant or real account."""
    import uuid
    from types import SimpleNamespace
    from cryptography.hazmat.primitives.asymmetric import ec
    from fastapi import HTTPException
    from starlette.requests import Request
    import jwt

    private = ec.generate_private_key(ec.SECP256R1())
    key = private.public_key()
    monkeypatch.setattr(q, "SUPABASE_JWKS", SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key)))
    subject = str(uuid.uuid4())
    claims = {"sub": subject, "iss": q.SUPABASE_ISSUER, "aud": "authenticated",
              "role": "authenticated", "iat": int(time.time()) - 30,
              "exp": int(time.time()) + 3600}
    def signed(**changes):
        return jwt.encode({**claims, **changes}, private, algorithm="ES256")
    assert q._verified_customer_subject("Bearer " + signed()) == subject
    result = q.auth_identity(Request({"type":"http","method":"GET","path":"/auth/me",
        "headers":[(b"authorization",("Bearer " + signed()).encode())],"query_string":b""}))
    assert result == {"authenticated": True,"subject":subject,"tenant_authorized":False}
    invalid = [None, "Basic xx", "Bearer ", "Bearer invalid", "Bearer " + signed(exp=1),
               "Bearer " + signed(iss="https://other.supabase.co/auth/v1"),
               "Bearer " + signed(aud="other"),
               "Bearer " + signed(role="service_role"),
               "Bearer " + signed(sub="not-a-uuid"),
               "Bearer " + signed(iat=int(time.time())+1000),
               "Bearer " + jwt.encode(claims, ec.generate_private_key(ec.SECP256R1()),
                                       algorithm="ES256")]
    for header in invalid:
        with pytest.raises(HTTPException) as exc:
            q._verified_customer_subject(header)
        assert exc.value.status_code == 401


def test_oauth_persists_verified_user_and_keeps_it_on_refresh(cfg, monkeypatch):
    import uuid
    owner = str(uuid.uuid4())
    state = parse_qs(urlparse(q.create_authorization_url(cfg, user_id=owner)).query)["state"][0]
    monkeypatch.setattr(q, "_exchange", lambda config, params: {
        "access_token": "FAKE_ACCESS", "refresh_token": "FAKE_REFRESH", "expires_in": 3600})
    q.complete_authorization(cfg, state=state, code="fake", realm="12345", user_id=owner)
    assert q.load_tokens(cfg)["authorized_user_id"] == owner
    q._save_tokens(cfg, {"access_token": "NEW_FAKE", "refresh_token": "NEW_REFRESH", "expires_in": 3600},
                   "12345", user_id=q.load_tokens(cfg).get("authorized_user_id"))
    assert q.load_tokens(cfg)["authorized_user_id"] == owner


def test_pilot_qbo_owner_requires_matching_rls_record(monkeypatch):
    import uuid
    from fastapi import HTTPException
    owner = str(uuid.uuid4())
    monkeypatch.setattr(q, "_verified_customer_subject", lambda header: owner if header == "Bearer valid" else (_ for _ in ()).throw(HTTPException(401)))
    monkeypatch.setenv("VERICON_SUPABASE_PUBLISHABLE_KEY", "test-public-key")
    seen = {}
    def get(url, *, params, headers, timeout):
        seen.update(params=params, headers=headers)
        return FakeResponse([{"qbo_realm_id": "12345", "connection_status": "pilot_linked"}])
    monkeypatch.setattr(q.requests, "get", get)
    assert q._pilot_qbo_owner("Bearer valid", "12345") == owner
    assert seen["params"]["user_id"] == "eq." + owner
    assert seen["headers"]["Authorization"] == "Bearer valid"
    with pytest.raises(HTTPException) as err:
        q._pilot_qbo_owner("Bearer valid", "wrong-company")
    assert err.value.status_code == 403
    monkeypatch.delenv("VERICON_SUPABASE_PUBLISHABLE_KEY")
    with pytest.raises(HTTPException) as err:
        q._pilot_qbo_owner("Bearer valid", "12345")
    assert err.value.status_code == 503


def test_user_bound_oauth_state_rejects_wrong_user_and_legacy_callback(cfg):
    import uuid
    owner, stranger = str(uuid.uuid4()), str(uuid.uuid4())
    state = parse_qs(urlparse(q.create_authorization_url(cfg, user_id=owner)).query)["state"][0]
    with pytest.raises(ValueError, match="user binding"):
        q.check_state(cfg, state, user_id=stranger)
    with pytest.raises(ValueError, match="user binding"):
        q.check_state(cfg, state)
    q.check_state(cfg, state, user_id=owner)
    with pytest.raises(ValueError, match="Missing"):
        q.check_state(cfg, state, user_id=owner)


def test_authorization_state_rejects_forgery_and_replay(cfg):
    url = q.create_authorization_url(cfg)
    parsed = parse_qs(urlparse(url).query)
    assert parsed["scope"] == [q.SCOPE]
    assert parsed["redirect_uri"] == [cfg.redirect_uri]
    state = parsed["state"][0]
    with pytest.raises(ValueError, match="mismatch"):
        q.check_state(cfg, "incorrect")
    wrong_realm = q.Config(cfg.client_id, cfg.client_secret, cfg.redirect_uri,
                           cfg.private_dir, "54321")
    wrong_client = q.Config("other-app", cfg.client_secret, cfg.redirect_uri,
                            cfg.private_dir, cfg.expected_realm)
    with pytest.raises(ValueError, match="tenant binding"):
        q.check_state(wrong_realm, state)
    with pytest.raises(ValueError, match="tenant binding"):
        q.check_state(wrong_client, state)
    q.check_state(cfg, state)
    with pytest.raises(ValueError, match="Missing"):
        q.check_state(cfg, state)
    # Without authenticated tenant sessions, every future data URL must fail closed.
    import asyncio
    from starlette.requests import Request
    from fastapi.responses import PlainTextResponse
    async def next_route(_request):
        return PlainTextResponse("allowed")
    async def gate(path):
        request = Request({"type": "http", "method": "GET", "path": path,
                           "headers": [], "query_string": b""})
        return (await q.reject_unauthenticated_data_routes(request, next_route)).status_code
    assert asyncio.run(gate("/api/tenant-b/invoices")) == 403
    assert asyncio.run(gate("/health")) == 200
    assert asyncio.run(gate("/oauth/quickbooks/callback")) == 200


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
    wrong_realm = q.Config(cfg.client_id, cfg.client_secret, cfg.redirect_uri,
                           cfg.private_dir, "54321")
    unknown_realm = q.Config(cfg.client_id, cfg.client_secret, cfg.redirect_uri,
                             cfg.private_dir, None)
    with pytest.raises(ValueError, match="Authorized company"):
        q.load_tokens(wrong_realm)
    with pytest.raises(ValueError, match="Expected QuickBooks company ID"):
        q.load_tokens(unknown_realm)
    assert (cfg.private_dir / "qbo.key").stat().st_mode & 0o077 == 0
    alias = cfg.private_dir.parent / "other-tenant"
    alias.symlink_to(cfg.private_dir, target_is_directory=True)
    other = q.Config(cfg.client_id, cfg.client_secret, cfg.redirect_uri, alias, cfg.expected_realm)
    with pytest.raises(PermissionError, match="non-symlink"):
        q.get_access_token(other)


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
    unbound = q.Config(cfg.client_id, cfg.client_secret, cfg.redirect_uri, cfg.private_dir, None)
    with pytest.raises(ValueError, match="Expected QuickBooks company ID"):
        q.get_access_token(unbound)
    with pytest.raises(ValueError, match="Expected QuickBooks company ID"):
        q.read_inventory_item(unbound, "VERICON TEST")
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
    monkeypatch.delenv("VERICON_QBO_EXPECTED_REALM", raising=False)
    with pytest.raises(ValueError, match="Expected QuickBooks company ID"):
        q.Config.from_env()
    monkeypatch.setenv("VERICON_QBO_EXPECTED_REALM", "12345")
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


def test_force_refresh_rotates_unexpired_tokens(cfg, monkeypatch):
    q._save_tokens(cfg, {"access_token": "STILL_VALID", "refresh_token": "OLD_REFRESH", "expires_in": 3600}, "12345")
    called = []
    def post(url, *, auth, data, headers, timeout):
        called.append(data.copy())
        return FakeResponse({"access_token": "REFRESHED", "refresh_token": "NEW_REFRESH", "expires_in": 3600})
    monkeypatch.setattr(q.requests, "post", post)
    token, realm = q.get_access_token(cfg, force_refresh=True)
    assert (token, realm) == ("REFRESHED", "12345")
    assert len(called) == 1 and called[0]["grant_type"] == "refresh_token"
    assert q.load_tokens(cfg)["refresh_token"] == "NEW_REFRESH"


def test_read_item_by_sku_real_filter(cfg, monkeypatch):
    q._save_tokens(cfg, {"access_token": "A", "refresh_token": "B", "expires_in": 3600}, "12345")
    seen = {}
    def get(url, *, params, headers, timeout):
        seen.update(params=params, url=url)
        return FakeResponse({"QueryResponse": {"Item": [{
            "Id": "19", "Name": "VERICON TEST", "Sku": "VERICON-TEST-001",
            "Type": "Inventory", "TrackQtyOnHand": True, "QtyOnHand": 7,
        }]}})
    monkeypatch.setattr(q.requests, "get", get)
    result = q.read_inventory_item_by_sku(cfg, "VERICON-TEST-001")
    assert seen["params"]["query"] == "SELECT * FROM Item WHERE Sku = 'VERICON-TEST-001'"
    assert result["items"][0]["QtyOnHand"] == 7
    with pytest.raises(ValueError, match="Invalid SKU"):
        q.read_inventory_item_by_sku(cfg, "TEST' OR 1=1")


def test_read_item_by_sku_duplicates_fail_closed(cfg, monkeypatch):
    q._save_tokens(cfg, {"access_token": "A", "refresh_token": "B", "expires_in": 3600}, "12345")
    monkeypatch.setattr(q.requests, "get", lambda *args, **kwargs: FakeResponse({"QueryResponse": {"Item": [
        {"Sku": "VERICON-TEST-001", "Type": "Inventory", "QtyOnHand": 7},
        {"Sku": "VERICON-TEST-001", "Type": "Inventory", "QtyOnHand": 6},
    ]}}))
    with pytest.raises(ValueError, match="ambiguous"):
        q.read_inventory_item_by_sku(cfg, "VERICON-TEST-001")


def test_qbo_source_has_no_accounting_write_http_calls():
    # Regression guard: QBO data transport must remain GET-only.
    # POST is permitted exclusively for the OAuth token endpoint.
    import ast
    from pathlib import Path
    tree = ast.parse(Path(q.__file__).read_text(encoding="utf-8"))
    outbound = set()
    for fn in tree.body:
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for call in ast.walk(fn):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                continue
            if isinstance(call.func.value, ast.Name) and call.func.value.id == "requests":
                outbound.add((fn.name, call.func.attr))
                if (fn.name, call.func.attr) == ("_exchange", "post"):
                    assert call.args and isinstance(call.args[0], ast.Name)
                    assert call.args[0].id == "TOKEN_URL"
    assert ("_exchange", "post") in outbound
    assert ("_query_item", "get") in outbound
    assert all(method == "get" or (fn == "_exchange" and method == "post")
               for fn, method in outbound)


def test_qbo_currency_from_preferences_only_when_unambiguous(cfg, monkeypatch):
    q._save_tokens(cfg, {"access_token": "A", "refresh_token": "B", "expires_in": 3600}, "12345")
    seen=[]
    def get(url, *, headers, timeout):
        seen.append(url)
        return FakeResponse({"Preferences": {"CurrencyPrefs": {
            "MultiCurrencyEnabled": False, "HomeCurrency": {"value": "USD"}}}})
    monkeypatch.setattr(q.requests,"get",get)
    assert q.read_home_currency(cfg)=="USD"
    assert seen[0].endswith('/preferences')
    monkeypatch.setattr(q.requests,"get",lambda *args,**kwargs: FakeResponse({
        "Preferences": {"CurrencyPrefs": {"MultiCurrencyEnabled": True,
                                           "HomeCurrency": {"value": "USD"}}}}))
    assert q.read_home_currency(cfg) is None
    monkeypatch.setattr(q.requests,"get",lambda *args,**kwargs: FakeResponse({
        "Preferences": {"CurrencyPrefs": {"MultiCurrencyEnabled": False}}}))
    assert q.read_home_currency(cfg) is None


def test_qbo_currency_api_failure_does_not_expose_body(cfg, monkeypatch):
    q._save_tokens(cfg, {"access_token": "A", "refresh_token": "B", "expires_in": 3600}, "12345")
    monkeypatch.setattr(q.requests,"get",lambda *args,**kwargs: FakeResponse({"secret":"HIDE"},status=403))
    with pytest.raises(ValueError,match="HTTP 403") as err:
        q.read_home_currency(cfg)
    assert "HIDE" not in str(err.value)


def test_shopify_proof_start_requires_verified_pilot_owner(monkeypatch):
    from fastapi import HTTPException
    from starlette.requests import Request
    monkeypatch.setattr(q, "_shopify_owner", lambda header: (_ for _ in ()).throw(HTTPException(status_code=401)))
    req = Request({"type":"http","method":"POST","path":"/shopify/ownership/start","headers":[]})
    with pytest.raises(HTTPException) as exc:
        q.shopify_ownership_start(req)
    assert exc.value.status_code == 401


def test_shopify_proof_wrong_code_does_not_verify(cfg, monkeypatch):
    import hashlib, json, uuid
    from fastapi import HTTPException
    from starlette.requests import Request
    owner = str(uuid.uuid4())
    monkeypatch.setattr(q, "_shopify_owner", lambda header: owner)
    monkeypatch.setattr(q, "load_saved_setup", lambda: cfg)
    monkeypatch.setattr("shopify_read.load_setup", lambda: object())
    monkeypatch.setattr("shopify_read.read_owner_proof", lambda config: "incorrect-code")
    path = q._shopify_proof_file(cfg)
    q._secure_dir(cfg)
    q._atomic_write(path, json.dumps({"user_id": owner, "store":"hudys3-p0.myshopify.com", "digest":hashlib.sha256(b"correct-code").hexdigest(), "expires_at":int(time.time())+60}).encode())
    req = Request({"type":"http","method":"POST","path":"/shopify/ownership/verify","headers":[]})
    with pytest.raises(HTTPException) as exc:
        q.shopify_ownership_verify(req)
    assert exc.value.status_code == 400
    assert not (cfg.private_dir / "shopify_owner_verified.json").exists()
