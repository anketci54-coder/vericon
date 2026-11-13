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


@pytest.mark.parametrize('fault', ['none', 'env', 'permissions', 'symlink', 'missing', 'redirect'])
def test_runtime_preflight_is_read_only_and_fail_closed(tmp_path, monkeypatch, fault):
    monkeypatch.setattr(q, 'BASE_DIR', tmp_path)
    monkeypatch.setenv('VERICON_SUPABASE_PUBLISHABLE_KEY', 'sb_publishable_test')
    private = tmp_path / 'private'
    private.mkdir(mode=0o700)
    setup = {'VERICON_QBO_CLIENT_ID': 'fake', 'VERICON_QBO_CLIENT_SECRET': 'fake',
             'VERICON_QBO_EXPECTED_REALM': '123',
             'VERICON_QBO_REDIRECT_URI': 'https://app.vericon.site/oauth/quickbooks/callback'}
    if fault == 'redirect':
        setup['VERICON_QBO_REDIRECT_URI'] = 'https://other.test/callback'
    for name, data in [('qbo_setup.json', json.dumps(setup)), ('qbo.key', 'fake'),
                       ('shopify_setup.json', '{}')]:
        path = private / name
        path.write_text(data)
        path.chmod(0o600)
    if fault == 'env':
        monkeypatch.delenv('VERICON_SUPABASE_PUBLISHABLE_KEY')
    elif fault == 'permissions':
        (private / 'qbo.key').chmod(0o644)
    elif fault == 'symlink':
        (private / 'qbo.key').unlink()
        (private / 'qbo.key').symlink_to(private / 'qbo_setup.json')
    elif fault == 'missing':
        (private / 'qbo.key').unlink()
    before = {p.name: p.read_bytes() for p in private.iterdir()}
    monkeypatch.setattr(q.requests.sessions.Session, 'request',
                        lambda *a, **k: pytest.fail('preflight must not call providers'))
    if fault == 'none':
        q.runtime_preflight()
    else:
        with pytest.raises((ValueError, PermissionError)):
            q.runtime_preflight()
    assert {p.name: p.read_bytes() for p in private.iterdir()} == before


@pytest.mark.parametrize('user_id', [None, '11111111-1111-4111-8111-111111111111'])
def test_oauth_state_is_consumed_once_under_concurrent_callbacks(cfg, monkeypatch, user_id):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    state = parse_qs(urlparse(q.create_authorization_url(cfg, user_id=user_id)).query)['state'][0]
    state_path = q._oauth_state_file(cfg, state, user_id=user_id)
    both_read = Barrier(2)
    original_read = Path.read_bytes

    def read_before_consumption(path):
        data = original_read(path)
        if path == state_path:
            both_read.wait(timeout=5)
        return data

    monkeypatch.setattr(Path, 'read_bytes', read_before_consumption)

    def callback(_):
        try:
            q.check_state(cfg, state, user_id=user_id)
            return 'accepted'
        except ValueError:
            return 'rejected'

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(callback, range(2)))
    assert sorted(results) == ['accepted', 'rejected']
    assert not state_path.exists()


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
    monkeypatch.setattr(q, "_require_live_supabase_session", lambda token, subject: None)
    claims = {"sub": subject, "iss": q.SUPABASE_ISSUER, "aud": "authenticated",
              "role": "authenticated", "iat": int(time.time()) - 30,
              "exp": int(time.time()) + 3600, "session_id": str(uuid.uuid4())}
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
               "Bearer " + signed(session_id=None),
               "Bearer " + signed(session_id="invalid"),
               "Bearer " + signed(is_anonymous=True),
               "Bearer " + signed(sub="not-a-uuid"),
               "Bearer " + signed(iat=int(time.time())+1000),
               "Bearer " + jwt.encode(claims, ec.generate_private_key(ec.SECP256R1()),
                                       algorithm="ES256")]
    for header in invalid:
        with pytest.raises(HTTPException) as exc:
            q._verified_customer_subject(header)
        assert exc.value.status_code == 401


@pytest.mark.parametrize('upstream,expected', [(401,401), (403,401), (429,503),
                                            (500,503), (502,503), (503,503), (302,503)])
def test_auth_provider_failure_is_not_reported_as_logout(monkeypatch, upstream, expected):
    from fastapi import HTTPException
    monkeypatch.setenv('VERICON_SUPABASE_PUBLISHABLE_KEY', 'public-test')
    monkeypatch.setattr(q.requests, 'get', lambda *a, **kw: FakeResponse({}, upstream))
    with pytest.raises(HTTPException) as exc:
        q._require_live_supabase_session('synthetic', 'subject')
    assert exc.value.status_code == expected



def test_revoked_or_unavailable_supabase_session_is_denied(monkeypatch):
    import uuid
    from fastapi import HTTPException
    subject = str(uuid.uuid4())
    token = "not-a-real-token"
    monkeypatch.setenv("VERICON_SUPABASE_PUBLISHABLE_KEY", "public-test-key")
    observed = []
    def fake_get(url, *, headers, timeout, allow_redirects):
        assert allow_redirects is False
        assert url == q.SUPABASE_ISSUER + "/user"
        assert headers == {"apikey": "public-test-key", "Authorization": "Bearer " + token}
        assert timeout == 5
        observed.append(url)
        return FakeResponse({"id": subject}) if len(observed) == 1 else FakeResponse({}, status=401)
    monkeypatch.setattr(q.requests, "get", fake_get)
    q._require_live_supabase_session(token, subject)
    with pytest.raises(HTTPException) as exc:
        q._require_live_supabase_session(token, subject)
    assert exc.value.status_code == 401
    monkeypatch.delenv("VERICON_SUPABASE_PUBLISHABLE_KEY")
    with pytest.raises(HTTPException) as exc:
        q._require_live_supabase_session(token, subject)
    assert exc.value.status_code == 503


def test_supabase_session_identity_mismatch_and_network_failure_denied(monkeypatch):
    import uuid
    import requests
    from fastapi import HTTPException
    monkeypatch.setenv("VERICON_SUPABASE_PUBLISHABLE_KEY", "public-test-key")
    subject = str(uuid.uuid4())
    monkeypatch.setattr(q.requests, "get", lambda *a, **kw: FakeResponse({"id": str(uuid.uuid4())}))
    with pytest.raises(HTTPException) as exc:
        q._require_live_supabase_session("test", subject)
    assert exc.value.status_code == 401
    def network_fail(*a, **kw):
        raise requests.Timeout("simulated")
    monkeypatch.setattr(q.requests, "get", network_fail)
    with pytest.raises(HTTPException) as exc:
        q._require_live_supabase_session("test", subject)
    assert exc.value.status_code == 503


def test_revoked_validly_signed_jwt_denied_at_auth_endpoint(monkeypatch):
    import uuid
    from types import SimpleNamespace
    from cryptography.hazmat.primitives.asymmetric import ec
    from starlette.requests import Request
    import jwt
    private = ec.generate_private_key(ec.SECP256R1())
    subject = str(uuid.uuid4())
    signed = jwt.encode({
        "sub": subject, "iss": q.SUPABASE_ISSUER, "aud": "authenticated",
        "role": "authenticated", "iat": int(time.time()) - 5,
        "exp": int(time.time()) + 1200, "session_id": str(uuid.uuid4()),
    }, private, algorithm="ES256")
    monkeypatch.setattr(q, "SUPABASE_JWKS", SimpleNamespace(
        get_signing_key_from_jwt=lambda _: SimpleNamespace(key=private.public_key())))
    monkeypatch.setenv("VERICON_SUPABASE_PUBLISHABLE_KEY", "public-test-key")
    state = {"status": 200}
    def fake_get(url, *, headers, timeout, allow_redirects):
        assert allow_redirects is False
        assert url == q.SUPABASE_ISSUER + "/user"
        assert headers["Authorization"] == "Bearer " + signed
        return FakeResponse({"id": subject} if state["status"] == 200 else {},
                            status=state["status"])
    monkeypatch.setattr(q.requests, "get", fake_get)
    from fastapi import HTTPException
    req = Request({"type": "http", "method": "GET", "path": "/auth/me",
                   "headers": [(b"authorization", ("Bearer " + signed).encode())],
                   "query_string": b""})
    first = q.auth_identity(req)
    assert first["authenticated"] is True and first["subject"] == subject
    state["status"] = 403
    with pytest.raises(HTTPException) as exc:
        q.auth_identity(req)
    assert exc.value.status_code == 401

def test_oauth_persists_verified_user_and_keeps_it_on_refresh(cfg, monkeypatch):
    import uuid
    owner = str(uuid.uuid4())
    state = parse_qs(urlparse(q.create_authorization_url(cfg, user_id=owner)).query)["state"][0]
    monkeypatch.setattr(q, "_exchange", lambda config, params: {
        "access_token": "FAKE_ACCESS", "refresh_token": "FAKE_REFRESH", "expires_in": 3600})
    q.complete_authorization(cfg, state=state, code="fake", realm="12345", user_id=owner)
    assert q.load_tenant_tokens(cfg,user_id=owner)["authorized_user_id"] == owner
    q.save_tenant_tokens(cfg, {"access_token": "NEW_FAKE", "refresh_token": "NEW_REFRESH", "expires_in": 3600},
                         user_id=q.load_tenant_tokens(cfg,user_id=owner)["authorized_user_id"])
    assert q.load_tenant_tokens(cfg,user_id=owner)["authorized_user_id"] == owner


def test_pilot_qbo_owner_requires_matching_rls_record(monkeypatch):
    import uuid
    from fastapi import HTTPException
    owner = str(uuid.uuid4())
    monkeypatch.setattr(q, "_verified_customer_subject", lambda header: owner if header == "Bearer valid" else (_ for _ in ()).throw(HTTPException(401)))
    monkeypatch.setenv("VERICON_SUPABASE_PUBLISHABLE_KEY", "test-public-key")
    seen = {}
    row = {"user_id": owner, "qbo_realm_id": "12345", "shop_domain": "hudys3-p0.myshopify.com",
           "connection_status": "pilot_linked"}
    def get(url, *, params, headers, timeout):
        seen.update(params=params, headers=headers)
        return FakeResponse([dict(row)])
    monkeypatch.setattr(q.requests, "get", get)
    assert q._pilot_qbo_owner("Bearer valid", "12345") == owner
    assert seen["params"]["user_id"] == "eq." + owner
    assert seen["headers"]["Authorization"] == "Bearer valid"
    with pytest.raises(HTTPException) as err:
        q._pilot_qbo_owner("Bearer valid", "wrong-company")
    assert err.value.status_code == 403
    row["shop_domain"] = "tenant-b.myshopify.com"
    with pytest.raises(HTTPException) as err:
        q._pilot_qbo_owner("Bearer valid", "12345")
    assert err.value.status_code == 403
    row["shop_domain"] = "hudys3-p0.myshopify.com"
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
    with pytest.raises(ValueError, match="Missing"):
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


@pytest.mark.parametrize('target', ['key', 'setup', 'directory'])
def test_qbo_secret_read_rejects_symlink_even_with_private_permissions(cfg, tmp_path, monkeypatch, target):
    outside = tmp_path / 'outside'
    outside.mkdir(mode=0o700)
    key = q.Fernet.generate_key()
    (outside / 'qbo.key').write_bytes(key)
    (outside / 'qbo.key').chmod(0o600)
    (outside / 'qbo_setup.json').write_text(json.dumps({
        'VERICON_QBO_CLIENT_ID': 'fake', 'VERICON_QBO_CLIENT_SECRET': 'fake',
        'VERICON_QBO_REDIRECT_URI': 'http://localhost:8782/oauth/quickbooks/callback',
        'VERICON_QBO_EXPECTED_REALM': '12345'}))
    (outside / 'qbo_setup.json').chmod(0o600)
    monkeypatch.setattr(q, 'BASE_DIR', tmp_path)
    if target == 'directory':
        cfg.private_dir.symlink_to(outside, target_is_directory=True)
    else:
        cfg.private_dir.mkdir(mode=0o700)
        name = 'qbo.key' if target == 'key' else 'qbo_setup.json'
        (cfg.private_dir / name).symlink_to(outside / name)
    with pytest.raises((ValueError, PermissionError)):
        q._key(cfg) if target == 'key' else q.load_saved_setup()


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
    assert all(method == "get" or (fn in ("_exchange", "disconnect_tenant_quickbooks") and method == "post")
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


@pytest.mark.parametrize('tenant', [False, True])
def test_shopify_proof_single_consumption_and_new_challenge_preserved(cfg, monkeypatch, tenant):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from starlette.requests import Request
    import shopify_read as s
    owner = '11111111-1111-4111-8111-111111111111'
    q._secure_dir(cfg)
    monkeypatch.setattr(q, 'load_saved_setup', lambda: cfg)
    monkeypatch.setattr(q, '_shopify_owner', lambda h: owner)
    monkeypatch.setattr(q, '_tenant_shopify_context', lambda h: {
        'user_id':owner, 'store':'tenant-b.myshopify.com', 'verified':False})
    monkeypatch.setattr(s, '_tenant_setup_path', lambda *a: cfg.private_dir / 'unused')
    monkeypatch.setattr(s, 'load_setup', lambda: None)
    start = q.tenant_shopify_ownership_start if tenant else q.shopify_ownership_start
    verify = q.tenant_shopify_ownership_verify if tenant else q.shopify_ownership_verify
    read = 'read_tenant_owner_proof' if tenant else 'read_owner_proof'
    req = Request({'type':'http','method':'POST','path':'/proof','headers':[]})
    code = start(req)['challenge']
    barrier = Barrier(2)
    def observed(*args):
        barrier.wait(timeout=5)
        return code
    monkeypatch.setattr(s, read, observed)
    def call(_):
        try: return verify(req)['verified']
        except q.HTTPException as exc: return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        values=list(pool.map(call, range(2)))
    assert values.count(True)==1 and values.count(400)==1
    # An old verification must not consume a newly issued challenge.
    code = start(req)['challenge']
    def replaced(*args):
        start(req)
        return code
    monkeypatch.setattr(s, read, replaced)
    with pytest.raises(q.HTTPException) as exc: verify(req)
    assert exc.value.status_code==400
    path = q._tenant_proof_path(cfg,owner,'tenant-b.myshopify.com') if tenant else q._shopify_proof_file(cfg)
    assert path.exists()


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


def test_tenant_token_files_are_isolated_and_legacy_unchanged(cfg):
    import uuid
    from dataclasses import replace
    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    payload = {"access_token":"TEST_A","refresh_token":"TEST_RA"}
    q._save_tokens(cfg,payload,"12345",user_id=first)
    legacy = (cfg.private_dir / "qbo_tokens.enc").read_bytes()
    q.save_tenant_tokens(cfg,payload,user_id=first)
    with pytest.raises(ValueError,match="not available"):
        q.load_tenant_tokens(cfg,user_id=second)
    other_company = replace(cfg, expected_realm="987654321")
    q.save_tenant_tokens(other_company,{"access_token":"TEST_B","refresh_token":"TEST_RB"},user_id=second)
    assert q.load_tenant_tokens(cfg,user_id=first)["access_token"] == "TEST_A"
    assert q.load_tenant_tokens(other_company,user_id=second)["access_token"] == "TEST_B"
    with pytest.raises(ValueError,match="not available"):
        q.load_tenant_tokens(cfg,user_id=second)
    with pytest.raises(ValueError,match="not available"):
        q.load_tenant_tokens(other_company,user_id=first)
    assert (cfg.private_dir / "qbo_tokens.enc").read_bytes() == legacy
    assert q.load_tokens(cfg)["authorized_user_id"] == first


def test_user_oauth_callback_does_not_overwrite_existing_pilot(cfg, monkeypatch):
    import uuid
    owner, other = str(uuid.uuid4()), str(uuid.uuid4())
    monkeypatch.setattr(q, "_exchange", lambda config, params: {
        "access_token": "FRESH", "refresh_token": "FRESH_R", "expires_in": 3600})
    q._save_tokens(cfg,{"access_token":"PILOT","refresh_token":"PILOT_R"},"12345",user_id=other)
    before=(cfg.private_dir/"qbo_tokens.enc").read_bytes()
    state=parse_qs(urlparse(q.create_authorization_url(cfg,user_id=owner)).query)["state"][0]
    q.complete_authorization(cfg,state=state,code="fake",realm="12345",user_id=owner)
    assert q.load_tenant_tokens(cfg,user_id=owner)["access_token"] == "FRESH"
    assert (cfg.private_dir/"qbo_tokens.enc").read_bytes() == before
    assert q.load_tokens(cfg)["access_token"] == "PILOT"
    with pytest.raises(ValueError,match="not available"):
        q.load_tenant_tokens(cfg,user_id=other)


def test_parallel_oauth_states_do_not_overwrite_or_cross_authorize(cfg, monkeypatch):
    import uuid
    a,b=str(uuid.uuid4()),str(uuid.uuid4())
    sa=parse_qs(urlparse(q.create_authorization_url(cfg,user_id=a)).query)["state"][0]
    sb=parse_qs(urlparse(q.create_authorization_url(cfg,user_id=b)).query)["state"][0]
    assert q._callback_state_record(cfg,sa)["user_id"]==a
    assert q._callback_state_record(cfg,sb)["user_id"]==b
    with pytest.raises(ValueError,match="user binding"):
        q.check_state(cfg,sa,user_id=b)
    q.check_state(cfg,sa,user_id=a)
    q.check_state(cfg,sb,user_id=b)
    with pytest.raises(ValueError,match="Missing"):
        q._callback_state_record(cfg,sa)


def test_second_qbo_company_callback_isolated_from_pilot(cfg, monkeypatch):
    from dataclasses import replace
    import uuid
    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    pilot = replace(cfg, expected_realm="12345")
    tenant = q._tenant_qbo_config(pilot, "987654321")
    monkeypatch.setattr(q, "_exchange", lambda config, params: {
        "access_token": "TEST_TENANT", "refresh_token": "TEST_REFRESH", "expires_in": 3600})
    q._save_tokens(pilot, {"access_token": "TEST_PILOT", "refresh_token": "TEST_PILOT_REFRESH"},
                   "12345", user_id=first)
    before = (cfg.private_dir / "qbo_tokens.enc").read_bytes()
    state = parse_qs(urlparse(q.create_authorization_url(tenant, user_id=second)).query)["state"][0]
    record = q._callback_state_record(pilot, state)
    assert record["expected_realm"] == "987654321"
    with pytest.raises(ValueError, match="Wrong QuickBooks sandbox company"):
        q.complete_authorization(tenant, state=state, code="fake", realm="12345", user_id=second)
    q.complete_authorization(tenant, state=state, code="fake", realm="987654321", user_id=second)
    assert q.load_tenant_tokens(tenant, user_id=second)["realm"] == "987654321"
    with pytest.raises(ValueError, match="not available"):
        q.load_tenant_tokens(pilot, user_id=second)
    assert (cfg.private_dir / "qbo_tokens.enc").read_bytes() == before


def test_tenant_quickbooks_start_fails_closed_without_shopify_setup(cfg, monkeypatch):
    from fastapi import HTTPException
    from starlette.requests import Request
    from dataclasses import replace
    import uuid
    owner = str(uuid.uuid4())
    monkeypatch.setattr(q, "_authorized_tenant_connection", lambda header: {
        "user_id": owner, "realm": "987654321", "store": "tenant-b.myshopify.com"})
    monkeypatch.setattr(q, "load_saved_setup", lambda: replace(
        cfg, redirect_uri="https://app.vericon.site/oauth/quickbooks/callback"))
    monkeypatch.setattr("shopify_read.load_tenant_setup", lambda user, store: (_ for _ in ()).throw(ValueError("missing")))
    req = Request({"type":"http","method":"POST","path":"/tenant/quickbooks/start","headers":[]})
    with pytest.raises(HTTPException) as exc:
        q.tenant_quickbooks_start(req)
    assert exc.value.status_code == 403
    assert not (cfg.private_dir / "qbo_oauth_states").exists()


def test_tenant_shopify_proof_start_rejects_unverified_user(monkeypatch):
    from fastapi import HTTPException
    from starlette.requests import Request
    monkeypatch.setattr(q,"_tenant_shopify_context",lambda header: (_ for _ in ()).throw(HTTPException(status_code=403)))
    req=Request({"type":"http","method":"POST","path":"/tenant/shopify/ownership/start","headers":[]})
    with pytest.raises(HTTPException) as exc:
        q.tenant_shopify_ownership_start(req)
    assert exc.value.status_code == 403


def test_tenant_shopify_proof_is_user_and_store_scoped(cfg,monkeypatch):
    import uuid,json
    from starlette.requests import Request
    user=str(uuid.uuid4());store="tenant-b.myshopify.com"
    monkeypatch.setattr(q,"_tenant_shopify_context",lambda header:{"user_id":user,"store":store,"verified":False})
    monkeypatch.setattr(q,"load_saved_setup",lambda:cfg)
    monkeypatch.setattr("shopify_read._tenant_setup_path",lambda user_id,shop:cfg.private_dir / "fake.json")
    q._secure_dir(cfg)
    req=Request({"type":"http","method":"POST","path":"/tenant/shopify/ownership/start","headers":[]})
    result=q.tenant_shopify_ownership_start(req)
    assert result["store"]==store and len(result["challenge"])>=24
    path=q._tenant_proof_path(cfg,user,store)
    proof=json.loads(path.read_text())
    assert result["challenge"] not in path.read_text()
    assert proof["user_id"]==user and proof["store"]==store


def test_finance_access_check_uses_authenticated_tenant_and_keeps_finance_closed(monkeypatch):
    from starlette.requests import Request
    from fastapi import HTTPException
    import uuid
    user=str(uuid.uuid4())
    req=Request({"type":"http","method":"GET","path":"/tenant/finance/access-check",
                 "headers":[(b"authorization",b"Bearer valid")]})
    monkeypatch.setattr(q,"_authorized_tenant_connection",lambda header:{"user_id":user,"store":"tenant-b.myshopify.com","realm":"12345"} if header=="Bearer valid" else (_ for _ in ()).throw(HTTPException(403)))
    result=q.tenant_finance_access_check(req)
    assert result=={"authenticated_tenant":True,"shop_domain":"tenant-b.myshopify.com","qbo_realm_id":"12345","financial_access_enabled":False,"invoice_count_access_enabled":False}
    assert not any("token" in k for k in result)
    bad=Request({"type":"http","method":"GET","path":"/tenant/finance/access-check","headers":[]})
    with pytest.raises(HTTPException) as exc:q.tenant_finance_access_check(bad)
    assert exc.value.status_code==403


def test_tenant_refresh_isolated_from_pilot(cfg,monkeypatch):
    import uuid,time
    from dataclasses import replace
    user=str(uuid.uuid4());other=str(uuid.uuid4())
    tenant=replace(cfg,expected_realm="987654321")
    q.save_tenant_tokens(tenant,{"access_token":"OLD","refresh_token":"OLD_REFRESH","expires_in":0},user_id=user)
    monkeypatch.setattr(q,"_exchange",lambda config,payload:{"access_token":"NEW","refresh_token":"ROTATED","expires_in":3600})
    token,realm=q.get_tenant_access_token(tenant,user_id=user)
    assert (token,realm)==("NEW","987654321")
    assert q.load_tenant_tokens(tenant,user_id=user)["refresh_token"]=="ROTATED"
    with pytest.raises(ValueError):q.get_tenant_access_token(tenant,user_id=other)
    assert not (cfg.private_dir / "qbo_tokens.enc").exists()


def test_tenant_invoice_count_never_accepts_other_realm(cfg,monkeypatch):
    import uuid
    from dataclasses import replace
    user=str(uuid.uuid4());other=str(uuid.uuid4())
    tenant=replace(cfg,expected_realm="987654321")
    q.save_tenant_tokens(tenant,{"access_token":"B_ONLY","refresh_token":"R_B","expires_in":3600},user_id=user)
    urls=[]
    def fake_get(url,*,params,headers,timeout):
        urls.append(url)
        assert headers["Authorization"]=="Bearer B_ONLY"
        return FakeResponse({"QueryResponse":{"totalCount":36}})
    monkeypatch.setattr(q.requests,"get",fake_get)
    assert q.read_tenant_invoice_count(tenant,user_id=user)==36
    assert urls==[q.SANDBOX_API+"/v3/company/987654321/query"]
    with pytest.raises(ValueError):q.read_tenant_invoice_count(tenant,user_id=other)
    assert len(urls)==1


def test_finance_invoice_route_cross_tenant_denied_before_qbo(monkeypatch):
    from starlette.requests import Request
    monkeypatch.setattr(q,"_authorized_tenant_connection",lambda h:{"user_id":"a","realm":"111","store":"a.myshopify.com"})
    monkeypatch.setattr(q,"read_tenant_invoice_count",lambda *a,**kw: (_ for _ in ()).throw(AssertionError("QBO must not be called")))
    req=Request({"type":"http","method":"GET","path":"/tenant/finance/invoice-count","headers":[]})
    with pytest.raises(q.HTTPException) as e:q.tenant_finance_invoice_count(req,realm="222")
    assert e.value.status_code==403


def test_tenant_budget_shared_across_instances_and_independent_realms(cfg, monkeypatch):
    from dataclasses import replace
    clock = [1000.0]
    monkeypatch.setattr(q.time, 'time', lambda: clock[0])
    q._tenant_count_budget(cfg)
    with pytest.raises(q.HTTPException) as exc:
        q._tenant_count_budget(replace(cfg))
    assert exc.value.status_code == 429
    q._tenant_count_budget(replace(cfg, expected_realm='222'))
    for i in range(1, 60):
        clock[0] = 1000 + i * .5
        q._tenant_count_budget(cfg)
    clock[0] = 1030.0
    with pytest.raises(q.HTTPException) as exc:
        q._tenant_count_budget(cfg)
    assert exc.value.headers['Retry-After'] == '30'
    clock[0] = 1060.0
    q._tenant_count_budget(cfg)


@pytest.mark.parametrize('status,cooldown', [(429,60), (503,5)])
def test_provider_backoff_survives_new_caller_without_retry(cfg, monkeypatch, status, cooldown):
    user = '11111111-1111-4111-8111-111111111111'
    q.save_tenant_tokens(cfg, {'access_token':'fake', 'refresh_token':'fake', 'expires_in':3600}, user_id=user)
    calls = []
    monkeypatch.setattr(q.requests, 'get', lambda *a, **kw: calls.append(1) or FakeResponse({},status))
    with pytest.raises(q.HTTPException) as exc:
        q.read_tenant_invoice_count(cfg, user_id=user)
    assert exc.value.status_code == status
    assert exc.value.headers['Retry-After'] == str(cooldown)
    with pytest.raises(q.HTTPException) as exc:
        q.read_tenant_invoice_count(cfg, user_id=user)
    assert exc.value.status_code == 429
    assert calls == [1]


@pytest.mark.parametrize('failure,expected,cooldown', [(429, 429, 60), (503, 503, 5),
                                                      ('timeout', 503, 5)])
def test_expired_token_refresh_failure_shares_count_cooldown(cfg, monkeypatch, failure, expected, cooldown):
    from dataclasses import replace
    user = '11111111-1111-4111-8111-111111111111'
    clock = [1000.0]
    monkeypatch.setattr(q.time, 'time', lambda: clock[0])
    q.save_tenant_tokens(cfg, {'access_token': 'synthetic', 'refresh_token': 'synthetic',
                             'expires_in': -1}, user_id=user)
    token_path = q._tenant_token_path(cfg, user_id=user)
    before = token_path.read_bytes()
    calls = []
    def refresh(*args, **kwargs):
        calls.append(1)
        if failure == 'timeout':
            raise q.requests.Timeout('synthetic timeout')
        return FakeResponse({}, failure)
    monkeypatch.setattr(q.requests, 'post', refresh)
    monkeypatch.setattr(q.requests, 'get', lambda *args, **kwargs: pytest.fail('No query after failed refresh'))
    with pytest.raises(q.HTTPException) as exc:
        q.read_tenant_invoice_count(cfg, user_id=user)
    assert exc.value.status_code == expected
    assert exc.value.headers['Retry-After'] == str(cooldown)
    # Beyond the ordinary half-second gate, a new caller still must not refresh.
    clock[0] += 1
    with pytest.raises(q.HTTPException) as exc:
        q.read_tenant_invoice_count(replace(cfg), user_id=user)
    assert exc.value.status_code == 429
    assert exc.value.headers['Retry-After'] == str(cooldown - 1)
    assert calls == [1] and token_path.read_bytes() == before
    # The provider can be attempted again only after the declared cooldown.
    clock[0] = 1000 + cooldown
    with pytest.raises(q.HTTPException):
        q.read_tenant_invoice_count(cfg, user_id=user)
    assert calls == [1, 1] and token_path.read_bytes() == before


def test_finance_invoice_route_owner_read_only(monkeypatch):
    from starlette.requests import Request
    monkeypatch.setenv('VERICON_PILOT_INVOICE_COUNT_REALMS', '111')
    monkeypatch.setattr(q,"_authorized_tenant_connection",lambda h:{"user_id":"a","realm":"111","store":"a.myshopify.com"})
    monkeypatch.setattr(q,"load_saved_setup",lambda: q.Config("id","secret","https://app.vericon.site/oauth/quickbooks/callback",q.BASE_DIR,"111"))
    monkeypatch.setattr(q,"read_tenant_invoice_count",lambda config,*,user_id: 31 if config.expected_realm=="111" and user_id=="a" else 0)
    req=Request({"type":"http","method":"GET","path":"/tenant/finance/invoice-count","headers":[]})
    assert q.tenant_finance_invoice_count(req,realm="111")=={"invoice_count":31,"realm":"111","read_only":True}


@pytest.mark.parametrize('financial,pilot,allowed', [
    (False, '', False), (None, '', False), ('true', '', False),
    (True, '', True), (False, '111', True), (False, '222', False)])
def test_invoice_count_requires_explicit_financial_or_pilot_grant(monkeypatch, financial, pilot, allowed):
    from starlette.requests import Request
    monkeypatch.setenv('VERICON_PILOT_INVOICE_COUNT_REALMS', pilot)
    monkeypatch.setattr(q, '_authorized_tenant_connection', lambda h: {
        'user_id': 'a', 'realm': '111', 'store': 'a.myshopify.com',
        'financial_access_enabled': financial})
    monkeypatch.setattr(q, 'load_saved_setup', lambda: q.Config('id','fake','',q.BASE_DIR,'111'))
    calls = []
    monkeypatch.setattr(q, 'read_tenant_invoice_count', lambda *a, **kw: calls.append('read') or 31)
    req = Request({'type':'http', 'method':'GET', 'path':'/tenant/finance/invoice-count','headers':[]})
    if allowed:
        assert q.tenant_finance_invoice_count(req, realm='111')['invoice_count'] == 31
    else:
        with pytest.raises(q.HTTPException) as exc:
            q.tenant_finance_invoice_count(req, realm='111')
        assert exc.value.status_code == 403
        assert calls == []


def test_tenant_disconnect_revoke_then_delete_only_owner(cfg,monkeypatch):
    import uuid
    from dataclasses import replace
    user=str(uuid.uuid4());other=str(uuid.uuid4())
    tenant=replace(cfg,expected_realm="987654321")
    other_tenant=replace(cfg,expected_realm="111111111")
    q.save_tenant_tokens(tenant,{"access_token":"A","refresh_token":"RA","expires_in":3600},user_id=user)
    q.save_tenant_tokens(other_tenant,{"access_token":"B","refresh_token":"RB","expires_in":3600},user_id=other)
    calls=[]
    def fake_post(url,*,auth,data,headers,timeout):
        assert url=="https://developer.api.intuit.com/v2/oauth2/tokens/revoke"
        calls.append(data["token"])
        return FakeResponse({},status=200)
    monkeypatch.setattr(q.requests,"post",fake_post)
    q.disconnect_tenant_quickbooks(tenant,user_id=user)
    assert calls==["RA"]
    with pytest.raises(ValueError):q.load_tenant_tokens(tenant,user_id=user)
    assert q.load_tenant_tokens(other_tenant,user_id=other)["access_token"]=="B"
    q.save_tenant_tokens(tenant,{"access_token":"A2","refresh_token":"RA2","expires_in":3600},user_id=user)
    assert q.load_tenant_tokens(tenant,user_id=user)["access_token"]=="A2"


def test_tenant_disconnect_failed_revoke_preserves_token(cfg,monkeypatch):
    import uuid
    from dataclasses import replace
    user=str(uuid.uuid4());tenant=replace(cfg,expected_realm="987654321")
    q.save_tenant_tokens(tenant,{"access_token":"A","refresh_token":"RA","expires_in":3600},user_id=user)
    monkeypatch.setattr(q.requests,"post",lambda *a,**kw:FakeResponse({},status=500))
    with pytest.raises(ValueError,match="unconfirmed"):
        q.disconnect_tenant_quickbooks(tenant,user_id=user)
    assert q.load_tenant_tokens(tenant,user_id=user)["access_token"]=="A"


def test_disconnect_reconnect_flow_same_user_and_realm(cfg,monkeypatch):
    import uuid
    from dataclasses import replace
    user=str(uuid.uuid4());other=str(uuid.uuid4())
    tenant=replace(cfg,expected_realm="987654321")
    q.save_tenant_tokens(tenant,{"access_token":"OLD","refresh_token":"OLD_REFRESH","expires_in":3600},user_id=user)
    monkeypatch.setattr(q.requests,"post",lambda *a,**kw:FakeResponse({},status=200))
    q.disconnect_tenant_quickbooks(tenant,user_id=user)
    with pytest.raises(ValueError):q.get_tenant_access_token(tenant,user_id=user)
    monkeypatch.setattr(q,"_exchange",lambda *a,**kw:{"access_token":"RECONNECTED","refresh_token":"ROTATED","expires_in":3600})
    url=q.create_authorization_url(tenant,user_id=user)
    state=parse_qs(urlparse(url).query)["state"][0]
    q.complete_authorization(tenant,state=state,code="valid",realm="987654321",user_id=user)
    assert q.get_tenant_access_token(tenant,user_id=user)==("RECONNECTED","987654321")


def test_second_customer_cannot_bind_same_qbo_company(cfg):
    import uuid
    from dataclasses import replace
    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    q.save_tenant_tokens(cfg, {"access_token":"A","refresh_token":"RA","expires_in":3600}, user_id=first)
    with pytest.raises(ValueError, match="already linked"):
        q.save_tenant_tokens(cfg, {"access_token":"B","refresh_token":"RB","expires_in":3600}, user_id=second)
    assert q.load_tenant_tokens(cfg, user_id=first)["access_token"] == "A"
    with pytest.raises(ValueError, match="not available"):
        q.load_tenant_tokens(cfg, user_id=second)
    other_company = replace(cfg, expected_realm="987654321")
    q.save_tenant_tokens(other_company, {"access_token":"B","refresh_token":"RB","expires_in":3600}, user_id=second)
    assert q.load_tenant_tokens(other_company, user_id=second)["access_token"] == "B"
    q.save_tenant_tokens(cfg, {"access_token":"A2","refresh_token":"RA2","expires_in":3600}, user_id=first)
    assert q.load_tenant_tokens(cfg, user_id=first)["access_token"] == "A2"


def test_check_state_rejects_symlinked_and_unsafe_state_file(cfg):
    import os
    import uuid
    owner = str(uuid.uuid4())
    state = parse_qs(urlparse(q.create_authorization_url(cfg, user_id=owner)).query)["state"][0]
    path = q._oauth_state_file(cfg, state, user_id=owner)
    target = cfg.private_dir / "outside.json"
    os.replace(path, target)
    os.symlink(target, path)
    with pytest.raises(ValueError, match="Missing or invalid"):
        q._callback_state_record(cfg, state)
    with pytest.raises(ValueError, match="Missing or invalid"):
        q.check_state(cfg, state, user_id=owner)
    path.unlink()
    os.replace(target, path)
    os.chmod(path, 0o644)
    with pytest.raises(ValueError, match="Missing or invalid"):
        q.check_state(cfg, state, user_id=owner)
    os.chmod(path, 0o600)
    q.check_state(cfg, state, user_id=owner)


def test_shopify_owner_requires_full_company_pair(cfg, monkeypatch):
    import uuid
    from fastapi import HTTPException
    owner = str(uuid.uuid4())
    monkeypatch.setattr(q, "_verified_customer_subject", lambda header: owner)
    monkeypatch.setattr(q, "load_saved_setup", lambda: cfg)
    monkeypatch.setenv("VERICON_SUPABASE_PUBLISHABLE_KEY", "test-public-key")
    row = {"user_id": owner, "shop_domain": "hudys3-p0.myshopify.com", "connection_status": "pilot_linked",
           "qbo_realm_id": cfg.expected_realm}
    monkeypatch.setattr(q.requests, "get", lambda url, **kw: FakeResponse([dict(row)]))
    assert q._shopify_owner("Bearer valid") == owner
    row["qbo_realm_id"] = "99999"
    with pytest.raises(HTTPException) as err:
        q._shopify_owner("Bearer valid")
    assert err.value.status_code == 403
    row["qbo_realm_id"] = cfg.expected_realm
    row["shop_domain"] = "tenant-b.myshopify.com"
    with pytest.raises(HTTPException) as err:
        q._shopify_owner("Bearer valid")
    assert err.value.status_code == 403

@pytest.mark.parametrize("route,method,handler", [
    ("/tenant/finance/access-check", "GET", q.tenant_finance_access_check),
    ("/tenant/shopify/ownership/start", "POST", q.tenant_shopify_ownership_start),
    ("/tenant/shopify/ownership/verify", "POST", q.tenant_shopify_ownership_verify),
    ("/tenant/quickbooks/start", "POST", q.tenant_quickbooks_start),
    ("/tenant/quickbooks/disconnect", "POST", q.tenant_quickbooks_disconnect),
])
def test_tenant_routes_reject_unauthenticated_request(route, method, handler):
    from starlette.requests import Request
    from fastapi import HTTPException
    req = Request({"type": "http", "method": method, "path": route, "headers": []})
    with pytest.raises(HTTPException) as exc:
        handler(req)
    assert exc.value.status_code == 401


def test_two_tenant_mapping_rejects_cross_owned_rows(monkeypatch):
    import uuid
    from fastapi import HTTPException
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    records = {
        a: {"user_id": a, "shop_domain": "tenant-a.myshopify.com",
            "qbo_realm_id": "111", "connection_status": "pilot_linked", "ownership_verified": True},
        b: {"user_id": b, "shop_domain": "tenant-b.myshopify.com",
            "qbo_realm_id": "222", "connection_status": "pilot_linked", "ownership_verified": True},
    }
    monkeypatch.setenv("VERICON_SUPABASE_PUBLISHABLE_KEY", "test-public")
    monkeypatch.setattr(q, "_verified_customer_subject", lambda header: a if header == "Bearer A" else b)
    def fake_get(url, *, params, headers, timeout):
        owner = a if headers["Authorization"] == "Bearer A" else b
        requested = params["user_id"][3:]
        return FakeResponse([records[requested]] if requested == owner else [])
    monkeypatch.setattr(q.requests, "get", fake_get)
    for header, own, other in [("Bearer A", a, b), ("Bearer B", b, a)]:
        result = q._authorized_tenant_connection(header)
        assert result["user_id"] == own
        assert result["realm"] == records[own]["qbo_realm_id"]
        with pytest.raises(HTTPException) as exc:
            q.tenant_finance_invoice_count(
                __import__("starlette.requests", fromlist=["Request"]).Request(
                    {"type": "http", "method": "GET", "path": "/tenant/finance/invoice-count",
                     "headers": [(b"authorization", header.encode())]}),
                realm=records[other]["qbo_realm_id"])
        assert exc.value.status_code == 403

@pytest.mark.parametrize('route,handler', [
    ('/tenant/quickbooks/disconnect', q.tenant_quickbooks_disconnect),
    ('/tenant/quickbooks/start', q.tenant_quickbooks_start),
    ('/tenant/shopify/ownership/start', q.tenant_shopify_ownership_start),
    ('/tenant/shopify/ownership/verify', q.tenant_shopify_ownership_verify),
])
def test_mutating_tenant_routes_fail_closed_on_cross_tenant_mapping(monkeypatch, route, handler):
    """Denied tenant mapping must not reach OAuth, token, or proof side effects."""
    from fastapi import HTTPException
    from starlette.requests import Request
    calls = []
    def denied(_header):
        raise HTTPException(status_code=403, detail='Cross-tenant denied')
    monkeypatch.setattr(q, '_authorized_tenant_connection', denied)
    monkeypatch.setattr(q, '_tenant_shopify_context', denied)
    monkeypatch.setattr(q, 'disconnect_tenant_quickbooks', lambda *a, **k: calls.append('revoke'))
    monkeypatch.setattr(q, 'create_authorization_url', lambda *a, **k: calls.append('oauth'))
    monkeypatch.setattr(q, '_atomic_write', lambda *a, **k: calls.append('write'))
    req = Request({'type': 'http', 'method': 'POST', 'path': route,
                   'headers': [(b'authorization', b'Bearer cross-tenant')]})
    with pytest.raises(HTTPException) as exc:
        handler(req)
    assert exc.value.status_code == 403
    assert calls == []


@pytest.mark.parametrize('value', ['*', '111,*', '111,', '111 222'])
def test_malformed_pilot_grant_fails_closed_before_startup(monkeypatch, value):
    monkeypatch.setenv('VERICON_PILOT_INVOICE_COUNT_REALMS', value)
    with pytest.raises(q.HTTPException) as exc:
        q.runtime_preflight()
    assert exc.value.status_code == 503


# Stage 4 HTTP contract harness: identity alone is mocked, never a fabricated JWT.
# RLS requests, provider I/O and private storage are isolated from the live service.
STAGE4_ROUTES = [
    ('GET', '/auth/me'), ('GET', '/health'),
    ('GET', '/tenant/finance/access-check'), ('GET', '/tenant/finance/invoice-count'),
    ('POST', '/shopify/ownership/start'), ('POST', '/shopify/ownership/verify'),
    ('POST', '/tenant/shopify/ownership/start'), ('POST', '/tenant/shopify/ownership/verify'),
    ('POST', '/oauth/quickbooks/start'), ('POST', '/tenant/quickbooks/disconnect'),
    ('POST', '/tenant/quickbooks/start'), ('GET', '/oauth/quickbooks/callback'),
]
STAGE4_OWNED_ROUTES = [(method, path) for method, path in STAGE4_ROUTES
                       if path not in ('/health', '/auth/me', '/oauth/quickbooks/callback')]


@pytest.fixture
def stage4_http(cfg, monkeypatch):
    import copy
    import shopify_read as s
    import socket
    import threading
    import urllib.error
    import urllib.request
    import uvicorn
    from urllib.parse import urlencode
    from types import SimpleNamespace
    cfg = q.replace(cfg, redirect_uri='https://app.vericon.site/oauth/quickbooks/callback')
    q._secure_dir(cfg)
    monkeypatch.setattr(q, 'load_saved_setup', lambda: cfg)
    monkeypatch.setattr(s, 'PRIVATE', cfg.private_dir)
    monkeypatch.setattr(s, 'load_setup', lambda: s.Config('fake', 'fake', s.STORE))
    monkeypatch.setenv('VERICON_SUPABASE_PUBLISHABLE_KEY', 'test-public')
    monkeypatch.delenv('VERICON_PILOT_INVOICE_COUNT_REALMS', raising=False)
    ids = {'A': '11111111-1111-4111-8111-111111111111',
           'B': '22222222-2222-4222-8222-222222222222'}
    rows = {actor: {'user_id': uid, 'shop_domain': f'tenant-{actor.lower()}.myshopify.com',
                   'qbo_realm_id': '12345' if actor == 'A' else '67890',
                   'connection_status': 'pilot_linked', 'ownership_verified': True,
                   'financial_access_enabled': True} for actor, uid in ids.items()}
    for actor, row in rows.items():
        q.save_tenant_tokens(q.replace(cfg, expected_realm=row['qbo_realm_id']),
            {'access_token': 'fake-' + actor, 'refresh_token': 'fake-refresh-' + actor},
            user_id=row['user_id'])
        s.save_tenant_setup(row['user_id'], row['shop_domain'], 'fake', 'fake')
    state = {'cfg': cfg, 'ids': ids, 'rows': rows, 'calls': [], 'rls_fault': None,
             'proof_values': {}, 'revoke_status': 200}
    def identity(header):
        if header not in ('Bearer fixture-A', 'Bearer fixture-B'):
            raise q.HTTPException(401, 'Fixture authentication required')
        return ids[header[-1]]
    monkeypatch.setattr(q, '_verified_customer_subject', identity)
    def get(url, **kw):
        if url.endswith('/vericon_pilot_connections'):
            actor = kw['headers']['Authorization'][-1]
            assert kw['params']['user_id'] == 'eq.' + ids[actor]
            fault = state['rls_fault']
            if fault == 'timeout':
                raise q.requests.Timeout('synthetic')
            if fault == 'malformed':
                return FakeResponse([None])
            row = copy.deepcopy(rows[actor])
            if fault == 'cross':
                row['user_id'] = ids['B' if actor == 'A' else 'A']
            elif fault == 'missing_owner':
                row.pop('user_id')
            elif fault == 'store':
                row['shop_domain'] = 'invalid.example'
            elif fault == 'realm':
                row['qbo_realm_id'] = 'invalid'
            elif fault == 'unlinked':
                row['connection_status'] = 'disconnected'
            return FakeResponse([row])
        assert url.startswith(q.SANDBOX_API) and url.endswith('/query')
        state['calls'].append(('query', url))
        return FakeResponse({'QueryResponse': {'totalCount': 7}})
    def post(url, **kw):
        state['calls'].append(('post', url))
        if url.endswith('/tokens/revoke'):
            return FakeResponse({}, state['revoke_status'])
        if url == q.TOKEN_URL:
            return FakeResponse({'access_token': 'new-fake', 'refresh_token': 'new-fake-refresh'})
        store = urlparse(url).hostname
        if url.endswith('/access_token'):
            return FakeResponse({'access_token': 'fake', 'scope': ','.join(s.REQUIRED_SCOPES)})
        assert url.endswith('/graphql.json') and kw['json']['query'].startswith('query')
        return FakeResponse({'data': {'shop': {'myshopifyDomain': store,
            'metafield': {'value': state['proof_values'].get(store)}}}})
    monkeypatch.setattr(q.requests, 'get', get)
    monkeypatch.setattr(q.requests, 'post', post)
    monkeypatch.setattr(q.requests.sessions.Session, 'request',
                        lambda *a, **kw: pytest.fail('unexpected external network'))
    state['snapshot'] = lambda: {str(p.relative_to(cfg.private_dir)): p.read_bytes()
                               for p in cfg.private_dir.rglob('*') if p.is_file()}
    # Use the installed server and stdlib client: real HTTP, no new dependency.
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    server = uvicorn.Server(uvicorn.Config(q.app, log_level='critical', access_log=False))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(.01)
    class Client:
        def request(self, method, path, *, params=None, headers=None, json=None):
            url = f'http://127.0.0.1:{sock.getsockname()[1]}' + path
            if params:
                url += '?' + urlencode(params)
            data = __import__('json').dumps(json).encode() if json is not None else None
            request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
            try:
                response = urllib.request.urlopen(request, timeout=5)
            except urllib.error.HTTPError as exc:
                response = exc
            with response:
                body = response.read().decode()
                return SimpleNamespace(status_code=response.status, text=body, headers=response.headers,
                                       json=lambda: __import__('json').loads(body))
    try:
        assert server.started, 'Isolated HTTP server did not start'
        state['client'] = Client()
        yield state
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
        assert not thread.is_alive()


def test_stage4_route_inventory_is_exhaustive():
    assert {(method, r.path) for r in q.app.routes for method in r.methods} == set(STAGE4_ROUTES)


@pytest.mark.parametrize('actor', ['A', 'B'])
@pytest.mark.parametrize('method,path', STAGE4_OWNED_ROUTES)
@pytest.mark.parametrize('fault', ['cross', 'missing_owner', 'malformed', 'timeout', 'unlinked'])
def test_stage4_http_denials_have_no_side_effects(stage4_http, actor, method, path, fault):
    import shopify_read as s
    h = stage4_http
    if not path.startswith('/tenant/'):
        h['rows'][actor].update(shop_domain=s.STORE, qbo_realm_id=h['cfg'].expected_realm)
    h['rls_fault'] = fault
    before = h['snapshot']()
    r = h['client'].request(method, path, params={'realm': h['rows'][actor]['qbo_realm_id']},
                            headers={'Authorization': 'Bearer fixture-' + actor})
    assert r.status_code == 403
    assert h['calls'] == [] and h['snapshot']() == before


@pytest.mark.parametrize('method,path', STAGE4_ROUTES)
def test_stage4_http_anonymous_has_no_side_effects(stage4_http, method, path):
    h = stage4_http
    before = h['snapshot']()
    r = h['client'].request(method, path, params={'realm': '12345'})
    expected = 200 if path == '/health' else 400 if path.endswith('/callback') else 401
    assert r.status_code == expected
    assert h['calls'] == [] and h['snapshot']() == before


@pytest.mark.parametrize('actor', ['A', 'B'])
def test_stage4_http_own_cross_and_reconnect(stage4_http, actor):
    h = stage4_http
    other = 'B' if actor == 'A' else 'A'
    row, peer = h['rows'][actor], h['rows'][other]
    cfg = q.replace(h['cfg'], expected_realm=row['qbo_realm_id'])
    peer_path = q._tenant_token_path(q.replace(cfg, expected_realm=peer['qbo_realm_id']), user_id=peer['user_id'])
    peer_before = peer_path.read_bytes()
    headers = {'Authorization': 'Bearer fixture-' + actor}
    def call(method, path, **kwargs):
        return h['client'].request(method, path, headers=headers, **kwargs)
    # Caller-scoped routes have no target parameter; extra input cannot select a peer.
    injected = {'user_id': peer['user_id'], 'store': peer['shop_domain'], 'realm': peer['qbo_realm_id']}
    assert call('GET', '/auth/me', params=injected).json()['subject'] == row['user_id']
    access = call('GET', '/tenant/finance/access-check', params=injected)
    assert access.status_code == 200 and access.json()['qbo_realm_id'] == row['qbo_realm_id']
    before = h['snapshot']()
    assert call('GET', '/tenant/finance/invoice-count', params={'realm': peer['qbo_realm_id']}).status_code == 403
    assert h['calls'] == [] and h['snapshot']() == before
    count = call('GET', '/tenant/finance/invoice-count', params={'realm': row['qbo_realm_id']})
    assert count.status_code == 200 and count.json() == {'invoice_count': 7, 'realm': row['qbo_realm_id'], 'read_only': True}
    assert f"/company/{row['qbo_realm_id']}/query" in h['calls'][0][1]
    started = call('POST', '/tenant/quickbooks/start', params=injected, json=injected)
    assert started.status_code == 200
    state = parse_qs(urlparse(started.json()['authorization_url']).query)['state'][0]
    record = q._callback_state_record(cfg, state)
    assert record['user_id'] == row['user_id'] and record['expected_realm'] == row['qbo_realm_id']
    before = h['snapshot'](); h['calls'].clear()
    callback = {'state': state, 'code': 'fake-code', 'realmId': peer['qbo_realm_id']}
    assert call('GET', '/oauth/quickbooks/callback', params=callback).status_code == 400
    assert h['calls'] == [] and h['snapshot']() == before
    callback['realmId'] = row['qbo_realm_id']
    assert call('GET', '/oauth/quickbooks/callback', params=callback).status_code == 200
    assert len(h['calls']) == 1 and peer_path.read_bytes() == peer_before
    assert call('GET', '/oauth/quickbooks/callback', params=callback).status_code == 400
    assert len(h['calls']) == 1
    # Fake provider only. Unconfirmed revoke keeps the credential; confirmed revoke
    # deletes only the authenticated caller. Reconnect creates a fresh bound state.
    h['revoke_status'] = 503
    own_path = q._tenant_token_path(cfg, user_id=row['user_id'])
    own_before = own_path.read_bytes()
    assert call('POST', '/tenant/quickbooks/disconnect').status_code == 503
    assert own_path.read_bytes() == own_before
    h['revoke_status'] = 200
    assert call('POST', '/tenant/quickbooks/disconnect', json=injected).status_code == 200
    assert not own_path.exists() and peer_path.read_bytes() == peer_before
    h['calls'].clear()
    assert call('POST', '/tenant/quickbooks/disconnect').status_code == 503
    assert h['calls'] == []  # repeated disconnect cannot repeat provider revoke
    assert call('POST', '/tenant/quickbooks/start').status_code == 200
    assert peer_path.read_bytes() == peer_before


@pytest.mark.parametrize('actor', ['A', 'B'])
@pytest.mark.parametrize('fault', ['user', 'store', 'expired', 'wrong_code', 'none'])
def test_stage4_http_tenant_proof_binding(stage4_http, actor, fault):
    h = stage4_http
    row = h['rows'][actor]; other = h['rows']['B' if actor == 'A' else 'A']
    row['ownership_verified'] = False
    headers = {'Authorization': 'Bearer fixture-' + actor}
    response = h['client'].request('POST', '/tenant/shopify/ownership/start', headers=headers,
                                  json={'user_id': other['user_id'], 'store': other['shop_domain']})
    assert response.status_code == 200 and response.json()['store'] == row['shop_domain']
    path = q._tenant_proof_path(h['cfg'], row['user_id'], row['shop_domain'])
    proof = json.loads(path.read_text())
    assert proof['user_id'] == row['user_id'] and proof['store'] == row['shop_domain']
    h['proof_values'][row['shop_domain']] = response.json()['challenge']
    if fault == 'user': proof['user_id'] = other['user_id']
    if fault == 'store': proof['store'] = other['shop_domain']
    if fault == 'expired': proof['expires_at'] = 0
    if fault == 'wrong_code': h['proof_values'][row['shop_domain']] = 'wrong-code'
    q._atomic_write(path, json.dumps(proof).encode())
    before = h['snapshot']()
    result = h['client'].request('POST', '/tenant/shopify/ownership/verify', headers=headers)
    assert result.status_code == (200 if fault == 'none' else 400)
    if fault != 'none':
        assert h['snapshot']() == before
        if fault != 'wrong_code': assert h['calls'] == []
    else:
        assert not path.exists() and path.with_suffix('.verified').is_file()
        assert result.json()['financial_access_enabled'] is False
        calls = len(h['calls'])
        assert h['client'].request('POST', '/tenant/shopify/ownership/verify', headers=headers).status_code == 400
        assert len(h['calls']) == calls


def test_stage4_http_pilot_routes_only_accept_pilot_owner(stage4_http):
    import shopify_read as s
    h = stage4_http
    h['rows']['A']['shop_domain'] = s.STORE
    a, b = {'Authorization': 'Bearer fixture-A'}, {'Authorization': 'Bearer fixture-B'}
    paths = ['/oauth/quickbooks/start', '/shopify/ownership/start', '/shopify/ownership/verify']
    before = h['snapshot']()
    for path in paths:
        assert h['client'].request('POST', path, headers=b).status_code == 403
    assert h['snapshot']() == before and h['calls'] == []
    start = h['client'].request('POST', paths[0], headers=a)
    assert start.status_code == 200
    state = parse_qs(urlparse(start.json()['authorization_url']).query)['state'][0]
    assert q._callback_state_record(h['cfg'], state)['user_id'] == h['ids']['A']
    proof = h['client'].request('POST', paths[1], headers=a)
    assert proof.status_code == 200
    h['proof_values'][s.STORE] = proof.json()['challenge']
    verified = h['client'].request('POST', paths[2], headers=a)
    assert verified.status_code == 200 and verified.json()['financial_access_enabled'] is False
    assert h['client'].request('POST', paths[2], headers=a).status_code == 400


@pytest.mark.parametrize('actor', ['A', 'B'])
@pytest.mark.parametrize('field', ['store', 'realm'])
def test_stage4_http_invalid_tenant_binding(stage4_http, actor, field):
    h = stage4_http; h['rls_fault'] = field
    before = h['snapshot']()
    for method, path in STAGE4_OWNED_ROUTES:
        # Store-proof routes intentionally do not authorize QBO access.
        if field == 'realm' and path.startswith('/tenant/shopify/'):
            continue
        r = h['client'].request(method, path, params={'realm': h['rows'][actor]['qbo_realm_id']},
                                headers={'Authorization': 'Bearer fixture-' + actor})
        assert r.status_code == 403, path
    assert h['calls'] == [] and h['snapshot']() == before
