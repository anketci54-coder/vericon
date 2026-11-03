#!/usr/bin/env python3
"""VERICON Module A: bounded, read-only QuickBooks Sandbox invoice line audit.

Checks product line arithmetic and independently reconstructs eligible USD invoice
subtotals, percentage discounts, tax line arithmetic and transaction totals.
Does not verify statutory tax rates, payments, orders, delivery or financial loss.
Missing/unsupported information is BLOCKED, never a fabricated discrepancy.
"""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import requests

from qbo_oauth import SANDBOX_API, get_access_token, load_saved_setup

MAX_INVOICES = 100
USD_REVIEW_TOLERANCE = Decimal("0.01")
COMPONENT_CENT_TOLERANCE = Decimal("0.005")
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


def audit_financial_components(inv: dict) -> dict:
    """Review each invoice component without treating internal consistency as real loss.

    A QuickBooks tax line exposes its own taxable base and tax percent; verifying
    their multiplication cannot prove that the taxable base or tax rate is lawful.
    """
    result = {"invoice_id": str(inv.get("Id") or ""),
              "subtotal_status": "BLOCKED_UNSUPPORTED_INVOICE",
              "discount_status": "BLOCKED_UNSUPPORTED_INVOICE",
              "tax_status": "BLOCKED_UNSUPPORTED_INVOICE",
              "total_status": "BLOCKED_UNSUPPORTED_INVOICE",
              "verified_tax_rate_lines": 0}
    lines = inv.get("Line")
    if not result["invoice_id"] or (inv.get("CurrencyRef") or {}).get("value") != "USD":
        return result
    if not isinstance(lines, list) or not lines or not all(isinstance(x, dict) for x in lines):
        return result
    kinds = [x.get("DetailType") for x in lines]
    valid = {"SalesItemLineDetail", "SubTotalLineDetail", "DiscountLineDetail"}
    if any(kind not in valid for kind in kinds):
        return result
    sales = [x for x in lines if x["DetailType"] == "SalesItemLineDetail"]
    subtotals = [x for x in lines if x["DetailType"] == "SubTotalLineDetail"]
    discounts = [x for x in lines if x["DetailType"] == "DiscountLineDetail"]
    # Limit to observed single-subtotal invoices; complex line grouping is unknown.
    if len(subtotals) != 1 or len(discounts) > 1:
        return result
    sub_idx = kinds.index("SubTotalLineDetail")
    if (any(x != "SalesItemLineDetail" for x in kinds[:sub_idx]) or
            any(x != "DiscountLineDetail" for x in kinds[sub_idx + 1:])):
        return result
    try:
        subtotal = number(subtotals[0].get("Amount"))
        line_sum = sum((number(x.get("Amount")) for x in sales), Decimal(0))
    except ValueError:
        result["subtotal_status"] = "BLOCKED_MISSING_LINE_AMOUNT"
        return result
    if not sales:
        result["subtotal_status"] = "BLOCKED_NO_PRODUCT_BASIS"
    elif abs(line_sum - subtotal) > COMPONENT_CENT_TOLERANCE:
        result["subtotal_status"] = "REVIEW_SUBTOTAL_AMOUNT"
    else:
        result["subtotal_status"] = "SUBTOTAL_MATCH"

    discount_amount = Decimal(0)
    if not discounts:
        result["discount_status"] = "NO_DISCOUNT"
    elif result["subtotal_status"] == "SUBTOTAL_MATCH":
        detail = discounts[0].get("DiscountLineDetail")
        if isinstance(detail, dict) and detail.get("PercentBased") is True:
            try:
                pct = number(detail.get("DiscountPercent"))
                discount_amount = number(discounts[0].get("Amount"))
                if pct < 0 or pct > 100 or discount_amount < 0:
                    raise ValueError("Discount outside supported range")
                expected = (subtotal * pct / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                result["discount_status"] = ("DISCOUNT_MATCH" if abs(discount_amount - expected)
                                             <= COMPONENT_CENT_TOLERANCE else "REVIEW_DISCOUNT_AMOUNT")
            except ValueError:
                result["discount_status"] = "BLOCKED_INVALID_DISCOUNT"
        else:
            result["discount_status"] = "BLOCKED_UNSUPPORTED_DISCOUNT"
    else:
        result["discount_status"] = "BLOCKED_SUBTOTAL_BASIS"

    tax = inv.get("TxnTaxDetail")
    tax_amount = None
    if isinstance(tax, dict) and "TotalTax" in tax:
        try:
            tax_amount = number(tax["TotalTax"])
            tax_lines = tax.get("TaxLine", [])
            if not isinstance(tax_lines, list):
                raise ValueError("Bad tax line list")
            if not tax_lines:
                result["tax_status"] = ("NO_TAX_RECORDED" if tax_amount == 0
                                        else "BLOCKED_MISSING_TAX_LINES")
            else:
                summed = Decimal(0)
                review_rate = False
                for tax_line in tax_lines:
                    if not isinstance(tax_line, dict):
                        raise ValueError("Bad tax line")
                    detail = tax_line.get("TaxLineDetail")
                    if not isinstance(detail, dict) or detail.get("PercentBased") is not True:
                        raise ValueError("Unsupported tax rate detail")
                    amount = number(tax_line.get("Amount"))
                    base = number(detail.get("NetAmountTaxable"))
                    rate = number(detail.get("TaxPercent"))
                    if base < 0 or rate < 0 or rate > 100:
                        raise ValueError("Invalid tax base or rate")
                    expected = (base * rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    review_rate |= abs(expected - amount) > COMPONENT_CENT_TOLERANCE
                    summed += amount
                    result["verified_tax_rate_lines"] += int(abs(expected - amount) <= COMPONENT_CENT_TOLERANCE)
                result["tax_status"] = ("REVIEW_TAX_COMPONENTS" if review_rate or
                                        abs(summed - tax_amount) > COMPONENT_CENT_TOLERANCE
                                        else "TAX_COMPONENTS_MATCH")
        except ValueError:
            result["tax_status"] = "BLOCKED_INVALID_TAX_DETAIL"
    else:
        result["tax_status"] = "BLOCKED_MISSING_TAX_DETAIL"

    if (result["subtotal_status"] == "SUBTOTAL_MATCH" and
        result["discount_status"] in ("NO_DISCOUNT", "DISCOUNT_MATCH") and
        result["tax_status"] in ("NO_TAX_RECORDED", "TAX_COMPONENTS_MATCH")):
        try:
            recorded_total = number(inv.get("TotalAmt"))
        except ValueError:
            result["total_status"] = "BLOCKED_MISSING_TOTAL"
        else:
            calculated = subtotal - discount_amount + tax_amount
            result["total_status"] = ("TOTAL_COMPONENTS_MATCH" if
                                      abs(recorded_total - calculated) <= COMPONENT_CENT_TOLERANCE
                                      else "REVIEW_TOTAL_AMOUNT")
    else:
        result["total_status"] = "BLOCKED_UNVERIFIED_COMPONENT"
    return result


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
    financial = [audit_financial_components(inv) for inv in invoices]
    blocked = [r["invoice_id"] for r in results if r["status"].startswith("BLOCKED_")]
    review = [r["invoice_id"] for r in results if r["status"].startswith("REVIEW_")]
    return {"source": "quickbooks_sandbox_live_read", "invoice_count": len(invoices),
            "line_amounts_checked": sum(r["checked_product_lines"] for r in results),
            "verified_invoice_count": sum(r["status"] == "LINE_AMOUNTS_MATCH" for r in results),
            "review_invoice_count": len(review), "blocked_invoice_count": len(blocked),
            "blocked_invoice_ids": blocked, "review_invoice_ids": review,
            "checked_fields": "USD sales line arithmetic and supported subtotal/discount/tax/total internal arithmetic",
            "subtotal_match_invoice_count": sum(r["subtotal_status"] == "SUBTOTAL_MATCH" for r in financial),
            "discount_match_invoice_count": sum(r["discount_status"] == "DISCOUNT_MATCH" for r in financial),
            "tax_rate_line_match_count": sum(r["verified_tax_rate_lines"] for r in financial),
            "tax_component_match_invoice_count": sum(r["tax_status"] == "TAX_COMPONENTS_MATCH" for r in financial),
            "no_tax_recorded_invoice_count": sum(r["tax_status"] == "NO_TAX_RECORDED" for r in financial),
            "total_component_match_invoice_count": sum(r["total_status"] == "TOTAL_COMPONENTS_MATCH" for r in financial),
            "total_review_invoice_ids": [r["invoice_id"] for r in financial if r["total_status"].startswith("REVIEW_")],
            "total_blocked_invoice_ids": [r["invoice_id"] for r in financial if r["total_status"].startswith("BLOCKED_")],
            "subtotal_review_invoice_ids": [r["invoice_id"] for r in financial if r["subtotal_status"].startswith("REVIEW_")],
            "discount_review_invoice_ids": [r["invoice_id"] for r in financial if r["discount_status"].startswith("REVIEW_")],
            "tax_review_invoice_ids": [r["invoice_id"] for r in financial if r["tax_status"].startswith("REVIEW_")],
            "cross_system_order_matching": "NOT_CHECKED_NO_SHOPIFY_ORDERS_OR_READ_ORDERS_SCOPE",
            "tax_law_discount_eligibility_delivery_validation": "NOT_CHECKED",
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
