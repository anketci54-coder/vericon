"""Module A invoice arithmetic regression tests; no real API writes."""
import ast
from pathlib import Path

import pytest

import invoice_audit as a


def invoice(*lines, currency="USD"):
    return {"Id": "I-1", "CurrencyRef": {"value": currency}, "Line": list(lines)}


def sales(qty=3, price=5, amount=15):
    return {"DetailType": "SalesItemLineDetail", "Amount": amount,
            "SalesItemLineDetail": {"Qty": qty, "UnitPrice": price}}


def test_line_amount_matches_and_does_not_duplicate_subtotal():
    row = invoice(sales(), {"DetailType": "SubTotalLineDetail", "Amount": 15})
    result = a.audit_invoice(row)
    assert result["status"] == "LINE_AMOUNTS_MATCH"
    assert result["checked_product_lines"] == 1
    assert result["review_product_lines"] == 0


def test_actual_line_amount_mismatch_is_review_not_loss():
    result = a.audit_invoice(invoice(sales(amount=13)))
    assert result["status"] == "REVIEW_LINE_AMOUNT"
    assert result["review_product_lines"] == 1


def test_missing_item_and_totals_only_are_blocked():
    result = a.audit_invoice(invoice({"DetailType": "SubTotalLineDetail", "Amount": 75}))
    assert result["status"] == "BLOCKED_NO_PRODUCT_LINES"
    assert result["checked_product_lines"] == 0


def test_missing_or_bad_fields_block_without_guessing():
    for line in (sales(qty=None),sales(price=None),sales(amount=None),sales(qty="NaN"),
                 {"DetailType": "UnknownFutureType", "Amount": 5}):
        assert a.audit_invoice(invoice(line))["status"].startswith("BLOCKED_")
    assert a.audit_invoice(invoice(sales(),currency="EUR"))["status"] == "BLOCKED_INVALID_INVOICE"


def test_batch_summary_does_not_claim_full_invoice_or_customer_error():
    result=a.audit_all([invoice(sales()),{"Id":"I-2","CurrencyRef":{"value":"USD"},
                                         "Line":[{"DetailType":"SubTotalLineDetail","Amount":75}]}])
    assert result["invoice_count"] == 2
    assert result["verified_invoice_count"] == 1
    assert result["blocked_invoice_count"] == 1
    assert result["review_invoice_count"] == 0
    assert result["financial_loss_claimed"] is False


def test_guard_invoice_reader_only_uses_get_and_oauth_read():
    tree=ast.parse(Path(a.__file__).read_text(encoding="utf-8"))
    api_calls=[(n.func.value.id,n.func.attr) for n in ast.walk(tree)
               if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
               and isinstance(n.func.value,ast.Name) and n.func.value.id=="requests"]
    assert api_calls == [("requests","get")]


def test_reader_blocks_incomplete_counts_and_duplicate_records(monkeypatch):
    monkeypatch.setattr(a, "get_access_token", lambda config: ("FAKE", "123"))
    monkeypatch.setattr(a, "load_saved_setup", lambda: object())
    def stub(url, query, headers):
        if "COUNT(*)" in query:
            return {"totalCount": 2}
        return {"Invoice": [{"Id":"A"},{"Id":"A"}]}
    monkeypatch.setattr(a, "_get_json",stub)
    with pytest.raises(ValueError,match="ambiguous"):
        a.read_invoices()
    monkeypatch.setattr(a,"_get_json", lambda url,query,headers:
                        {"totalCount": 101} if "COUNT(*)" in query else {"Invoice":[]})
    with pytest.raises(ValueError,match="limit"):
        a.read_invoices()
