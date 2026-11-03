#!/usr/bin/env python3
"""VERICON Module A: bounded, read-only QuickBooks Sandbox invoice line audit.

Verifies only Qty x UnitPrice against line Amount. Does NOT validate the invoice
subtotal, tax, discounts, payment, shipping, Shopify orders or financial loss.
Missing/unsupported information is BLOCKED, never a fabricated discrepancy.
"""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

import requests

from qbo_oauth import SANDBOX_API, get_access_token, load_saved_setup

MAX_INVOICES = 100
USD_REVIEW_TOLERANCE = Decimal("0.01")
SUPPORTED_NON_PRODUCT_LINES = frozenset(("SubTotalLineDetail", "DiscountLineDetail"))


def number(value) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError("Missing numeric field")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Invalid numeric field") from None
    if not result.is_finite():
        raise ValueError("Non-finite numeric field")
    return result


def audit_invoice(inv: dict) -> dict:
    identifier = str(inv.get("Id") or "")
    base = {"invoice_id": identifier, "checked_product_lines": 0, "review_product_lines": 0,
            "status": "BLOCKED_INVALID_INVOICE"}
    if not identifier or (inv.get("CurrencyRef") or {}).get("value") != "USD":
        return base
    lines = inv.get("Line")
    if not isinstance(lines, list) or not lines:
        return {**base, "status": "BLOCKED_NO_LINES"}
    product_lines = 0
    for line in lines:
        if not isinstance(line, dict):
            return {**base, "status": "BLOCKED_UNSUPPORTED_LINE"}
        kind = line.get("DetailType")
        if kind in SUPPORTED_NON_PRODUCT_LINES:
            continue  # Not a second product sale; do not double count subtotals.
        if kind != "SalesItemLineDetail":
            return {**base, "status": "BLOCKED_UNSUPPORTED_LINE"}
        product_lines += 1
        detail = line.get("SalesItemLineDetail") or {}
        try:
            quantity = number(detail.get("Qty"))
            unit_price = number(detail.get("UnitPrice"))
            amount = number(line.get("Amount"))
        except (ValueError, AttributeError):
            return {**base, "status": "BLOCKED_INCOMPLETE_PRODUCT_LINE"}
        base["checked_product_lines"] += 1
        if abs(quantity * unit_price - amount) > USD_REVIEW_TOLERANCE:
            base["review_product_lines"] += 1
    if not product_lines:
        return {**base, "status": "BLOCKED_NO_PRODUCT_LINES"}
    return {**base, "status": "REVIEW_LINE_AMOUNT" if base["review_product_lines"]
            else "LINE_AMOUNTS_MATCH"}


def _get_json(url: str, query: str, headers: dict) -> dict:
    response = requests.get(url, params={"query": query}, headers=headers, timeout=20)
    if response.status_code != 200:
        raise ValueError(f"QuickBooks Sandbox Invoice read failed (HTTP {response.status_code})")
    payload = response.json()
    if payload.get("Fault") or not isinstance(payload.get("QueryResponse"), dict):
        raise ValueError("QuickBooks Invoice read incomplete or fault")
    return payload["QueryResponse"]


def read_invoices() -> list[dict]:
    token, realm = get_access_token(load_saved_setup())
    url = f"{SANDBOX_API}/v3/company/{realm}/query"
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    count_data = _get_json(url, "SELECT COUNT(*) FROM Invoice", headers)
    count = count_data.get("totalCount")
    if type(count) is not int or count < 0 or count > MAX_INVOICES:
        raise ValueError("Invoice count unknown or above controlled batch limit")
    data = _get_json(url, f"SELECT * FROM Invoice STARTPOSITION 1 MAXRESULTS {MAX_INVOICES}", headers)
    invoices = data.get("Invoice", [])
    if not isinstance(invoices, list) or len(invoices) != count:
        raise ValueError("Invoice collection incomplete or changed during read")
    ids = [row.get("Id") for row in invoices if isinstance(row, dict)]
    if len(ids) != count or any(not v for v in ids) or len(set(ids)) != count:
        raise ValueError("Invoice identifiers missing or ambiguous")
    return invoices


def audit_all(invoices: list[dict]) -> dict:
    results = [audit_invoice(inv) for inv in invoices]
    blocked = [r["invoice_id"] for r in results if r["status"].startswith("BLOCKED_")]
    review = [r["invoice_id"] for r in results if r["status"].startswith("REVIEW_")]
    return {"source": "quickbooks_sandbox_live_read", "invoice_count": len(invoices),
            "line_amounts_checked": sum(r["checked_product_lines"] for r in results),
            "verified_invoice_count": sum(r["status"] == "LINE_AMOUNTS_MATCH" for r in results),
            "review_invoice_count": len(review), "blocked_invoice_count": len(blocked),
            "blocked_invoice_ids": blocked, "review_invoice_ids": review,
            "checked_fields": "USD sales line Qty x UnitPrice versus Amount only",
            "cross_system_order_matching": "NOT_CHECKED_NO_SHOPIFY_ORDERS_OR_READ_ORDERS_SCOPE",
            "tax_discount_total_delivery_validation": "NOT_CHECKED",
            "financial_loss_claimed": False}


if __name__ == "__main__":
    try:
        print(json.dumps(audit_all(read_invoices()), ensure_ascii=False))
    except ValueError as exc:
        print(json.dumps({"status": "BLOCKED_INVOICE_READ", "reason": str(exc)}))
        raise SystemExit(2) from None
    except requests.RequestException:
        print(json.dumps({"status": "BLOCKED_INVOICE_READ", "reason": "Network read unavailable"}))
        raise SystemExit(2) from None
