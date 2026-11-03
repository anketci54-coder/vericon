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


def audit_all(invoices: list[dict], payments: list[dict] | None = None,
              credit_memos: list[dict] | None = None,
              purchase_orders: list[dict] | None = None,
              bills: list[dict] | None = None) -> dict:
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
            "financial_loss_claimed": False,
            "payment_graph": audit_payment_links(invoices, payments, credit_memos) if payments is not None
                             else {"status": "NOT_CHECKED"},
            "supplier_po_bills": audit_supplier_po_bills(purchase_orders, bills)
                                 if purchase_orders is not None and bills is not None
                                 else {"status": "NOT_CHECKED"}}


if __name__ == "__main__":
    try:
        invoices = read_invoices()
        payments = read_payments()
        credit_memos = read_credit_memos()
        purchase_orders = read_supplier_documents("PurchaseOrder")
        bills = read_supplier_documents("Bill")
        print(json.dumps(audit_all(invoices, payments, credit_memos, purchase_orders, bills), ensure_ascii=False))
    except ValueError as exc:
        print(json.dumps({"status": "BLOCKED_INVOICE_READ", "reason": str(exc)}))
        raise SystemExit(2) from None
    except requests.RequestException:
        print(json.dumps({"status": "BLOCKED_INVOICE_READ", "reason": "Network read unavailable"}))
        raise SystemExit(2) from None
