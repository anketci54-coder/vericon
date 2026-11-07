"""VERICON QuickBooks Online SANDBOX-only OAuth + read-only Item client.

This module is NOT a running service until an operator deliberately configures
an HTTPS callback with access logs disabled and starts uvicorn locally.
"""
from __future__ import annotations

import argparse
import json
import fcntl
import os
import re
import secrets
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse

import requests
from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
SANDBOX_API = "https://sandbox-quickbooks.api.intuit.com"
SCOPE = "com.intuit.quickbooks.accounting"
BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="VERICON QBO sandbox connector", docs_url=None, redoc_url=None, openapi_url=None)


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


def create_authorization_url(config: Config) -> str:
    _secure_dir(config)
    state = secrets.token_urlsafe(32)
    _atomic_write(
        _state_path(config),
        json.dumps({"state": state, "expires_at": int(time.time()) + 600}).encode(),
    )
    return AUTH_URL + "?" + urlencode(
        {"client_id": config.client_id,
         "response_type": "code",
         "scope": SCOPE,
         "redirect_uri": config.redirect_uri,
         "state": state}
    )


def check_state(config: Config, supplied: str) -> None:
    path = _state_path(config)
    try:
        obj = json.loads(path.read_bytes())
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        raise ValueError("Missing or invalid OAuth state") from None
    if not secrets.compare_digest(str(obj.get("state", "")), str(supplied)):
        raise ValueError("OAuth state mismatch")
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


def _save_tokens(config: Config, payload: dict, realm: str) -> None:
    _secure_dir(config)
    record = {
        "access_token": payload["access_token"],
        "refresh_token": payload["refresh_token"],
        "expires_at": time.time() + int(payload.get("expires_in", 3600)),
        "realm": realm,
    }
    blob = Fernet(_key(config)).encrypt(json.dumps(record).encode())
    _atomic_write(config.private_dir / "qbo_tokens.enc", blob)


def load_tokens(config: Config) -> dict:
    path = config.private_dir / "qbo_tokens.enc"
    if not path.exists():
        raise ValueError("QuickBooks authorization not completed")
    if path.stat().st_mode & 0o077:
        raise PermissionError("Token file permissions must be 0600")
    return json.loads(Fernet(_key(config)).decrypt(path.read_bytes()))


def complete_authorization(config: Config, *, state: str, code: str, realm: str) -> None:
    check_state(config, state)
    if not code or not realm or not realm.isdigit():
        raise ValueError("Invalid Intuit callback")
    if config.expected_realm and realm != config.expected_realm:
        raise ValueError("Wrong QuickBooks sandbox company")
    token = _exchange(config, {"grant_type": "authorization_code", "code": code,
                               "redirect_uri": config.redirect_uri})
    _save_tokens(config, token, realm)


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
        _save_tokens(config, updated, record["realm"])
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


@app.get("/health", response_class=PlainTextResponse)
def health() -> str:
    return "VERICON-QBO-SANDBOX-CONNECTOR"


@app.get("/oauth/quickbooks/callback", response_class=PlainTextResponse)
def quickbooks_callback(state: str = "", code: str = "", realmId: str = "", error: str = "") -> str:
    if error:
        raise HTTPException(status_code=400, detail="Intuit authorization was rejected")
    try:
        complete_authorization(Config.from_env(), state=state, code=code, realm=realmId)
    except (ValueError, PermissionError, requests.RequestException):
        # Do not leak authorization code, realm ID or tokens into the browser.
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
