#!/usr/bin/env python3
"""VERICON Module A: bounded, read-only QuickBooks Sandbox invoice line audit.

Checks product line arithmetic and independently reconstructs eligible USD invoice
subtotals, percentage discounts, tax line arithmetic and transaction totals.
Does not verify statutory tax rates, payments, orders, delivery or financial loss.
Missing/unsupported information is BLOCKED, never a fabricated discrepancy.
"""
from __future__ import annotations

import json
import hashlib
from concurrent.futures import ThreadPoolExecutor
import os
import re
import stat
import sys
from pathlib import Path
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from collections import Counter

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


def read_payments() -> list[dict]:
    """Bounded, read-only Payment records. No payment/credit creation permitted."""
    token, realm = get_access_token(load_saved_setup())
    url = f"{SANDBOX_API}/v3/company/{realm}/query"
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    count_data = _get_json(url, "SELECT COUNT(*) FROM Payment", headers)
    count = count_data.get("totalCount")
    if type(count) is not int or count < 0 or count > MAX_INVOICES:
        raise ValueError("Payment count unknown or above controlled batch limit")
    data = _get_json(url, f"SELECT * FROM Payment STARTPOSITION 1 MAXRESULTS {MAX_INVOICES}", headers)
    payments = data.get("Payment", [])
    if not isinstance(payments, list) or len(payments) != count:
        raise ValueError("Payment collection incomplete or changed during read")
    ids = [row.get("Id") for row in payments if isinstance(row, dict)]
    if len(ids) != count or any(not v for v in ids) or len(set(ids)) != count:
        raise ValueError("Payment identifiers missing or ambiguous")
    return payments


def read_credit_memos() -> list[dict]:
    """Read a bounded set of CreditMemo endpoints using the existing QBO GET path."""
    token, realm = get_access_token(load_saved_setup())
    url = f"{SANDBOX_API}/v3/company/{realm}/query"
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    count = _get_json(url, "SELECT COUNT(*) FROM CreditMemo", headers).get("totalCount")
    if type(count) is not int or count < 0 or count > MAX_INVOICES:
        raise ValueError("CreditMemo count unknown or above controlled batch limit")
    rows = _get_json(url, f"SELECT * FROM CreditMemo STARTPOSITION 1 MAXRESULTS {MAX_INVOICES}", headers).get("CreditMemo", [])
    if not isinstance(rows, list) or len(rows) != count:
        raise ValueError("CreditMemo records incomplete or changed during read")
    ids = [str(row.get("Id") or "") for row in rows if isinstance(row, dict)]
    if len(ids) != count or any(not ident for ident in ids) or len(set(ids)) != count:
        raise ValueError("CreditMemo identifiers missing or ambiguous")
    return rows




def read_supplier_documents(entity: str) -> list[dict]:
    """Read a bounded QBO Sandbox purchase-order or vendor-bill collection."""
    if entity not in ("PurchaseOrder", "Bill"):
        raise ValueError("Unsupported supplier document")
    token, realm = get_access_token(load_saved_setup())
    url = f"{SANDBOX_API}/v3/company/{realm}/query"
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    count = _get_json(url, f"SELECT COUNT(*) FROM {entity}", headers).get("totalCount")
    if type(count) is not int or count < 0 or count > MAX_INVOICES:
        raise ValueError("Supplier document count invalid or above limit")
    rows = _get_json(url, f"SELECT * FROM {entity} STARTPOSITION 1 MAXRESULTS {MAX_INVOICES}",
                     headers).get(entity, [])
    if not isinstance(rows, list) or len(rows) != count:
        raise ValueError("Supplier document collection incomplete")
    ids = [str(row.get("Id") or "") for row in rows if isinstance(row, dict)]
    if len(ids) != count or any(not ident for ident in ids) or len(set(ids)) != count:
        raise ValueError("Supplier document identifiers missing or ambiguous")
    return rows


def _supplier_item_lines(txn: dict) -> Counter:
    """Comparable item lines, independent of their order. Never infer SKU from name."""
    rows = txn.get("Line")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Missing item lines")
    result = Counter()
    for row in rows:
        if not isinstance(row, dict) or row.get("DetailType") != "ItemBasedExpenseLineDetail":
            raise ValueError("Unsupported supplier line")
        detail = row.get("ItemBasedExpenseLineDetail")
        if not isinstance(detail, dict) or not isinstance(detail.get("ItemRef"), dict):
            raise ValueError("Unidentified supplier item")
        item_id = str(detail["ItemRef"].get("value") or "")
        if not item_id:
            raise ValueError("Missing supplier item reference")
        qty = number(detail.get("Qty"))
        unit = number(detail.get("UnitPrice"))
        amount = number(row.get("Amount"))
        if qty < 0 or unit < 0 or amount < 0:
            raise ValueError("Negative supplier item values unsupported")
        if abs(qty * unit - amount) > COMPONENT_CENT_TOLERANCE:
            raise ArithmeticError("Supplier line arithmetic needs review")
        result[(item_id, qty, unit, amount)] += 1
    return result


def audit_supplier_po_bills(purchase_orders: list[dict], bills: list[dict]) -> dict:
    """Only compare an explicitly linked single Bill and PurchaseOrder.

    Missing links, partial billing, unsupported lines and other paths do not
    become invented losses. This is NOT a delivery, payment or cross-system audit.
    """
    result = {"status": "PARTIAL_SOURCE_COVERAGE",
              "purchase_order_count": len(purchase_orders), "bill_count": len(bills),
              "linked_pairs": 0, "matched_pairs": 0, "review_pairs": 0,
              "blocked_pairs": 0, "without_bill_link": 0, "pairs": [],
              "delivery_verified": False, "financial_loss_claimed": False,
              "shopify_order_matching": "NOT_CHECKED"}
    bill_index = {str(b.get("Id") or ""): b for b in bills if isinstance(b, dict)}
    if len(bill_index) != len(bills) or "" in bill_index:
        return {**result, "status": "BLOCKED_BILL_INDEX"}
    linked_bill_counts = Counter()
    for po in purchase_orders:
        refs = po.get("LinkedTxn", []) if isinstance(po, dict) else None
        if isinstance(refs, list):
            linked_bill_counts.update(
                str(ref.get("TxnId") or "") for ref in refs
                if isinstance(ref, dict) and ref.get("TxnType") == "Bill"
            )
    for po in purchase_orders:
        if not isinstance(po, dict) or not po.get("Id"):
            return {**result, "status": "BLOCKED_PURCHASE_ORDER_INDEX"}
        refs = po.get("LinkedTxn", [])
        if not isinstance(refs, list) or not all(isinstance(x, dict) for x in refs):
            result["blocked_pairs"] += 1
            result["pairs"].append({"po_id": str(po["Id"]), "status": "BLOCKED_LINK_FORMAT"})
            continue
        bill_links = [str(x.get("TxnId") or "") for x in refs if x.get("TxnType") == "Bill"]
        if not bill_links:
            result["without_bill_link"] += 1
            result["pairs"].append({"po_id": str(po["Id"]),
                                    "status": "NOT_CHECKED_NO_BILL_LINK"})
            continue
        result["linked_pairs"] += 1
        bid = bill_links[0] if len(bill_links) == 1 else None
        status = "BLOCKED_MULTIPLE_BILL_LINKS" if len(bill_links) != 1 or not bid else None
        if status is None and linked_bill_counts[bid] > 1:
            status = "BLOCKED_SHARED_BILL_REFERENCE"
        bill = bill_index.get(bid) if bid else None
        if status is None and not bill:
            status = "BLOCKED_LINKED_BILL_MISSING"
        if status is None:
            vendor_a = (po.get("VendorRef") or {}).get("value")
            vendor_b = (bill.get("VendorRef") or {}).get("value")
            currency_a = (po.get("CurrencyRef") or {}).get("value")
            currency_b = (bill.get("CurrencyRef") or {}).get("value")
            if not vendor_a or vendor_a != vendor_b or not currency_a or currency_a != currency_b:
                status = "BLOCKED_VENDOR_OR_CURRENCY"
        if status is None:
            try:
                po_lines = _supplier_item_lines(po)
                bill_lines = _supplier_item_lines(bill)
                po_total = number(po.get("TotalAmt"))
                bill_total = number(bill.get("TotalAmt"))
                if po_total < 0 or bill_total < 0:
                    status = "BLOCKED_NEGATIVE_TOTAL"
                elif po_lines != bill_lines or abs(po_total - bill_total) > COMPONENT_CENT_TOLERANCE:
                    status = "REVIEW_PO_BILL_DIFFERENCE"
                else:
                    status = "MATCHED_PO_BILL_LINES_AND_TOTAL"
            except ArithmeticError:
                status = "REVIEW_SOURCE_LINE_ARITHMETIC"
            except (ValueError, TypeError, AttributeError):
                status = "BLOCKED_INCOMPLETE_OR_UNSUPPORTED_LINES"
        row = {"po_id": str(po["Id"]), "bill_id": bid, "status": status}
        result["pairs"].append(row)
        if status.startswith("BLOCKED_"):
            result["blocked_pairs"] += 1
        elif status.startswith("REVIEW_"):
            result["review_pairs"] += 1
        else:
            result["matched_pairs"] += 1
    result["status"] = ("NOT_CHECKED_NO_LINKED_PO_BILL_PAIRS" if not result["linked_pairs"]
                        else "REVIEW_PO_BILL_DIFFERENCES" if result["review_pairs"] else
                        "PARTIAL_LINKS_BLOCKED" if result["blocked_pairs"] else
                        "LINKED_PAIRS_MATCH_WITH_UNLINKED_ORDERS" if result["without_bill_link"] else
                        "LINKED_PAIRS_MATCH")
    return result


def audit_payment_links(invoices: list[dict], payments: list[dict], credit_memos: list[dict] | None = None) -> dict:
    """Validate typed invoice-payment edges without confusing credit with cash.

    Invoice.LinkedTxn[Payment] and Payment.Line.LinkedTxn[Invoice] must agree.
    Payment.Line.Amount is the applied amount; Payment.TotalAmt may be zero
    when a credit memo offsets an invoice, so it must not be used as cash proof.
    """
    base = {"status": "BLOCKED_GRAPH_INPUT", "invoice_nodes": len(invoices),
            "payment_nodes": len(payments), "verified_edges": 0,
            "invoices_with_payment_links": 0, "partial_balance_invoice_ids": [],
            "credit_memo_related_payment_ids": [], "invoice_balance_mismatch_ids": [],
            "cash_received_verified": False, "credit_memo_endpoints_verified": False,
            "shopify_order_links_verified": False}
    try:
        invoice_index = {str(x["Id"]): x for x in invoices}
        payment_index = {str(x["Id"]): x for x in payments}
        if (len(invoice_index) != len(invoices) or len(payment_index) != len(payments) or
                any(not key for key in (*invoice_index, *payment_index,))):
            return base
        invoice_edges = set()
        for iid, inv in invoice_index.items():
            if (inv.get("CurrencyRef") or {}).get("value") != "USD":
                return {**base, "status": "BLOCKED_GRAPH_CURRENCY"}
            refs = inv.get("LinkedTxn", [])
            if not isinstance(refs, list):
                return base
            for ref in refs:
                if not isinstance(ref, dict):
                    return base
                if ref.get("TxnType") == "Payment":
                    if not ref.get("TxnId"):
                        return base
                    edge = (iid, str(ref["TxnId"]))
                    if edge in invoice_edges:
                        return {**base, "status": "BLOCKED_DUPLICATE_EDGE"}
                    invoice_edges.add(edge)
        payment_edges = {}
        credit_related = []
        credit_edges = []
        for pid, pay in payment_index.items():
            if (pay.get("CurrencyRef") or {}).get("value") != "USD":
                return {**base, "status": "BLOCKED_GRAPH_CURRENCY"}
            lines = pay.get("Line", [])
            if not isinstance(lines, list):
                return base
            credit_present = False
            for line in lines:
                if not isinstance(line, dict):
                    return base
                refs = line.get("LinkedTxn", [])
                if not isinstance(refs, list):
                    return base
                types = [r.get("TxnType") for r in refs if isinstance(r, dict)]
                if len(types) != len(refs):
                    return base
                if "CreditMemo" in types:
                    if "Invoice" in types:
                        return {**base, "status": "BLOCKED_AMBIGUOUS_ALLOCATION"}
                    credit_present = True
                    if types != ["CreditMemo"] or not refs[0].get("TxnId"):
                        return {**base, "status": "BLOCKED_AMBIGUOUS_CREDIT_LINK"}
                    credit_amount = number(line.get("Amount"))
                    if credit_amount < 0:
                        return {**base, "status": "BLOCKED_NEGATIVE_CREDIT_ALLOCATION"}
                    credit_edges.append((pid, str(refs[0]["TxnId"]), credit_amount))
                if "Invoice" not in types:
                    continue
                # One allocation amount must refer to exactly one invoice.
                if types != ["Invoice"] or not refs[0].get("TxnId"):
                    return {**base, "status": "BLOCKED_AMBIGUOUS_ALLOCATION"}
                iid = str(refs[0]["TxnId"])
                edge = (iid, pid)
                if edge in payment_edges:
                    return {**base, "status": "BLOCKED_DUPLICATE_EDGE"}
                amount = number(line.get("Amount"))
                if amount < 0:
                    return {**base, "status": "BLOCKED_NEGATIVE_ALLOCATION"}
                payment_edges[edge] = amount
            if credit_present:
                credit_related.append(pid)
        if invoice_edges != set(payment_edges):
            return {**base, "status": "BLOCKED_NONRECIPROCAL_LINKS",
                    "invoice_only_edges": len(invoice_edges - set(payment_edges)),
                    "payment_only_edges": len(set(payment_edges) - invoice_edges)}
        if any(iid not in invoice_index or pid not in payment_index for iid, pid in payment_edges):
            return {**base, "status": "BLOCKED_MISSING_GRAPH_NODE"}
        allocated = {iid: Decimal(0) for iid in invoice_index}
        paid_link_counts = {iid: 0 for iid in invoice_index}
        for (iid, pid), amount in payment_edges.items():
            allocated[iid] += amount
            paid_link_counts[iid] += 1
        mismatches = []
        partial = []
        for iid, inv in invoice_index.items():
            total = number(inv.get("TotalAmt"))
            balance = number(inv.get("Balance"))
            if total < 0 or balance < 0 or balance > total:
                return {**base, "status": "BLOCKED_INVALID_INVOICE_BALANCE"}
            if abs(total - balance - allocated[iid]) > COMPONENT_CENT_TOLERANCE:
                mismatches.append(iid)
            if paid_link_counts[iid] and balance > 0:
                partial.append(iid)
        credit_endpoints_verified = False
        if credit_memos is not None and credit_edges:
            memo_index = {str(m.get("Id") or ""): m for m in credit_memos if isinstance(m, dict)}
            if (len(memo_index) != len(credit_memos) or not all(memo_index)):
                return {**base, "status": "BLOCKED_CREDIT_MEMO_INDEX"}
            seen_credit_edges = set()
            allocated_to_credit = {ident: Decimal(0) for ident in memo_index}
            for pid, memo_id, amount in credit_edges:
                edge = (pid, memo_id)
                if edge in seen_credit_edges:
                    return {**base, "status": "BLOCKED_DUPLICATE_CREDIT_LINK"}
                seen_credit_edges.add(edge)
                memo = memo_index.get(memo_id)
                payment = payment_index[pid]
                if not memo or (memo.get("CurrencyRef") or {}).get("value") != "USD":
                    return {**base, "status": "BLOCKED_CREDIT_MEMO_ENDPOINT"}
                customer = (memo.get("CustomerRef") or {}).get("value")
                payment_customer = (payment.get("CustomerRef") or {}).get("value")
                if not customer or customer != payment_customer:
                    return {**base, "status": "BLOCKED_CREDIT_MEMO_CUSTOMER"}
                allocated_to_credit[memo_id] += amount
                if allocated_to_credit[memo_id] - number(memo.get("TotalAmt")) > COMPONENT_CENT_TOLERANCE:
                    return {**base, "status": "BLOCKED_CREDIT_OVERALLOCATION"}
            credit_endpoints_verified = True
        result = {**base, "status": "GRAPH_LINKS_VERIFIED" if not mismatches
                  else "BLOCKED_BALANCE_ALLOCATION_MISMATCH",
                  "verified_edges": len(payment_edges),
                  "invoices_with_payment_links": sum(x > 0 for x in paid_link_counts.values()),
                  "invoices_with_multiple_payment_links": sum(x > 1 for x in paid_link_counts.values()),
                  "partial_balance_invoice_ids": sorted(partial),
                  "credit_memo_related_payment_ids": sorted(credit_related),
                  "credit_memo_endpoints_verified": credit_endpoints_verified,
                  "credit_memo_reference_count": len(credit_edges),
                  "invoice_balance_mismatch_ids": sorted(mismatches)}
        return result
    except (KeyError, TypeError, AttributeError, ValueError):
        return base


def audit_order_invoice_batch(orders: list[dict], invoices: list[dict]) -> dict:
    """Bounded cross-system batch; never treat an unlinked document as matched."""
    blocked = {"status": "BLOCKED_BATCH_INPUT", "verified": False}
    if not isinstance(orders, list) or not 1 <= len(orders) <= 20:
        return blocked
    if not isinstance(invoices, list) or len(invoices) > MAX_INVOICES:
        return blocked
    order_ids = [str(o.get("id") or "") for o in orders if isinstance(o, dict)]
    invoice_ids = [str(inv.get("Id") or "") for inv in invoices if isinstance(inv, dict)]
    if (len(order_ids) != len(orders) or len(set(order_ids)) != len(order_ids)
            or any(not ident.startswith("gid://shopify/Order/") for ident in order_ids)
            or len(invoice_ids) != len(invoices) or any(not ident for ident in invoice_ids)
            or len(set(invoice_ids)) != len(invoice_ids)):
        return blocked
    results = [audit_shopify_invoice_link(order, invoices) for order in orders]
    verified = all(row.get("verified") is True for row in results)
    return {"status": "BATCH_ORDER_INVOICE_VERIFIED" if verified else "REVIEW_BATCH_INCOMPLETE",
            "verified": verified, "orders_checked": len(orders),
            "orders_verified": sum(row.get("verified") is True for row in results),
            "results": results, "bank_settlement_verified": False}


def audit_shopify_invoice_link(order: dict, invoices: list[dict]) -> dict:
    """Fail closed: a matching document number alone is not an order link."""
    name = str(order.get("name") or "")
    order_gid = str(order.get("id") or "")
    shop_total = ((order.get("totalPriceSet") or {}).get("shopMoney") or {})
    base = {"shopify_order": name, "status": "BLOCKED_NO_VERIFIED_ORDER_REFERENCE",
            "verified": False, "same_number_candidates": 0}
    if not name or not order_gid.startswith("gid://shopify/Order/"):
        return {**base, "status": "BLOCKED_INVALID_SHOPIFY_ORDER"}
    doc_number = name.lstrip("#")
    candidates = [inv for inv in invoices if str(inv.get("DocNumber") or "") == doc_number]
    base["same_number_candidates"] = len(candidates)
    if not shop_total.get("currencyCode") or shop_total.get("amount") is None:
        return {**base, "status": "BLOCKED_MISSING_SHOPIFY_AMOUNT"}
    linked = []
    for inv in invoices:
        fields = inv.get("CustomField") or []
        if not isinstance(fields, list):
            return {**base, "status": "BLOCKED_INVALID_QBO_CUSTOM_FIELDS"}
        explicit_links = [str(field.get("StringValue") or "").strip() for field in fields
                          if isinstance(field, dict) and str(field.get("Name") or "").strip().lower()
                          in ("shopify order id", "shopify_order_id")]
        if order_gid in explicit_links or order_gid.split("/")[-1] in explicit_links:
            linked.append(inv)
    if not linked:
        return base
    if len(linked) != 1:
        return {**base, "status": "BLOCKED_MULTIPLE_LINKED_INVOICES", "linked_count": len(linked)}
    inv = linked[0]
    currency = (inv.get("CurrencyRef") or {}).get("value")
    if currency != shop_total["currencyCode"]:
        return {**base, "status": "BLOCKED_LINKED_CURRENCY_MISMATCH"}
    try:
        if abs(number(inv.get("TotalAmt")) - number(shop_total["amount"])) > Decimal("0.01"):
            return {**base, "status": "REVIEW_LINKED_TOTAL_MISMATCH"}
    except ValueError:
        return {**base, "status": "BLOCKED_LINKED_AMOUNT_UNKNOWN"}
    if "lineItems" not in order or "shippingLines" not in order:
        return {**base, "status": "REFERENCE_AND_TOTAL_MATCH_LINE_ITEMS_NOT_VERIFIED"}
    return _audit_pilot_line_items(order, inv, base)


def _audit_pilot_line_items(order: dict, inv: dict, base: dict) -> dict:
    """Exact two-line pilot reconciliation, not a generic shipping mapping."""
    currency = (inv.get("CurrencyRef") or {}).get("value")
    def money(obj: dict) -> Decimal:
        value = ((obj or {}).get("shopMoney") or {})
        if value.get("currencyCode") != currency:
            raise ValueError("Currency mismatch")
        return number(value.get("amount"))
    try:
        products = ((order.get("lineItems") or {}).get("nodes"))
        shipping = ((order.get("shippingLines") or {}).get("nodes"))
        if not isinstance(products, list) or not isinstance(shipping, list):
            return {**base, "status": "BLOCKED_MISSING_ORDER_LINES"}
        if len(products) != 1 or len(shipping) != 1:
            return {**base, "status": "BLOCKED_UNSUPPORTED_ORDER_LINES"}
        p, freight = products[0], shipping[0]
        if p.get("sku") != "VERICON-TEST-001" or freight.get("title") != "Standart":
            return {**base, "status": "BLOCKED_UNRECOGNIZED_PILOT_ITEM"}
        qty = number(p.get("quantity"))
        unit = money(p.get("originalUnitPriceSet"))
        net = money(p.get("discountedTotalSet"))
        delivery = money(freight.get("discountedPriceSet"))
        subtotal = money(order.get("subtotalPriceSet"))
        tax = money(order.get("totalTaxSet"))
        total = money(order.get("totalPriceSet"))
        if qty != 1 or unit <= 0 or net <= 0 or delivery < 0 or subtotal <= 0 or total <= 0:
            return {**base, "status": "BLOCKED_NONPOSITIVE_PILOT_SALE"}
        if qty * unit != net or net != subtotal or net + delivery + tax != total:
            return {**base, "status": "REVIEW_SHOPIFY_COMPONENTS"}
        lines = [line for line in (inv.get("Line") or []) if line.get("DetailType") == "SalesItemLineDetail"]
        unsupported = [line for line in (inv.get("Line") or []) if line.get("DetailType") not in
                       ("SalesItemLineDetail", "SubTotalLineDetail")]
        if len(lines) != 2 or unsupported:
            return {**base, "status": "BLOCKED_QBO_UNSUPPORTED_LINES"}
        actual = {}
        for line in lines:
            detail = line.get("SalesItemLineDetail") or {}
            sku = (detail.get("ItemRef") or {}).get("name")
            if not sku or sku in actual:
                return {**base, "status": "BLOCKED_QBO_DUPLICATE_OR_UNKNOWN_ITEMS"}
            actual[sku] = (number(detail.get("Qty")), number(detail.get("UnitPrice")),
                           number(line.get("Amount")), (detail.get("TaxCodeRef") or {}).get("value"))
        expected = {"VERICON-TEST-001": (qty, unit, net, "NON"),
                    "SHIPPING-STANDARD": (Decimal(1), delivery, delivery, "NON")}
        if actual != expected:
            return {**base, "status": "REVIEW_ORDER_INVOICE_LINE_MISMATCH"}
        recorded_tax = number((inv.get("TxnTaxDetail") or {}).get("TotalTax"))
        if tax != 0 or recorded_tax != tax:
            return {**base, "status": "REVIEW_ORDER_INVOICE_TAX_MISMATCH"}
        if subtotal + delivery + tax != number(inv.get("TotalAmt")):
            return {**base, "status": "REVIEW_ORDER_INVOICE_COMPONENT_TOTAL"}
    except (ValueError, TypeError, AttributeError):
        return {**base, "status": "BLOCKED_INCOMPLETE_ORDER_INVOICE_EVIDENCE"}
    return {**base, "status": "PILOT_ORDER_INVOICE_VERIFIED", "verified": True,
            "invoice_id": str(inv.get("Id")), "line_count": len(lines),
            "currency": currency, "total": str(total),
            "scope": "controlled_shopify_qbo_sandbox_pilot_only"}


def audit_pilot_payment_accounting(order: dict, invoice: dict, link: dict) -> dict:
    """Do not infer real settlement from simulated Shopify checkout payments."""
    base = {"status": "BLOCKED_PAYMENT_EVIDENCE", "settlement_verified": False,
            "real_cash_claimed": False}
    if link.get("verified") is not True or link.get("status") != "PILOT_ORDER_INVOICE_VERIFIED":
        return {**base, "status": "BLOCKED_ORDER_INVOICE_LINK"}
    try:
        currency = (invoice.get("CurrencyRef") or {}).get("value")
        total_money = ((order.get("totalPriceSet") or {}).get("shopMoney") or {})
        if not currency or total_money.get("currencyCode") != currency:
            return {**base, "status": "BLOCKED_PAYMENT_CURRENCY"}
        total = number(total_money.get("amount"))
        invoice_total, balance = number(invoice.get("TotalAmt")), number(invoice.get("Balance"))
        if total <= 0 or invoice_total != total or balance < 0 or balance > invoice_total:
            return {**base, "status": "BLOCKED_INVALID_PAYMENT_TOTALS"}
        transactions = order.get("transactions")
        if not isinstance(transactions, list) or not transactions:
            return {**base, "status": "BLOCKED_MISSING_SHOPIFY_TRANSACTIONS"}
        if any(not isinstance(txn, dict) for txn in transactions):
            return base
        if order.get("test") is not True:
            return {**base, "status": "NOT_CHECKED_NONTEST_PAYMENT_SETTLEMENT"}
        successful = [txn for txn in transactions if txn.get("status") == "SUCCESS"
                      and txn.get("kind") in ("SALE", "CAPTURE")]
        if not successful or any(txn.get("test") is not True for txn in successful):
            return {**base, "status": "BLOCKED_PAYMENT_TEST_CLASSIFICATION"}
        applied = Decimal(0)
        for txn in successful:
            money = ((txn.get("amountSet") or {}).get("shopMoney") or {})
            if money.get("currencyCode") != currency:
                return {**base, "status": "BLOCKED_PAYMENT_CURRENCY"}
            applied += number(money.get("amount"))
        if applied != total:
            return {**base, "status": "REVIEW_TEST_GATEWAY_PAYMENT_TOTAL"}
        linked = invoice.get("LinkedTxn")
        if not isinstance(linked, list):
            return {**base, "status": "BLOCKED_QBO_PAYMENT_LINKS"}
        if order.get("displayFinancialStatus") == "PAID" and balance == invoice_total and not linked:
            return {**base, "status": "TEST_PAID_QBO_UNPAID_EXPECTED",
                    "shopify_test_payment": str(applied), "qbo_outstanding": str(balance),
                    "currency": currency}
        return {**base, "status": "REVIEW_QBO_PAYMENT_RECORDS",
                "shopify_test_payment": str(applied), "qbo_outstanding": str(balance),
                "currency": currency}
    except (ValueError, TypeError, AttributeError):
        return base


def audit_refund_credit_links(order: dict, refunds: list[dict], credits: list[dict]) -> dict:
    """Offline refund/credit reconciliation; never claims bank settlement.

    Normalized refunds require a successful REFUND transaction. Credit memos
    must explicitly reference the Shopify refund ID; equal amounts alone are
    not evidence of a link. This is an offline contract, not an API mapper.
    """
    base = {"status": "BLOCKED_REFUND_EVIDENCE", "verified": False,
            "bank_settlement_verified": False, "real_cash_claimed": False}
    try:
        order_id = str(order.get("id") or "")
        total_set = ((order.get("totalPriceSet") or {}).get("shopMoney") or {})
        currency = total_set.get("currencyCode")
        order_total = number(total_set.get("amount"))
        if not order_id.startswith("gid://shopify/Order/") or not currency or order_total <= 0:
            return {**base, "status": "BLOCKED_INVALID_REFUND_ORDER"}
        if not isinstance(refunds, list) or not isinstance(credits, list):
            return base
        if not refunds and not credits:
            return {**base, "status": "NO_REFUNDS_RECORDED"}
        if order.get("test") is not True:
            return {**base, "status": "NOT_CHECKED_REAL_REFUND_SETTLEMENT"}
        refund_index = {}
        all_transaction_ids = set()
        for refund in refunds:
            rid = str(refund.get("id") or "")
            if not rid.startswith("gid://shopify/Refund/") or rid in refund_index:
                return {**base, "status": "BLOCKED_DUPLICATE_OR_INVALID_REFUND_ID"}
            if refund.get("order_id") != order_id:
                return {**base, "status": "BLOCKED_REFUND_ORDER_LINK"}
            amount = refund.get("amount") or {}
            value = number(amount.get("value"))
            if amount.get("currency") != currency or value <= 0:
                return {**base, "status": "BLOCKED_REFUND_AMOUNT_CURRENCY"}
            transactions = refund.get("transactions")
            if not isinstance(transactions, list) or not transactions:
                return {**base, "status": "BLOCKED_REFUND_TRANSACTION_MISSING"}
            successful = Decimal(0)
            for txn in transactions:
                txn_id = str(txn.get("id") or "")
                if not txn_id or txn_id in all_transaction_ids:
                    return {**base, "status": "BLOCKED_DUPLICATE_REFUND_TRANSACTION"}
                all_transaction_ids.add(txn_id)
                if txn.get("kind") != "REFUND" or txn.get("status") != "SUCCESS" or txn.get("test") is not True:
                    return {**base, "status": "BLOCKED_REFUND_TRANSACTION_NOT_SUCCESSFUL"}
                if txn.get("currency") != currency:
                    return {**base, "status": "BLOCKED_REFUND_TRANSACTION_CURRENCY"}
                tx_amount = number(txn.get("amount"))
                if tx_amount <= 0:
                    return {**base, "status": "BLOCKED_REFUND_TRANSACTION_AMOUNT"}
                successful += tx_amount
            if successful != value:
                return {**base, "status": "REVIEW_REFUND_TRANSACTION_TOTAL"}
            refund_index[rid] = value
        if sum(refund_index.values(), Decimal(0)) > order_total:
            return {**base, "status": "REVIEW_REFUNDS_EXCEED_ORDER"}
        credit_index = {}
        credit_ids = set()
        for credit in credits:
            credit_id = str(credit.get("id") or "")
            refund_id = str(credit.get("shopify_refund_id") or "")
            if not credit_id or credit_id in credit_ids:
                return {**base, "status": "BLOCKED_DUPLICATE_CREDIT_MEMO"}
            credit_ids.add(credit_id)
            if refund_id not in refund_index or refund_id in credit_index:
                return {**base, "status": "BLOCKED_UNLINKED_OR_DUPLICATE_REFUND_CREDIT"}
            amount = number(credit.get("amount"))
            if credit.get("currency") != currency or amount <= 0:
                return {**base, "status": "BLOCKED_CREDIT_AMOUNT_CURRENCY"}
            credit_index[refund_id] = amount
        if set(credit_index) != set(refund_index):
            return {**base, "status": "BLOCKED_MISSING_CREDIT_MEMO"}
        if any(credit_index[rid] != value for rid, value in refund_index.items()):
            return {**base, "status": "REVIEW_REFUND_CREDIT_AMOUNT_MISMATCH"}
        return {**base, "status": "TEST_REFUND_CREDIT_RECORDS_MATCH", "verified": True,
                "refund_count": len(refund_index), "currency": currency,
                "total": str(sum(refund_index.values(), Decimal(0))),
                "scope": "offline_normalized_test_only"}
    except (ValueError, TypeError, AttributeError, KeyError):
        return base


def normalize_refund_credit_api(order: dict, raw_credits: list[dict], invoice: dict | None = None) -> dict:
    """Adapt actual Shopify Refund and QBO CreditMemo read responses, fail closed."""
    base = {"status": "BLOCKED_REFUND_API_MAPPING", "verified": False,
            "bank_settlement_verified": False, "real_cash_claimed": False}
    raw_refunds = order.get("refunds")
    if not isinstance(raw_refunds, list) or not isinstance(raw_credits, list):
        return base
    if len(raw_refunds) > 20 or len(raw_credits) > 100:
        return {**base, "status": "BLOCKED_REFUND_API_LIMIT"}
    if not raw_refunds:
        return {**base, "status": "NO_SHOPIFY_REFUNDS", "shopify_refund_count": 0,
                "qbo_credit_memo_count": len(raw_credits)}
    if not isinstance(invoice, dict):
        return {**base, "status": "BLOCKED_MISSING_LINKED_INVOICE"}
    expected_customer = str((invoice.get("CustomerRef") or {}).get("value") or "")
    order_ref = str(order.get("id") or "")
    fields = invoice.get("CustomField")
    if not expected_customer or not isinstance(fields, list):
        return {**base, "status": "BLOCKED_INVOICE_CUSTOMER_OR_REFERENCE"}
    linked_order_ids = [str(f.get("StringValue") or "").strip() for f in fields
                        if isinstance(f, dict) and str(f.get("Name") or "").strip().lower()
                        in ("shopify order id", "shopify_order_id")]
    if len(linked_order_ids) != 1 or linked_order_ids[0] not in (order_ref, order_ref.split("/")[-1]):
        return {**base, "status": "BLOCKED_INVOICE_CUSTOMER_OR_REFERENCE"}
    try:
        invoice_tax = number((invoice.get("TxnTaxDetail") or {}).get("TotalTax"))
        order_tax_set = (order.get("totalTaxSet") or {}).get("shopMoney") or {}
        order_tax = number(order_tax_set.get("amount"))
        order_currency = ((order.get("totalPriceSet") or {}).get("shopMoney") or {}).get("currencyCode")
        if not order_currency or order_tax_set.get("currencyCode") != order_currency:
            return {**base, "status": "BLOCKED_REFUND_TAX_CURRENCY_UNKNOWN"}
        if invoice_tax != 0 or order_tax != 0:
            return {**base, "status": "NOT_CHECKED_TAXABLE_REFUND_POLICY"}
        refunds = []
        for row in raw_refunds:
            amount = ((row.get("totalRefundedSet") or {}).get("shopMoney") or {})
            connection = row.get("transactions") or {}
            txs = connection.get("nodes")
            page_info = connection.get("pageInfo") or {}
            if page_info.get("hasNextPage") is not False:
                return {**base, "status": "BLOCKED_REFUND_TRANSACTION_PAGINATION"}
            if not isinstance(txs, list) or len(txs) > 20:
                return base
            refunds.append({"id": row.get("id"), "order_id": (row.get("order") or {}).get("id"),
                "amount": {"value": amount.get("amount"), "currency": amount.get("currencyCode")},
                "transactions": [{"id": t.get("id"), "kind": t.get("kind"),
                    "status": t.get("status"), "test": t.get("test"),
                    "currency": ((t.get("amountSet") or {}).get("shopMoney") or {}).get("currencyCode"),
                    "amount": ((t.get("amountSet") or {}).get("shopMoney") or {}).get("amount")}
                    for t in txs]})
        credits = []
        known_refund_ids = {row["id"] for row in refunds}
        for row in raw_credits:
            fields = row.get("CustomField")
            if not isinstance(fields, list):
                return base
            refs = [str(f.get("StringValue") or "").strip() for f in fields
                    if isinstance(f, dict) and str(f.get("Name") or "").strip().lower()
                    in ("shopify refund id", "shopify_refund_id")]
            if len(refs) > 1:
                return {**base, "status": "BLOCKED_AMBIGUOUS_CREDIT_REFUND_FIELD"}
            if not refs:
                continue
            ref = refs[0]
            if ref.isdigit():
                ref = "gid://shopify/Refund/" + ref
            if ref not in known_refund_ids:
                continue
            credit_customer = str((row.get("CustomerRef") or {}).get("value") or "")
            if credit_customer != expected_customer:
                return {**base, "status": "BLOCKED_CREDIT_MEMO_CUSTOMER_MISMATCH"}
            credits.append({"id": row.get("Id"), "shopify_refund_id": ref,
                 "currency": (row.get("CurrencyRef") or {}).get("value"),
                 "amount": row.get("TotalAmt")})
        result = audit_refund_credit_links(order, refunds, credits)
        result["qbo_credit_memo_count"] = len(raw_credits)
        result["qbo_explicit_ref_count"] = len(credits)
        if result.get("verified") is not True:
            return result
        for row in raw_credits:
            fields = row.get("CustomField") or []
            linked_refs = [str(field.get("StringValue") or "").strip() for field in fields
                           if isinstance(field, dict) and str(field.get("Name") or "").strip().lower()
                           in ("shopify refund id", "shopify_refund_id")]
            if not linked_refs:
                continue
            refund_ref = linked_refs[0]
            if refund_ref.isdigit():
                refund_ref = "gid://shopify/Refund/" + refund_ref
            if refund_ref not in known_refund_ids:
                continue
            credit_tax = number((row.get("TxnTaxDetail") or {}).get("TotalTax"))
            if credit_tax != 0:
                return {**base, "status": "REVIEW_CREDIT_MEMO_UNEXPECTED_TAX",
                        "qbo_credit_memo_count": len(raw_credits)}
            lines = row.get("Line")
            if not isinstance(lines, list):
                return {**base, "status": "BLOCKED_CREDIT_MEMO_TAX_LINES_UNKNOWN"}
            item_lines = [line for line in lines if line.get("DetailType") == "SalesItemLineDetail"]
            if not item_lines or any((line.get("SalesItemLineDetail") or {}).get("TaxCodeRef", {}).get("value") != "NON" for line in item_lines):
                return {**base, "status": "REVIEW_CREDIT_MEMO_TAX_CODE",
                        "qbo_credit_memo_count": len(raw_credits)}
        return result
    except (TypeError, ValueError, AttributeError, KeyError):
        return base


def audit_pilot_credit_application(invoice: dict, credit: dict, payment: dict) -> dict:
    """Verify QuickBooks credit application without treating it as cash received."""
    base = {"status": "BLOCKED_CREDIT_APPLICATION_EVIDENCE", "verified": False,
            "cash_received_verified": False, "bank_settlement_verified": False}
    try:
        invoice_id, credit_id = str(invoice.get("Id") or ""), str(credit.get("Id") or "")
        payment_id = str(payment.get("Id") or "")
        currency = (invoice.get("CurrencyRef") or {}).get("value")
        customer = (invoice.get("CustomerRef") or {}).get("value")
        if not all((invoice_id, credit_id, payment_id, currency, customer)):
            return base
        if (currency != (credit.get("CurrencyRef") or {}).get("value") or
                currency != (payment.get("CurrencyRef") or {}).get("value") or
                customer != (credit.get("CustomerRef") or {}).get("value") or
                customer != (payment.get("CustomerRef") or {}).get("value")):
            return {**base, "status": "BLOCKED_CREDIT_APPLICATION_CURRENCY_CUSTOMER"}
        total, balance = number(invoice.get("TotalAmt")), number(invoice.get("Balance"))
        credit_total, credit_balance = number(credit.get("TotalAmt")), number(credit.get("Balance"))
        if (total <= 0 or credit_total <= 0 or balance < 0 or credit_balance != 0 or
                number(payment.get("TotalAmt")) != 0 or number(payment.get("UnappliedAmt")) != 0):
            return {**base, "status": "BLOCKED_CREDIT_APPLICATION_AMOUNTS"}
        refs = invoice.get("LinkedTxn")
        if not isinstance(refs, list) or len(refs) != 1 or refs[0] != {"TxnId": payment_id, "TxnType": "Payment"}:
            return {**base, "status": "BLOCKED_CREDIT_APPLICATION_INVOICE_LINK"}
        lines = payment.get("Line")
        if not isinstance(lines, list) or len(lines) != 2:
            return {**base, "status": "BLOCKED_CREDIT_APPLICATION_LINES"}
        allocations = {}
        for line in lines:
            links = line.get("LinkedTxn")
            if not isinstance(links, list) or len(links) != 1 or not isinstance(links[0], dict):
                return {**base, "status": "BLOCKED_CREDIT_APPLICATION_LINE_REFERENCE"}
            typ, ident = links[0].get("TxnType"), str(links[0].get("TxnId") or "")
            if typ not in ("Invoice", "CreditMemo") or typ in allocations:
                return {**base, "status": "BLOCKED_CREDIT_APPLICATION_DUPLICATE_LINE"}
            allocations[typ] = (ident, number(line.get("Amount")))
        if set(allocations) != {"Invoice", "CreditMemo"} or allocations["Invoice"][0] != invoice_id or allocations["CreditMemo"][0] != credit_id:
            return {**base, "status": "BLOCKED_CREDIT_APPLICATION_WRONG_ENDPOINT"}
        invoice_applied, credit_applied = allocations["Invoice"][1], allocations["CreditMemo"][1]
        if (invoice_applied <= 0 or invoice_applied != credit_applied or
                invoice_applied != credit_total or balance != total - invoice_applied):
            return {**base, "status": "REVIEW_CREDIT_APPLICATION_BALANCE"}
        return {**base, "status": "PILOT_CREDIT_APPLICATION_VERIFIED",
                "verified": True, "applied": str(invoice_applied), "remaining": str(balance),
                "currency": currency, "payment_id": payment_id,
                "scope": "controlled_sandbox_credit_offset_not_cash"}
    except (ValueError, TypeError, AttributeError, KeyError):
        return base


def select_invoice_by_shopify_order(order: dict, invoices: list[dict]) -> dict:
    """Require exactly one explicit Shopify order ID in QBO enhanced custom fields."""
    order_id = str(order.get("id") or "")
    if not order_id.startswith("gid://shopify/Order/") or not order_id.split("/")[-1].isdigit():
        raise ValueError("Invalid Shopify order ID")
    if not isinstance(invoices, list) or len(invoices) > MAX_INVOICES:
        raise ValueError("Unbounded invoice candidates")
    matches = []
    seen = set()
    for invoice in invoices:
        if not isinstance(invoice, dict):
            raise ValueError("Invalid invoice candidate")
        ident = str(invoice.get("Id") or "")
        if not ident or ident in seen:
            raise ValueError("Duplicate or missing invoice ID")
        seen.add(ident)
        fields = invoice.get("CustomField")
        if not isinstance(fields, list):
            raise ValueError("Invoice custom fields missing")
        refs = [str(field.get("StringValue") or "").strip() for field in fields
                if isinstance(field, dict) and str(field.get("Name") or "").strip().lower()
                in ("shopify order id", "shopify_order_id")]
        if len(refs) > 1:
            raise ValueError("Ambiguous invoice order reference")
        if refs and refs[0] in (order_id, order_id.split("/")[-1]):
            matches.append(invoice)
    if len(matches) != 1:
        raise ValueError("Missing or duplicate linked Shopify invoice")
    return matches[0]


def read_try_pilot_invoices() -> list[dict]:
    """Read bounded TRY sandbox invoice details with explicit order references."""
    from qbo_oauth import Config
    vault = Path(__file__).resolve().parent / "private" / "qbo_try_32e0"
    setup = json.loads((vault / "qbo_setup.json").read_text(encoding="utf-8"))
    if setup.get("VERICON_QBO_EXPECTED_REALM") != "9341458641399133":
        raise ValueError("Unexpected TRY sandbox company")
    config = Config(client_id=setup["VERICON_QBO_CLIENT_ID"],
                    client_secret=setup["VERICON_QBO_CLIENT_SECRET"],
                    redirect_uri=setup["VERICON_QBO_REDIRECT_URI"],
                    private_dir=vault, expected_realm="9341458641399133")
    token, realm = get_access_token(config)
    base_url = f"{SANDBOX_API}/v3/company/{realm}"
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    count = _get_json(base_url + "/query", "SELECT COUNT(*) FROM Invoice", headers).get("totalCount")
    if type(count) is not int or count < 0 or count > MAX_INVOICES:
        raise ValueError("TRY sandbox invoice count unknown or above limit")
    if not count:
        raise ValueError("TRY sandbox has no invoices")
    rows = _get_json(base_url + "/query",
                     f"SELECT * FROM Invoice STARTPOSITION 1 MAXRESULTS {count}", headers).get("Invoice")
    if not isinstance(rows, list) or len(rows) != count:
        raise ValueError("TRY sandbox invoice list incomplete")
    ids = [str(row.get("Id") or "") for row in rows if isinstance(row, dict)]
    if len(ids) != count or any(not ident.isdigit() for ident in ids) or len(set(ids)) != count:
        raise ValueError("TRY sandbox invoice IDs missing or duplicate")
    def get_detail(ident: str) -> dict:
        response = requests.get(f"{base_url}/invoice/{ident}",
                                params={"minorversion": "75", "include": "enhancedAllCustomFields"},
                                headers=headers, timeout=20)
        response.raise_for_status()
        body = response.json()
        invoice = body.get("Invoice") if not body.get("Fault") else None
        if not isinstance(invoice, dict) or str(invoice.get("Id")) != ident:
            raise ValueError("TRY sandbox invoice detail incomplete")
        return invoice
    with ThreadPoolExecutor(max_workers=4) as executor:
        detailed = list(executor.map(get_detail, ids))
    return detailed


def read_try_pilot_invoice(order: dict | None = None) -> dict:
    """Keep the existing pilot call; resolve invoice by explicit Shopify ID."""
    if order is None:
        from shopify_read import read_shopify_test_order
        order = read_shopify_test_order()
    return select_invoice_by_shopify_order(order, read_try_pilot_invoices())


def read_try_pilot_credit_memos() -> list[dict]:
    """Read bounded CreditMemo records with enhanced custom fields, no writes."""
    from qbo_oauth import Config
    vault = Path(__file__).resolve().parent / "private" / "qbo_try_32e0"
    setup = json.loads((vault / "qbo_setup.json").read_text(encoding="utf-8"))
    if setup.get("VERICON_QBO_EXPECTED_REALM") != "9341458641399133":
        raise ValueError("Unexpected TRY sandbox company")
    config = Config(client_id=setup["VERICON_QBO_CLIENT_ID"],
                    client_secret=setup["VERICON_QBO_CLIENT_SECRET"],
                    redirect_uri=setup["VERICON_QBO_REDIRECT_URI"],
                    private_dir=vault, expected_realm="9341458641399133")
    token, realm = get_access_token(config)
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    url = f"{SANDBOX_API}/v3/company/{realm}"
    count = _get_json(url + "/query", "SELECT COUNT(*) FROM CreditMemo", headers).get("totalCount")
    if type(count) is not int or count < 0 or count > 25:
        raise ValueError("Pilot CreditMemo count invalid or above limit")
    if not count:
        return []
    rows = _get_json(url + "/query", f"SELECT * FROM CreditMemo STARTPOSITION 1 MAXRESULTS {count}", headers).get("CreditMemo")
    if not isinstance(rows, list) or len(rows) != count:
        raise ValueError("Pilot CreditMemo query incomplete")
    ids = [str(x.get("Id") or "") for x in rows if isinstance(x, dict)]
    if len(ids) != count or any(not v.isdigit() for v in ids) or len(set(ids)) != count:
        raise ValueError("Pilot CreditMemo IDs invalid or ambiguous")
    detailed = []
    for ident in ids:
        response = requests.get(url + "/creditmemo/" + ident,
                                params={"minorversion":"75", "include":"enhancedAllCustomFields"},
                                headers=headers, timeout=20)
        response.raise_for_status()
        body = response.json()
        memo = body.get("CreditMemo") if not body.get("Fault") else None
        if not isinstance(memo, dict) or str(memo.get("Id")) != ident:
            raise ValueError("Pilot CreditMemo detail incomplete")
        detailed.append(memo)
    return detailed


def read_try_pilot_credit_payment(invoice: dict) -> dict:
    """Fetch only the payment referenced by the sandbox pilot invoice."""
    from qbo_oauth import Config
    links = invoice.get("LinkedTxn")
    if not isinstance(links, list) or len(links) != 1 or links[0].get("TxnType") != "Payment":
        raise ValueError("Missing or ambiguous pilot payment")
    payment_id = str(links[0].get("TxnId") or "")
    if not payment_id.isdigit():
        raise ValueError("Invalid pilot payment ID")
    vault = Path(__file__).resolve().parent / "private" / "qbo_try_32e0"
    setup = json.loads((vault / "qbo_setup.json").read_text(encoding="utf-8"))
    if setup.get("VERICON_QBO_EXPECTED_REALM") != "9341458641399133":
        raise ValueError("Unexpected sandbox company")
    config = Config(client_id=setup["VERICON_QBO_CLIENT_ID"],
                    client_secret=setup["VERICON_QBO_CLIENT_SECRET"],
                    redirect_uri=setup["VERICON_QBO_REDIRECT_URI"],
                    private_dir=vault, expected_realm="9341458641399133")
    token, realm = get_access_token(config)
    response = requests.get(f"{SANDBOX_API}/v3/company/{realm}/payment/{payment_id}",
                            headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
                            timeout=20)
    response.raise_for_status()
    data = response.json()
    payment = data.get("Payment") if not data.get("Fault") else None
    if not isinstance(payment, dict) or str(payment.get("Id")) != payment_id:
        raise ValueError("Payment response incomplete or unexpected")
    return payment


def pilot_evidence_fingerprint(order: dict, invoice: dict, credits: list[dict], payment: dict) -> str:
    """Fingerprint financial evidence only; never store customer or token data."""
    def line_projection(line: dict) -> dict:
        detail = line.get("SalesItemLineDetail") or {}
        return {"type": line.get("DetailType"), "amount": line.get("Amount"),
                "item": (detail.get("ItemRef") or {}).get("name"),
                "qty": detail.get("Qty"), "unit_price": detail.get("UnitPrice"),
                "tax_code": (detail.get("TaxCodeRef") or {}).get("value"),
                "linked": line.get("LinkedTxn")}
    data = {
        "order": {"id": order.get("id"), "total": order.get("totalPriceSet"),
                  "subtotal": order.get("subtotalPriceSet"), "tax": order.get("totalTaxSet"),
                  "line_items": order.get("lineItems"), "shipping": order.get("shippingLines"),
                  "refunds": order.get("refunds")},
        "invoice": {"id": invoice.get("Id"), "total": invoice.get("TotalAmt"),
                    "balance": invoice.get("Balance"), "currency": invoice.get("CurrencyRef"),
                    "tax": invoice.get("TxnTaxDetail"), "lines": [line_projection(x) for x in invoice.get("Line", [])],
                    "links": invoice.get("LinkedTxn"), "fields": invoice.get("CustomField")},
        "credits": [{"id": c.get("Id"), "total": c.get("TotalAmt"), "balance": c.get("Balance"),
                     "currency": (c.get("CurrencyRef") or {}).get("value"),
                     "tax": c.get("TxnTaxDetail"), "lines": [line_projection(x) for x in c.get("Line", [])],
                     "fields": c.get("CustomField")} for c in credits],
        "payment": {"id": payment.get("Id"), "total": payment.get("TotalAmt"),
                    "unapplied": payment.get("UnappliedAmt"), "currency": (payment.get("CurrencyRef") or {}).get("value"),
                    "lines": [line_projection(x) for x in payment.get("Line", [])]},
    }
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def audit_pilot_evidence_change(previous: str, current: str, checks: dict) -> dict:
    """A changed observation invalidates an earlier verification until rechecked."""
    if not isinstance(previous, str) or len(previous) != 64 or not isinstance(current, str) or len(current) != 64:
        return {"status": "BLOCKED_MISSING_EVIDENCE_BASELINE", "verified": False}
    if previous != current:
        return {"status": "REVIEW_EVIDENCE_CHANGED_RECHECK_REQUIRED", "verified": False}
    if (checks.get("order_link") is not True or checks.get("refund_link") is not True or
            checks.get("credit_application") is not True or checks.get("tax_classification") is not True):
        return {"status": "REVIEW_CURRENT_CHECKS_INCOMPLETE", "verified": False}
    return {"status": "CURRENT_EVIDENCE_CONSISTENT", "verified": True}


def compare_pilot_baseline(current: str, path: Path | None = None) -> dict:
    """Create one private, immutable initial observation; later reads never overwrite it."""
    if not isinstance(current, str) or re.fullmatch(r"[0-9a-f]{64}", current) is None:
        return {"status": "BLOCKED_INVALID_CURRENT_FINGERPRINT", "verified": False}
    target = path or (Path(__file__).resolve().parent / "private" / "pilot_evidence_baseline.sha256")
    parent = target.parent
    if not parent.is_dir() or parent.is_symlink() or stat.S_IMODE(parent.stat().st_mode) != 0o700:
        return {"status": "BLOCKED_UNSAFE_BASELINE_DIRECTORY", "verified": False}
    if not target.exists() and not target.is_symlink():
        try:
            fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "w", encoding="ascii") as handle:
                handle.write(current + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return {"status": "BASELINE_RECORDED_NOT_VERIFIED", "verified": False}
    if target.is_symlink() or not target.is_file() or stat.S_IMODE(target.stat().st_mode) != 0o600:
        return {"status": "BLOCKED_UNSAFE_BASELINE_FILE", "verified": False}
    rows = target.read_text(encoding="ascii").splitlines()
    valid = (len(rows) in (1, 2) and
             re.fullmatch(r"[0-9a-f]{64}", rows[0]) is not None and
             (len(rows) == 1 or re.fullmatch(r"APPROVED_TAX_CORRECTION [0-9a-f]{64}", rows[1]) is not None))
    if not valid:
        return {"status": "BLOCKED_INVALID_STORED_BASELINE", "verified": False}
    approved = rows[-1].split(" ")[-1]
    if approved != current:
        return {"status": "REVIEW_EVIDENCE_CHANGED_RECHECK_REQUIRED", "verified": False}
    return {"status": "BASELINE_UNCHANGED", "verified": False,
            "historical_correction_recorded": len(rows) == 2}


def accept_pilot_tax_correction(current: str, checks_verified: bool,
                                path: Path | None = None) -> dict:
    """One explicit, read-only-audited correction; preserve the first fingerprint."""
    if checks_verified is not True:
        return {"status": "BLOCKED_UNVERIFIED_CORRECTION", "verified": False}
    if path is None:
        from shopify_read import read_shopify_test_order
        order = read_shopify_test_order()
        invoice = read_try_pilot_invoice()
        credits = read_try_pilot_credit_memos()
        payment = read_try_pilot_credit_payment(invoice)
        report = pilot_summary_report(order, invoice, credits, payment)
        fresh = pilot_evidence_fingerprint(order, invoice, credits, payment)
        if (report.get("current_records_verified") is not True or
                report.get("history") != "REVIEW_EVIDENCE_CHANGED_RECHECK_REQUIRED" or
                current != fresh):
            return {"status": "BLOCKED_UNVERIFIED_LIVE_CORRECTION", "verified": False}
    target = path or (Path(__file__).resolve().parent / "private" / "pilot_evidence_baseline.sha256")
    status = compare_pilot_baseline(current, target)
    if status["status"] != "REVIEW_EVIDENCE_CHANGED_RECHECK_REQUIRED":
        return {"status": "BLOCKED_NO_NEW_CORRECTION_TO_ACCEPT", "verified": False}
    import fcntl
    fd = os.open(target, os.O_RDWR | os.O_NOFOLLOW)
    try:
        with os.fdopen(fd, "r+", encoding="ascii") as file:
            fcntl.flock(file.fileno(), fcntl.LOCK_EX)
            rows = file.read().splitlines()
            if len(rows) != 1 or re.fullmatch(r"[0-9a-f]{64}", rows[0]) is None:
                return {"status": "BLOCKED_CORRECTION_HISTORY_CHANGED", "verified": False}
            file.seek(0, os.SEEK_END)
            file.write("APPROVED_TAX_CORRECTION " + current + "\n")
            file.flush()
            os.fsync(file.fileno())
    except OSError:
        raise
    return {"status": "APPROVED_CORRECTION_RECORDED", "verified": False}


def audit_all(invoices: list[dict], payments: list[dict] | None = None,
              credit_memos: list[dict] | None = None,
              purchase_orders: list[dict] | None = None,
              bills: list[dict] | None = None,
              shopify_order: dict | None = None) -> dict:
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
            "cross_system_order_matching": (audit_shopify_invoice_link(shopify_order, invoices)
                                            if shopify_order is not None else "NOT_CHECKED_NO_SHOPIFY_ORDERS_OR_READ_ORDERS_SCOPE"),
            "tax_law_discount_eligibility_delivery_validation": "NOT_CHECKED",
            "financial_loss_claimed": False,
            "payment_graph": audit_payment_links(invoices, payments, credit_memos) if payments is not None
                             else {"status": "NOT_CHECKED"},
            "supplier_po_bills": audit_supplier_po_bills(purchase_orders, bills)
                                 if purchase_orders is not None and bills is not None
                                 else {"status": "NOT_CHECKED"}}


def pilot_summary_report(order: dict, invoice: dict, credits: list[dict], payment: dict) -> dict:
    """Summarize existing checks without converting a review into a pass."""
    order_link = audit_shopify_invoice_link(order, [invoice])
    refund_link = normalize_refund_credit_api(order, credits, invoice)
    refund_ids = {str(row.get("id") or "").split("/")[-1]
                  for row in (order.get("refunds") or [])}
    linked = [c for c in credits if any(
        str(f.get("Name") or "").strip().lower() in ("shopify refund id", "shopify_refund_id")
        and str(f.get("StringValue") or "").strip().split("/")[-1] in refund_ids
        for f in (c.get("CustomField") or []) if isinstance(f, dict))]
    application = (audit_pilot_credit_application(invoice, linked[0], payment)
                   if len(linked) == 1 else {"status": "BLOCKED_LINKED_CREDIT_AMBIGUITY", "verified": False})
    fingerprint = pilot_evidence_fingerprint(order, invoice, credits, payment)
    history = compare_pilot_baseline(fingerprint)
    current_verified = (order_link.get("verified") is True and refund_link.get("verified") is True
                        and application.get("verified") is True)
    verified = current_verified and history.get("status") == "BASELINE_UNCHANGED"
    return {"scope": "sandbox_pilot_only", "order": order.get("name"),
            "invoice": invoice.get("DocNumber"), "currency": (invoice.get("CurrencyRef") or {}).get("value"),
            "invoice_total": invoice.get("TotalAmt"), "open_balance": invoice.get("Balance"),
            "order_invoice": order_link.get("status"), "refund_credit": refund_link.get("status"),
            "credit_application": application.get("status"), "history": history.get("status"),
            "current_records_verified": current_verified,
            "overall": ("PILOT_VERIFIED" if verified else
                        "CURRENT_VERIFIED_HISTORICAL_CHANGE" if current_verified and
                        history.get("status") == "REVIEW_EVIDENCE_CHANGED_RECHECK_REQUIRED" else
                        "REVIEW_OR_INCOMPLETE"),
            "cash_received_verified": False, "bank_settlement_verified": False}


if __name__ == "__main__" and sys.argv[1:] == ["--pilot-batch"]:
    try:
        from shopify_read import read_shopify_test_orders
        orders = read_shopify_test_orders()
        if not orders:
            print(json.dumps({"status": "NO_TEST_ORDERS", "verified": False}))
        else:
            invoices = read_try_pilot_invoices()
            result = audit_order_invoice_batch(orders, invoices)
            print(json.dumps(result, ensure_ascii=False))
    except (ValueError, PermissionError, requests.RequestException, KeyError, OSError, TypeError):
        print(json.dumps({"status": "BLOCKED_PILOT_BATCH_API_READ", "verified": False}))
        raise SystemExit(2) from None
    raise SystemExit(0)


if __name__ == "__main__" and sys.argv[1:] == ["--pilot-report"]:
    try:
        from shopify_read import read_shopify_test_order
        invoice = read_try_pilot_invoice()
        report = pilot_summary_report(read_shopify_test_order(), invoice,
                                      read_try_pilot_credit_memos(), read_try_pilot_credit_payment(invoice))
        print(json.dumps(report, ensure_ascii=False))
    except (ValueError, PermissionError, requests.RequestException, KeyError, OSError, TypeError):
        print(json.dumps({"status": "BLOCKED_PILOT_REPORT_API_READ", "verified": False}))
        raise SystemExit(2) from None
    raise SystemExit(0)


if __name__ == "__main__" and sys.argv[1:] == ["--pilot-refunds"]:
    try:
        from shopify_read import read_shopify_test_order
        order = read_shopify_test_order()
        credits = read_try_pilot_credit_memos()
        invoice = read_try_pilot_invoice()
        result = normalize_refund_credit_api(order, credits, invoice)
        if result.get("verified") is True:
            refund_ids = {str(row.get("id") or "").split("/")[-1]
                          for row in (order.get("refunds") or [])}
            linked = [c for c in credits if any(
                str(f.get("Name") or "").strip().lower() == "shopify refund id" and
                str(f.get("StringValue") or "").strip().split("/")[-1] in refund_ids
                for f in (c.get("CustomField") or []))]
            if len(linked) == 1:
                result["credit_application"] = audit_pilot_credit_application(
                    invoice, linked[0], read_try_pilot_credit_payment(invoice))
            else:
                result["credit_application"] = {"status": "BLOCKED_LINKED_CREDIT_AMBIGUITY", "verified": False}
        payment = read_try_pilot_credit_payment(invoice)
        result["evidence_fingerprint"] = pilot_evidence_fingerprint(order, invoice, credits, payment)
        result["baseline_comparison"] = compare_pilot_baseline(result["evidence_fingerprint"])
        result["full_current_verification"] = bool(
            result.get("verified") is True and
            (result.get("credit_application") or {}).get("verified") is True)
        if result.get("status") == "REVIEW_CREDIT_MEMO_TAX_CODE":
            result["full_current_verification"] = False
        print(json.dumps(result, ensure_ascii=False))
    except (ValueError, PermissionError, requests.RequestException, KeyError, OSError):
        print(json.dumps({"status":"BLOCKED_REFUND_API_READ", "verified":False}))
        raise SystemExit(2) from None
    raise SystemExit(0)


if __name__ == "__main__" and sys.argv[1:] == ["--pilot-link"]:
    try:
        from shopify_read import read_shopify_test_order
        order = read_shopify_test_order()
        invoice = read_try_pilot_invoice()
        link = audit_shopify_invoice_link(order, [invoice])
        link["payment_accounting"] = audit_pilot_payment_accounting(order, invoice, link)
        print(json.dumps(link, ensure_ascii=False))
    except (ValueError, PermissionError, requests.RequestException, KeyError, OSError):
        print(json.dumps({"status": "BLOCKED_PILOT_API_READ", "verified": False}))
        raise SystemExit(2) from None
    raise SystemExit(0)


if __name__ == "__main__":
    try:
        invoices = read_invoices()
        payments = read_payments()
        credit_memos = read_credit_memos()
        purchase_orders = read_supplier_documents("PurchaseOrder")
        bills = read_supplier_documents("Bill")
        from shopify_read import read_shopify_test_order
        pilot_order = read_shopify_test_order()
        print(json.dumps(audit_all(invoices, payments, credit_memos, purchase_orders, bills,
                                   shopify_order=pilot_order), ensure_ascii=False))
    except ValueError as exc:
        print(json.dumps({"status": "BLOCKED_INVOICE_READ", "reason": str(exc)}))
        raise SystemExit(2) from None
    except requests.RequestException:
        print(json.dumps({"status": "BLOCKED_INVOICE_READ", "reason": "Network read unavailable"}))
        raise SystemExit(2) from None
