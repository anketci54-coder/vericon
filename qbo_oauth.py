"""VERICON QuickBooks Online SANDBOX-only OAuth + read-only Item client.

This module is NOT a running service until an operator deliberately configures
an HTTPS callback with access logs disabled and starts uvicorn locally.
"""
from __future__ import annotations

import argparse
import json
import hashlib
import logging
import fcntl
import os
import re
import secrets
import tempfile
import time
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse

import requests
import jwt
from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse

AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
SANDBOX_API = "https://sandbox-quickbooks.api.intuit.com"
SCOPE = "com.intuit.quickbooks.accounting"
BASE_DIR = Path(__file__).resolve().parent
SUPABASE_ISSUER = "https://ftzxcvrrgvlhlxufxccz.supabase.co/auth/v1"
SUPABASE_JWKS = jwt.PyJWKClient(SUPABASE_ISSUER + "/.well-known/jwks.json", timeout=4)
app = FastAPI(title="VERICON QBO sandbox connector", docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def reject_unauthenticated_data_routes(request, call_next):
    # Only a token-validation endpoint is allowed; customer data stays closed.
    if request.url.path not in ("/health", "/oauth/quickbooks/callback", "/oauth/quickbooks/start", "/auth/me", "/shopify/ownership/start", "/shopify/ownership/verify", "/tenant/quickbooks/start", "/tenant/shopify/ownership/start", "/tenant/shopify/ownership/verify", "/tenant/finance/access-check", "/tenant/finance/invoice-count", "/tenant/quickbooks/disconnect"):
        return PlainTextResponse("Forbidden", status_code=403)
    return await call_next(request)


@dataclass(frozen=True)
class Config:
    client_id: str
    client_secret: str
    redirect_uri: str
    private_dir: Path
    expected_realm: str | None

    @classmethod
    def from_env(cls) -> "Config":
        keys = ("VERICON_QBO_CLIENT_ID", "VERICON_QBO_CLIENT_SECRET", "VERICON_QBO_REDIRECT_URI")
        missing = [key for key in keys if not os.environ.get(key)]
        if missing:
            raise ValueError("Missing private environment configuration: " + ", ".join(missing))
        redirect_uri = os.environ[keys[2]]
        parsed = urlparse(redirect_uri)
        if parsed.scheme != "https" and not (
            parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1")
        ):
            raise ValueError("OAuth redirect must be HTTPS (or sandbox loopback on localhost)")
        if not parsed.hostname or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError("Invalid OAuth redirect host or parameters")
        if parsed.path != "/oauth/quickbooks/callback":
            raise ValueError("OAuth redirect path must be /oauth/quickbooks/callback")
        expected_realm = os.environ.get("VERICON_QBO_EXPECTED_REALM", "")
        if not expected_realm.isdigit():
            raise ValueError("Expected QuickBooks company ID is required")
        return cls(
            client_id=os.environ[keys[0]],
            client_secret=os.environ[keys[1]],
            redirect_uri=redirect_uri,
            private_dir=Path(os.environ.get("VERICON_QBO_PRIVATE_DIR", str(BASE_DIR / "private"))),
            expected_realm=expected_realm,
        )


def _secure_dir(config: Config) -> None:
    config.private_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if config.private_dir.is_symlink() or config.private_dir.stat().st_mode & 0o077:
        raise PermissionError("Private directory must be non-symlink with permissions 0700")


def _atomic_write(path: Path, data: bytes) -> None:
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".vericon-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        os.chmod(path, 0o600)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _key(config: Config) -> bytes:
    _secure_dir(config)
    path = config.private_dir / "qbo.key"
    if not path.exists():
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(Fernet.generate_key())
        except FileExistsError:
            pass
    if path.stat().st_mode & 0o077:
        raise PermissionError("Encryption key file permissions must be 0600")
    return path.read_bytes()


def _state_path(config: Config) -> Path:
    return config.private_dir / "qbo_oauth_state.json"


def _oauth_state_file(config: Config, state: str, *, user_id: str | None) -> Path:
    if user_id is None:
        return _state_path(config)
    if not isinstance(state, str) or len(state) < 32 or len(state) > 128 or not re.fullmatch(r"[A-Za-z0-9_-]+", state):
        raise ValueError("Invalid OAuth state")
    folder = config.private_dir / "qbo_oauth_states"
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    if folder.is_symlink() or folder.stat().st_mode & 0o077:
        raise PermissionError("OAuth state directory unsafe")
    return folder / (hashlib.sha256(state.encode()).hexdigest() + ".json")


def _callback_state_record(config: Config, state: str) -> dict:
    path = _oauth_state_file(config, state, user_id="lookup")
    if path.is_file() and not path.is_symlink() and not path.stat().st_mode & 0o077:
        return json.loads(path.read_text())
    # Legacy CLI only; never accept legacy state on the public customer callback.
    raise ValueError("Missing or invalid OAuth state")


def create_authorization_url(config: Config, *, user_id: str | None = None) -> str:
    if user_id is not None:
        user_id = str(uuid.UUID(user_id))
    if not config.expected_realm or not str(config.expected_realm).isdigit():
        raise ValueError("Expected QuickBooks company ID is required")
    _secure_dir(config)
    state = secrets.token_urlsafe(32)
    _atomic_write(
        _oauth_state_file(config, state, user_id=user_id),
        json.dumps({"state": state, "expires_at": int(time.time()) + 600,
                    "expected_realm": config.expected_realm,
                    "client_id": config.client_id, "user_id": user_id}).encode(),
    )
    return AUTH_URL + "?" + urlencode(
        {"client_id": config.client_id,
         "response_type": "code",
         "scope": SCOPE,
         "redirect_uri": config.redirect_uri,
         "state": state}
    )


def check_state(config: Config, supplied: str, *, user_id: str | None = None) -> None:
    path = _oauth_state_file(config, supplied, user_id=user_id)
    try:
        obj = json.loads(path.read_bytes())
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        raise ValueError("Missing or invalid OAuth state") from None
    if not secrets.compare_digest(str(obj.get("state", "")), str(supplied)):
        raise ValueError("OAuth state mismatch")
    if (not config.expected_realm or
            not secrets.compare_digest(str(obj.get("expected_realm", "")), str(config.expected_realm)) or
            not secrets.compare_digest(str(obj.get("client_id", "")), str(config.client_id))):
        raise ValueError("OAuth state tenant binding mismatch")
    if user_id is not None:
        user_id = str(uuid.UUID(user_id))
    if obj.get("user_id") != user_id:
        raise ValueError("OAuth state user binding mismatch")
    path.unlink(missing_ok=True)  # prevent replay, even on failed token exchange
    if int(obj.get("expires_at", 0)) < int(time.time()):
        raise ValueError("OAuth state expired")


def _exchange(config: Config, params: dict[str, str]) -> dict:
    response = requests.post(
        TOKEN_URL,
        auth=(config.client_id, config.client_secret),
        data=params,
        headers={"Accept": "application/json"},
        timeout=20,
    )
    if response.status_code != 200:
        raise ValueError(f"Intuit token exchange refused (HTTP {response.status_code})")
    payload = response.json()
    if not payload.get("access_token") or not payload.get("refresh_token"):
        raise ValueError("Intuit response has no complete token pair")
    return payload


def _tenant_token_path(config: Config, *, user_id: str | None = None) -> Path:
    """Keep legacy pilot untouched; isolate new user/realm pairs in a private directory."""
    if user_id is None:
        return config.private_dir / "qbo_tokens.enc"
    user_id = str(uuid.UUID(user_id))
    if not config.expected_realm or not str(config.expected_realm).isdigit():
        raise ValueError("Expected QuickBooks company ID is required")
    tenant_dir = config.private_dir / "qbo_tenants"
    tenant_dir.mkdir(mode=0o700, exist_ok=True)
    if tenant_dir.is_symlink() or tenant_dir.stat().st_mode & 0o077:
        raise PermissionError("Tenant directory must be non-symlink with mode 0700")
    return tenant_dir / (user_id + "_" + config.expected_realm + ".enc")


def _save_tokens(config: Config, payload: dict, realm: str, *, user_id: str | None = None) -> None:
    _secure_dir(config)
    record = {
        "access_token": payload["access_token"],
        "refresh_token": payload["refresh_token"],
        "expires_at": time.time() + int(payload.get("expires_in", 3600)),
        "realm": realm,
        "authorized_user_id": user_id,
    }
    blob = Fernet(_key(config)).encrypt(json.dumps(record).encode())
    _atomic_write(config.private_dir / "qbo_tokens.enc", blob)


def save_tenant_tokens(config: Config, payload: dict, *, user_id: str) -> None:
    """Explicit new-tenant path; never overwrite the legacy pilot token."""
    _secure_dir(config)
    user_id = str(uuid.UUID(user_id))
    record = {"access_token": payload["access_token"], "refresh_token": payload["refresh_token"],
              "expires_at": time.time() + int(payload.get("expires_in", 3600)),
              "realm": config.expected_realm, "authorized_user_id": user_id}
    _atomic_write(_tenant_token_path(config, user_id=user_id),
                  Fernet(_key(config)).encrypt(json.dumps(record).encode()))


def load_tenant_tokens(config: Config, *, user_id: str) -> dict:
    """Fail closed: never fall back to another tenant's or the legacy pilot token."""
    user_id = str(uuid.UUID(user_id))
    path = _tenant_token_path(config, user_id=user_id)
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError("Tenant QuickBooks authorization not available")
    record = json.loads(Fernet(_key(config)).decrypt(path.read_bytes()))
    if record.get("authorized_user_id") != user_id or record.get("realm") != config.expected_realm:
        raise ValueError("Tenant QuickBooks authorization mismatch")
    return record


def disconnect_tenant_quickbooks(config: Config, *, user_id: str) -> None:
    """Revoke Intuit refresh token, then remove only the matching tenant credential."""
    user_id = str(uuid.UUID(user_id))
    path = _tenant_token_path(config, user_id=user_id)
    lock = path.with_suffix(".lock")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(fd, "rb") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        record = load_tenant_tokens(config, user_id=user_id)
        response = requests.post(
            "https://developer.api.intuit.com/v2/oauth2/tokens/revoke",
            auth=(config.client_id, config.client_secret),
            data={"token": record["refresh_token"]},
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            timeout=20)
        if response.status_code != 200:
            raise ValueError("QuickBooks token revocation unconfirmed")
        path.unlink()


def get_tenant_access_token(config: Config, *, user_id: str) -> tuple[str, str]:
    """Refresh only this user's realm token; never use the pilot token file."""
    user_id = str(uuid.UUID(user_id))
    path = _tenant_token_path(config, user_id=user_id)
    lock = path.with_suffix(".lock")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(fd, "rb") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        record = load_tenant_tokens(config, user_id=user_id)
        if time.time() < float(record["expires_at"]) - 120:
            return record["access_token"], record["realm"]
        updated = _exchange(config, {"grant_type": "refresh_token",
                                     "refresh_token": record["refresh_token"]})
        save_tenant_tokens(config, updated, user_id=user_id)
        return updated["access_token"], config.expected_realm


def read_tenant_invoice_count(config: Config, *, user_id: str) -> int:
    """Tenant-bound QBO read: realm comes only from verified token storage."""
    token, realm = get_tenant_access_token(config, user_id=user_id)
    if realm != config.expected_realm:
        raise ValueError("Tenant realm binding mismatch")
    response = requests.get(f"{SANDBOX_API}/v3/company/{realm}/query",
        params={"query": "SELECT COUNT(*) FROM Invoice"},
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"}, timeout=20)
    if response.status_code != 200:
        raise ValueError("Tenant invoice count read refused")
    body = response.json()
    count = (body.get("QueryResponse") or {}).get("totalCount")
    if body.get("Fault") or type(count) is not int or count < 0:
        raise ValueError("Tenant invoice count invalid")
    return count


def load_tokens(config: Config) -> dict:
    if not config.expected_realm or not str(config.expected_realm).isdigit():
        raise ValueError("Expected QuickBooks company ID is required")
    _secure_dir(config)
    path = config.private_dir / "qbo_tokens.enc"
    if not path.exists():
        raise ValueError("QuickBooks authorization not completed")
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise PermissionError("Token file must be non-symlink with permissions 0600")
    record = json.loads(Fernet(_key(config)).decrypt(path.read_bytes()))
    if record.get("realm") != config.expected_realm:
        raise ValueError("Authorized company does not match configured sandbox")
    return record


def complete_authorization(config: Config, *, state: str, code: str, realm: str,
                           user_id: str | None = None) -> None:
    if not code or not realm or not realm.isdigit():
        raise ValueError("Invalid Intuit callback")
    if config.expected_realm and realm != config.expected_realm:
        raise ValueError("Wrong QuickBooks sandbox company")
    check_state(config, state, user_id=user_id)
    token = _exchange(config, {"grant_type": "authorization_code", "code": code,
                               "redirect_uri": config.redirect_uri})
    if user_id is not None:
        save_tenant_tokens(config, token, user_id=user_id)
    else:
        _save_tokens(config, token, realm, user_id=None)


def get_access_token(config: Config, *, force_refresh: bool = False) -> tuple[str, str]:
    if not config.expected_realm or not str(config.expected_realm).isdigit():
        raise ValueError("Expected QuickBooks company ID is required")
    _secure_dir(config)
    # Allow one renewal at a time: simultaneous renewals can invalidate rotated tokens.
    lock = config.private_dir / "qbo_refresh.lock"
    fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(fd, "rb") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        record = load_tokens(config)
        if config.expected_realm and record["realm"] != config.expected_realm:
            raise ValueError("Authorized company does not match configured sandbox")
        if not force_refresh and time.time() < float(record["expires_at"]) - 120:
            return record["access_token"], record["realm"]
        updated = _exchange(config, {"grant_type": "refresh_token",
                                     "refresh_token": record["refresh_token"]})
        # Intuit can rotate refresh tokens; replace BOTH atomically.
        _save_tokens(config, updated, record["realm"], user_id=record.get("authorized_user_id"))
        return updated["access_token"], record["realm"]


def _query_item(config: Config, query: str) -> dict:
    access_token, realm = get_access_token(config)
    response = requests.get(
        f"{SANDBOX_API}/v3/company/{realm}/query",
        params={"query": query},
        headers={"Authorization": "Bearer " + access_token, "Accept": "application/json"},
        timeout=20,
    )
    if response.status_code != 200:
        raise ValueError(f"QuickBooks sandbox query failed (HTTP {response.status_code})")
    payload = response.json()
    if "Fault" in payload or "QueryResponse" not in payload:
        raise ValueError("QuickBooks returned a fault or incomplete query response")
    items = payload["QueryResponse"].get("Item", [])
    if not isinstance(items, list):
        raise ValueError("QuickBooks items response has invalid format")
    return {
        "source": "quickbooks_sandbox",
        "query_time_utc": datetime.now(timezone.utc).isoformat(),
        "items": [{
            "Id": item.get("Id"),
            "Name": item.get("Name"),
            "Sku": item.get("Sku"),
            "Type": item.get("Type"),
            "TrackQtyOnHand": item.get("TrackQtyOnHand"),
            "QtyOnHand": item.get("QtyOnHand"),
            "UnitPrice": item.get("UnitPrice"),
        } for item in items],
    }


def read_home_currency(config: Config) -> str | None:
    """Read QBO base currency. Unknown for multicurrency, malformed or absent settings.

    No FX inference or conversion is permitted in the sandbox price check.
    """
    token, realm = get_access_token(config)
    response = requests.get(
        f"{SANDBOX_API}/v3/company/{realm}/preferences",
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
        timeout=20,
    )
    if response.status_code != 200:
        raise ValueError(f"QuickBooks preferences GET failed (HTTP {response.status_code})")
    payload = response.json()
    prefs = payload.get("Preferences")
    if payload.get("Fault") or not isinstance(prefs, dict):
        raise ValueError("QuickBooks preferences unavailable")
    currency = prefs.get("CurrencyPrefs") or {}
    if currency.get("MultiCurrencyEnabled") is not False:
        return None  # Different selling currencies may apply; block price comparison.
    home = (currency.get("HomeCurrency") or {}).get("value")
    if not isinstance(home, str) or not re.fullmatch(r"[A-Z]{3}", home):
        return None
    return home


def read_inventory_item(config: Config, name: str) -> dict:
    if not re.fullmatch(r"[\w .-]{1,100}", name, flags=re.ASCII):
        raise ValueError("Invalid Item name for safe read-only query")
    return _query_item(config, "SELECT * FROM Item WHERE Name = '" + name + "'")


def read_inventory_item_by_sku(config: Config, sku: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", sku):
        raise ValueError("Invalid SKU for safe QuickBooks query")
    result = _query_item(config, "SELECT * FROM Item WHERE Sku = '" + sku + "'")
    matches = [item for item in result["items"] if item.get("Sku") == sku]
    if len(matches) != 1:
        raise ValueError("QuickBooks SKU missing or ambiguous")
    result["items"] = matches
    return result


def _require_live_supabase_session(token: str, subject: str) -> None:
    """Fail closed unless Supabase Auth still recognizes this session."""
    key = os.environ.get("VERICON_SUPABASE_PUBLISHABLE_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Session validation unavailable")
    try:
        response = requests.get(
            SUPABASE_ISSUER + "/user",
            headers={"apikey": key, "Authorization": "Bearer " + token},
            timeout=5,
        )
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Session validation unavailable") from None
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Session not active")
    try:
        user = response.json()
    except ValueError:
        raise HTTPException(status_code=503, detail="Session validation unavailable") from None
    if not isinstance(user, dict) or user.get("id") != subject:
        raise HTTPException(status_code=401, detail="Session not active")


def _verified_customer_subject(header: str | None) -> str:
    """Authenticate Supabase user JWT; do not infer tenant ownership from it."""
    if not isinstance(header, str) or not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    token = header[7:]
    if not token or len(token) > 8192 or any(c.isspace() for c in token):
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        key = SUPABASE_JWKS.get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=["ES256"],
                            issuer=SUPABASE_ISSUER, audience="authenticated",
                            options={"require": ["exp", "iat", "iss", "aud", "sub"]}, leeway=0)
        subject = str(uuid.UUID(claims["sub"]))
        if claims.get("role") != "authenticated":
            raise ValueError("Not a user session")
        _require_live_supabase_session(token, subject)
        return subject
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid authentication") from None


@app.get("/auth/me")
def auth_identity(request: Request) -> dict:
    return {"authenticated": True, "subject": _verified_customer_subject(request.headers.get("authorization")),
            "tenant_authorized": False}


@app.get("/health", response_class=PlainTextResponse)
def health() -> str:
    return "VERICON-QBO-SANDBOX-CONNECTOR"


def _pilot_qbo_owner(header: str | None, realm: str) -> str:
    subject = _verified_customer_subject(header)
    api_key = os.environ.get("VERICON_SUPABASE_PUBLISHABLE_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="Pilot authorization not configured")
    try:
        response = requests.get(
            SUPABASE_ISSUER.replace("/auth/v1", "/rest/v1") + "/vericon_pilot_connections",
            params={"select": "qbo_realm_id,connection_status", "user_id": "eq." + subject},
            headers={"apikey": api_key, "Authorization": header}, timeout=8)
        rows = response.json() if response.status_code == 200 else []
    except (requests.RequestException, ValueError):
        rows = []
    if not isinstance(rows, list) or len(rows) != 1 or rows[0].get("qbo_realm_id") != realm or rows[0].get("connection_status") != "pilot_linked":
        raise HTTPException(status_code=403, detail="Pilot account authorization denied")
    return subject


def _authorized_tenant_connection(header: str | None) -> dict:
    """Require an authenticated, RLS-visible, ownership-verified tenant mapping."""
    subject = _verified_customer_subject(header)
    key = os.environ.get("VERICON_SUPABASE_PUBLISHABLE_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Tenant authorization unavailable")
    try:
        response = requests.get(
            SUPABASE_ISSUER.replace("/auth/v1", "/rest/v1") + "/vericon_pilot_connections",
            params={"select": "user_id,shop_domain,qbo_realm_id,connection_status,ownership_verified",
                    "user_id": "eq." + subject},
            headers={"apikey": key, "Authorization": header}, timeout=8)
        rows = response.json() if response.status_code == 200 else []
    except (requests.RequestException, ValueError):
        rows = []
    if not isinstance(rows, list) or len(rows) != 1:
        raise HTTPException(status_code=403, detail="Tenant connection not authorized")
    row = rows[0]
    realm = row.get("qbo_realm_id")
    store = row.get("shop_domain")
    if (row.get("user_id") != subject or row.get("connection_status") != "pilot_linked"
            or row.get("ownership_verified") is not True or not isinstance(realm, str)
            or not realm.isdigit() or not isinstance(store, str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,61}\.myshopify\.com", store)):
        raise HTTPException(status_code=403, detail="Tenant connection not authorized")
    return {"user_id": subject, "realm": realm, "store": store}


@app.get("/tenant/finance/access-check")
def tenant_finance_access_check(request: Request) -> dict:
    """Verify tenant binding without exposing any financial records or credentials."""
    connection = _authorized_tenant_connection(request.headers.get("authorization"))
    # Financial data stays disabled until separate explicit enablement and
    # actual cross-session isolation verification. Never return tokens.
    return {"authenticated_tenant": True, "shop_domain": connection["store"],
            "qbo_realm_id": connection["realm"], "financial_access_enabled": False}


@app.get("/tenant/finance/invoice-count")
def tenant_finance_invoice_count(request: Request, realm: str) -> dict:
    """Bounded read-only tenant isolation probe; no invoices or tokens returned."""
    connection = _authorized_tenant_connection(request.headers.get("authorization"))
    if realm != connection["realm"]:
        raise HTTPException(status_code=403, detail="Cross-tenant finance access denied")
    config = _tenant_qbo_config(load_saved_setup(), connection["realm"])
    try:
        count = read_tenant_invoice_count(config, user_id=connection["user_id"])
    except (ValueError, requests.RequestException):
        raise HTTPException(status_code=503, detail="Financial read unavailable") from None
    return {"invoice_count": count, "realm": connection["realm"], "read_only": True}


def _tenant_qbo_config(config: Config, realm: str) -> Config:
    if not isinstance(realm, str) or not realm.isdigit():
        raise ValueError("Invalid tenant QuickBooks company")
    return replace(config, expected_realm=realm)


def _shopify_proof_file(config: Config) -> Path:
    return config.private_dir / "shopify_owner_challenge.json"


def _shopify_owner(header: str | None) -> str:
    from shopify_read import STORE
    subject = _verified_customer_subject(header)
    api_key = os.environ.get("VERICON_SUPABASE_PUBLISHABLE_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="Pilot authorization unavailable")
    try:
        r = requests.get(SUPABASE_ISSUER.replace("/auth/v1", "/rest/v1") + "/vericon_pilot_connections",
                         params={"select": "shop_domain,connection_status", "user_id": "eq." + subject},
                         headers={"apikey": api_key, "Authorization": header}, timeout=8)
        rows = r.json() if r.status_code == 200 else []
    except (requests.RequestException, ValueError):
        rows = []
    if not isinstance(rows, list) or len(rows) != 1 or rows[0].get("shop_domain") != STORE or rows[0].get("connection_status") != "pilot_linked":
        raise HTTPException(status_code=403, detail="Shopify pilot account denied")
    return subject


@app.post("/shopify/ownership/start")
def shopify_ownership_start(request: Request) -> dict:
    from shopify_read import STORE
    owner = _shopify_owner(request.headers.get("authorization"))
    config = load_saved_setup()
    _secure_dir(config)
    code = secrets.token_urlsafe(24)
    _atomic_write(_shopify_proof_file(config), json.dumps({
        "user_id": owner, "store": STORE, "digest": hashlib.sha256(code.encode()).hexdigest(),
        "expires_at": int(time.time()) + 600}).encode())
    return {"challenge": code, "expires_in": 600, "namespace": "vericon", "key": "owner_proof"}


@app.post("/shopify/ownership/verify")
def shopify_ownership_verify(request: Request) -> dict:
    from shopify_read import STORE, load_setup, read_owner_proof
    owner = _shopify_owner(request.headers.get("authorization"))
    config = load_saved_setup()
    path = _shopify_proof_file(config)
    try:
        proof = json.loads(path.read_text())
        if proof.get("user_id") != owner or proof.get("store") != STORE:
            raise ValueError("Owner mismatch")
        if int(proof.get("expires_at", 0)) < time.time():
            raise ValueError("Expired")
        value = read_owner_proof(load_setup())
        if not value or not secrets.compare_digest(
                hashlib.sha256(value.encode()).hexdigest(), str(proof.get("digest", ""))):
            raise ValueError("Challenge mismatch")
        path.unlink(missing_ok=True)
        _atomic_write(config.private_dir / "shopify_owner_verified.json", json.dumps({
            "user_id": owner, "store": STORE, "verified_at": int(time.time()),
            "proof_digest": proof["digest"]}).encode())
    except (ValueError, OSError, KeyError, requests.RequestException):
        raise HTTPException(status_code=400, detail="Shopify ownership proof not verified") from None
    return {"verified": True, "store": STORE, "financial_access_enabled": False}


def _tenant_proof_path(config: Config, user_id: str, store: str) -> Path:
    from shopify_read import _tenant_setup_path
    _tenant_setup_path(user_id, store)
    folder = config.private_dir / "shopify_owner_proofs"
    folder.mkdir(mode=0o700, exist_ok=True)
    if folder.is_symlink() or (folder.stat().st_mode & 0o077):
        raise PermissionError("Unsafe tenant proof directory")
    return folder / (user_id + "_" + store + ".json")


def _tenant_shopify_context(header: str | None) -> dict:
    subject = _verified_customer_subject(header)
    key = os.environ.get("VERICON_SUPABASE_PUBLISHABLE_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Tenant authorization unavailable")
    try:
        r = requests.get(SUPABASE_ISSUER.replace("/auth/v1", "/rest/v1") + "/vericon_pilot_connections",
            params={"select":"user_id,shop_domain,connection_status,ownership_verified", "user_id":"eq." + subject},
            headers={"apikey":key,"Authorization":header}, timeout=8)
        rows = r.json() if r.status_code == 200 else []
    except (ValueError, requests.RequestException):
        rows = []
    if not isinstance(rows,list) or len(rows)!=1:
        raise HTTPException(status_code=403,detail="Tenant not authorized")
    row=rows[0]
    store=row.get("shop_domain")
    if row.get("user_id")!=subject or row.get("connection_status")!="pilot_linked" or not isinstance(store,str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,61}\.myshopify\.com",store):
        raise HTTPException(status_code=403,detail="Tenant not authorized")
    from shopify_read import STORE,load_tenant_setup
    if store == STORE:
        raise HTTPException(status_code=409,detail="Pilot already verified")
    try:
        load_tenant_setup(subject,store)
    except (ValueError,PermissionError,OSError):
        raise HTTPException(status_code=403,detail="Tenant Shopify credentials unavailable") from None
    return {"user_id":subject,"store":store,"verified":row.get("ownership_verified") is True}


@app.post("/tenant/shopify/ownership/start")
def tenant_shopify_ownership_start(request: Request) -> dict:
    context=_tenant_shopify_context(request.headers.get("authorization"))
    if context["verified"]:
        return {"verified":True,"store":context["store"]}
    config=load_saved_setup()
    code=secrets.token_urlsafe(24)
    path=_tenant_proof_path(config,context["user_id"],context["store"])
    _atomic_write(path,json.dumps({"digest":hashlib.sha256(code.encode()).hexdigest(),
        "expires_at":int(time.time())+600,"user_id":context["user_id"],"store":context["store"]}).encode())
    return {"challenge":code,"expires_in":600,"store":context["store"],"namespace":"vericon","key":"owner_proof"}


@app.post("/tenant/shopify/ownership/verify")
def tenant_shopify_ownership_verify(request: Request) -> dict:
    context=_tenant_shopify_context(request.headers.get("authorization"))
    config=load_saved_setup()
    path=_tenant_proof_path(config,context["user_id"],context["store"])
    try:
        proof=json.loads(path.read_text())
        if proof.get("user_id")!=context["user_id"] or proof.get("store")!=context["store"] or int(proof.get("expires_at",0))<time.time():
            raise ValueError("Invalid proof")
        from shopify_read import read_tenant_owner_proof
        value=read_tenant_owner_proof(context["user_id"],context["store"])
        if not value or not secrets.compare_digest(hashlib.sha256(value.encode()).hexdigest(),proof["digest"]):
            raise ValueError("Proof mismatch")
        path.unlink(missing_ok=True)
        _atomic_write(path.with_suffix(".verified"),json.dumps({"user_id":context["user_id"],
            "store":context["store"],"verified_at":int(time.time())}).encode())
    except (ValueError,OSError,KeyError,requests.RequestException):
        raise HTTPException(status_code=400,detail="Tenant Shopify ownership not verified") from None
    return {"verified":True,"store":context["store"],"financial_access_enabled":False}


@app.post("/oauth/quickbooks/start")
def quickbooks_start(request: Request) -> dict:
    config = load_saved_setup()
    if config.redirect_uri != "https://app.vericon.site/oauth/quickbooks/callback":
        raise HTTPException(status_code=503, detail="Public callback not configured")
    owner = _pilot_qbo_owner(request.headers.get("authorization"), config.expected_realm or "")
    return {"authorization_url": create_authorization_url(config, user_id=owner)}


@app.post("/tenant/quickbooks/disconnect")
def tenant_quickbooks_disconnect(request: Request) -> dict:
    connection = _authorized_tenant_connection(request.headers.get("authorization"))
    config = _tenant_qbo_config(load_saved_setup(), connection["realm"])
    try:
        disconnect_tenant_quickbooks(config, user_id=connection["user_id"])
    except (ValueError, requests.RequestException, OSError, PermissionError):
        raise HTTPException(status_code=503, detail="QuickBooks disconnect not confirmed") from None
    return {"disconnected": True, "realm": connection["realm"], "reconnect_via": "/tenant/quickbooks/start"}


@app.post("/tenant/quickbooks/start")
def tenant_quickbooks_start(request: Request) -> dict:
    connection = _authorized_tenant_connection(request.headers.get("authorization"))
    config = load_saved_setup()
    if config.redirect_uri != "https://app.vericon.site/oauth/quickbooks/callback":
        raise HTTPException(status_code=503, detail="Public callback not configured")
    from shopify_read import STORE, load_tenant_setup
    if connection["store"] != STORE:
        try:
            load_tenant_setup(connection["user_id"], connection["store"])
        except (ValueError, PermissionError, OSError):
            raise HTTPException(status_code=403, detail="Tenant Shopify connection not configured") from None
    tenant_config = _tenant_qbo_config(config, connection["realm"])
    return {"authorization_url": create_authorization_url(tenant_config, user_id=connection["user_id"])}


@app.get("/oauth/quickbooks/callback", response_class=PlainTextResponse)
def quickbooks_callback(state: str = "", code: str = "", realmId: str = "", error: str = "") -> str:
    if error:
        raise HTTPException(status_code=400, detail="Intuit authorization was rejected")
    try:
        config = load_saved_setup()
        owner = None
        if config.redirect_uri == "https://app.vericon.site/oauth/quickbooks/callback":
            record = _callback_state_record(config, state)
            owner = str(uuid.UUID(record["user_id"]))
            recorded_realm = record.get("expected_realm")
            if not isinstance(recorded_realm, str) or not recorded_realm.isdigit():
                raise ValueError("Invalid OAuth state tenant realm")
            # Existing pilot uses the original config; future tenants get their
            # own realm-scoped config, with no pilot token fallback.
            if recorded_realm != config.expected_realm:
                config = _tenant_qbo_config(config, recorded_realm)
        complete_authorization(config, state=state, code=code, realm=realmId, user_id=owner)
    except (ValueError, KeyError, OSError, PermissionError, requests.RequestException) as exc:
        reason = str(exc)
        if isinstance(exc, FileNotFoundError):
            category = "missing_oauth_state_file"
        elif isinstance(exc, json.JSONDecodeError):
            category = "invalid_oauth_state_file"
        elif reason == "Wrong QuickBooks sandbox company":
            category = "realm_mismatch"
        elif reason.startswith("Intuit token exchange refused (HTTP "):
            category = "token_exchange_http_failure"
        elif reason in ("Missing or invalid OAuth state", "OAuth state mismatch", "OAuth state expired"):
            category = "state_validation_failure"
        elif reason == "OAuth state user binding mismatch":
            category = "user_binding_failure"
        else:
            category = "other_failure"
        logging.getLogger("uvicorn.error").warning("QBO_OAUTH_CALLBACK_FAILURE category=%s exception_type=%s", category, type(exc).__name__)
        raise HTTPException(status_code=400, detail="QuickBooks authorization failed") from None
    return "QuickBooks Sandbox connection authorized. You can close this tab."


def load_saved_setup() -> Config:
    private = BASE_DIR / "private"
    path = private / "qbo_setup.json"
    if not private.is_dir() or private.stat().st_mode & 0o077:
        raise PermissionError("Private directory missing or unsafe")
    if not path.is_file() or path.stat().st_mode & 0o077:
        raise PermissionError("Saved setup missing or unsafe")
    values = json.loads(path.read_text(encoding="utf-8"))
    required = ("VERICON_QBO_CLIENT_ID", "VERICON_QBO_CLIENT_SECRET",
                "VERICON_QBO_REDIRECT_URI", "VERICON_QBO_EXPECTED_REALM")
    if any(not values.get(k) for k in required):
        raise ValueError("Saved setup incomplete")
    if not str(values["VERICON_QBO_EXPECTED_REALM"]).isdigit():
        raise ValueError("Invalid sandbox company ID")
    return Config(client_id=values["VERICON_QBO_CLIENT_ID"],
                  client_secret=values["VERICON_QBO_CLIENT_SECRET"],
                  redirect_uri=values["VERICON_QBO_REDIRECT_URI"],
                  private_dir=private, expected_realm=values["VERICON_QBO_EXPECTED_REALM"])


def main() -> None:
    parser = argparse.ArgumentParser(description="VERICON QBO sandbox connector")
    parser.add_argument("--saved-setup", action="store_true",
                        help="Use secure private sandbox setup without retyping credentials")
    cmd = parser.add_subparsers(dest="command", required=True)
    cmd.add_parser("auth-url", help="Generate a state-protected authorization URL")
    item_cmd = cmd.add_parser("item", help="Read one QBO sandbox item by exact name")
    item_cmd.add_argument("--name", default="VERICON TEST")
    cmd.add_parser("status", help="Show connection status without revealing credentials")
    args = parser.parse_args()
    config = load_saved_setup() if args.saved_setup else Config.from_env()
    if args.command == "auth-url":
        print(create_authorization_url(config))
    elif args.command == "item":
        print(json.dumps(read_inventory_item(config, args.name), ensure_ascii=False))
    else:
        try:
            record = load_tokens(config)
            print(json.dumps({"connected": True, "realm_matches_expected": (
                not config.expected_realm or record["realm"] == config.expected_realm),
                "access_token_current": time.time() < float(record["expires_at"]) - 120}))
        except ValueError:
            print(json.dumps({"connected": False}))


if __name__ == "__main__":
    main()
