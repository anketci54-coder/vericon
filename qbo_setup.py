#!/usr/bin/env python3
"""One-time local QBO sandbox OAuth authorization helper for VERICON.

Run only in an interactive SSH session using a localhost port-forward.
Never paste private credentials into a conversation, GitHub or shell commands.
"""
from __future__ import annotations

import getpass
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from qbo_oauth import Config, create_authorization_url, load_tokens, read_inventory_item

ROOT = Path(__file__).resolve().parent
PRIVATE = ROOT / "private"
CONFIG = PRIVATE / "qbo_setup.json"
HOST = "127.0.0.1"
PORT = 8782
REDIRECT = f"http://localhost:{PORT}/oauth/quickbooks/callback"


def atomic_json(path: Path, data: dict) -> None:
    import tempfile
    fd, temp = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def ask_credentials() -> dict:
    print("VERICON | QuickBooks SANDBOX | first-time authorization")
    print("Use the *Development* keys, NOT Production. Do not share keys in chat.")
    client_id = input("Development Client ID: ").strip()
    client_secret = getpass.getpass("NEW/ROTATED Development Client Secret (hidden): ").strip()
    realm = input("Sandbox company ID (realm ID): ").strip()
    if not client_id or not client_secret or not realm.isdigit():
        raise ValueError("Missing client ID, client secret or numeric sandbox company ID")
    return {"VERICON_QBO_CLIENT_ID": client_id,
            "VERICON_QBO_CLIENT_SECRET": client_secret,
            "VERICON_QBO_EXPECTED_REALM": realm,
            "VERICON_QBO_REDIRECT_URI": REDIRECT,
            "VERICON_QBO_PRIVATE_DIR": str(PRIVATE)}


def apply_config(data: dict) -> Config:
    for key, value in data.items():
        os.environ[key] = value
    return Config.from_env()


def port_is_free() -> bool:
    with socket.socket() as s:
        try:
            s.bind((HOST, PORT))
        except OSError:
            return False
    return True


def main() -> int:
    if not sys.stdin.isatty():
        print("ERROR: Interactive terminal required; do not pass credentials as arguments.")
        return 2
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    if PRIVATE.stat().st_mode & 0o077:
        print("ERROR: private/ permissions are not 0700")
        return 2
    if CONFIG.exists():
        if CONFIG.stat().st_mode & 0o077:
            print("ERROR: saved configuration permissions are not 0600")
            return 2
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        print("Saved private sandbox credentials found. Reusing without showing them.")
    else:
        data = ask_credentials()
        atomic_json(CONFIG, data)
    config = apply_config(data)
    if not port_is_free():
        print(f"ERROR: localhost port {PORT} is occupied. No process was changed.")
        return 2
    print("Launching LOCAL-ONLY callback; do not expose it on a public interface.")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "qbo_oauth:app",
         "--host", HOST, "--port", str(PORT), "--no-access-log", "--log-level", "warning"],
        cwd=str(ROOT),
        env=os.environ.copy(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        for _ in range(30):
            if proc.poll() is not None:
                raise RuntimeError("Callback process failed before opening the local port")
            if not port_is_free():
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("Callback did not start")
        url = create_authorization_url(config)
        print("\nOpen this URL in the SAME COMPUTER browser:")
        print(url)
        print("\nThe SSH -L 8782 tunnel must remain open. Waiting for Intuit approval (maximum 9 minutes)...")
        initial = None
        try:
            initial = load_tokens(config)
        except ValueError:
            pass
        for _ in range(540):
            if proc.poll() is not None:
                raise RuntimeError("Callback stopped before confirmation")
            try:
                tokens = load_tokens(config)
                if initial is None or tokens != initial:
                    print("OAuth authorization stored securely.")
                    try:
                        result = read_inventory_item(config, "VERICON TEST")
                    except ValueError as exc:
                        print("Item query failed after authorization:", str(exc))
                        return 3
                    print(json.dumps({
                        "query_success": True,
                        "items": [{"Sku": row.get("Sku"), "QtyOnHand": row.get("QtyOnHand"),
                                   "Type": row.get("Type")} for row in result["items"]],
                        "source": "QuickBooks sandbox",
                    }, ensure_ascii=False))
                    return 0
            except ValueError:
                pass
            time.sleep(1)
        print("Authorization not completed; no live connection claimed.")
        return 1
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=4)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, OSError) as exc:
        print("ERROR:", str(exc))
        raise SystemExit(2)
