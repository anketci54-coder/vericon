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


def financial_case(*, amount=15, total=15, subtotal=15, discount=None, tax_amount=0, taxable_base=None, tax_rate=None):
    lines=[sales(qty=3, price=5, amount=amount),
           {"DetailType":"SubTotalLineDetail", "Amount":subtotal}]
    if discount is not None:
        lines.append({"DetailType":"DiscountLineDetail", "Amount":discount,
                      "DiscountLineDetail":{"PercentBased":True,"DiscountPercent":10}})
    tax={"TotalTax":tax_amount}
    if tax_rate is not None:
        tax["TaxLine"]=[{"DetailType":"TaxLineDetail", "Amount":tax_amount,
                         "TaxLineDetail":{"PercentBased":True,"TaxPercent":tax_rate,
                                          "NetAmountTaxable":taxable_base}}]
    return {"Id":"TEST-ID", "CurrencyRef":{"value":"USD"},
            "Line":lines, "TxnTaxDetail":tax, "TotalAmt":total}


def test_financial_components_exact_subtotal_zero_tax_and_total():
    result=a.audit_financial_components(financial_case())
    assert result["subtotal_status"]=="SUBTOTAL_MATCH"
    assert result["discount_status"]=="NO_DISCOUNT"
    assert result["tax_status"]=="NO_TAX_RECORDED"
    assert result["total_status"]=="TOTAL_COMPONENTS_MATCH"
    assert result["verified_tax_rate_lines"]==0


def test_financial_tax_rate_math_and_inclusive_total():
    result=a.audit_financial_components(financial_case(total=16.2,tax_amount=1.2,
                                                         taxable_base=15,tax_rate=8))
    assert result["tax_status"]=="TAX_COMPONENTS_MATCH"
    assert result["verified_tax_rate_lines"]==1
    assert result["total_status"]=="TOTAL_COMPONENTS_MATCH"


def test_discount_percentage_calculation_and_net_total():
    result=a.audit_financial_components(financial_case(discount=1.5,total=13.5))
    assert result["discount_status"]=="DISCOUNT_MATCH"
    assert result["total_status"]=="TOTAL_COMPONENTS_MATCH"


def test_subtotal_without_product_basis_is_blocked_even_if_total_arithmetic_works():
    row=financial_case(total=81,subtotal=75,tax_amount=6,taxable_base=75,tax_rate=8)
    row["Line"]=row["Line"][1:]
    result=a.audit_financial_components(row)
    assert result["subtotal_status"]=="BLOCKED_NO_PRODUCT_BASIS"
    assert result["tax_status"]=="TAX_COMPONENTS_MATCH"
    assert result["total_status"]=="BLOCKED_UNVERIFIED_COMPONENT"


def test_one_cent_difference_is_review_not_silently_accepted():
    result=a.audit_financial_components(financial_case(total=15.01))
    assert result["total_status"]=="REVIEW_TOTAL_AMOUNT"
    result=a.audit_financial_components(financial_case(discount=1.51,total=13.49))
    assert result["discount_status"]=="REVIEW_DISCOUNT_AMOUNT"
    assert result["total_status"]=="BLOCKED_UNVERIFIED_COMPONENT"
    result=a.audit_financial_components(financial_case(tax_amount=1.21,taxable_base=15,tax_rate=8,total=16.21))
    assert result["tax_status"]=="REVIEW_TAX_COMPONENTS"
    assert result["total_status"]=="BLOCKED_UNVERIFIED_COMPONENT"


def test_missing_tax_and_unknown_discount_are_not_matched():
    assert a.audit_financial_components(financial_case(tax_amount=2))["tax_status"]=="BLOCKED_MISSING_TAX_LINES"
    row=financial_case()
    row.pop("TxnTaxDetail")
    assert a.audit_financial_components(row)["total_status"]=="BLOCKED_UNVERIFIED_COMPONENT"
    row=financial_case(discount=2,total=13)
    row["Line"][-1]["DiscountLineDetail"]={"PercentBased":False}
    result=a.audit_financial_components(row)
    assert result["discount_status"]=="BLOCKED_UNSUPPORTED_DISCOUNT"
    assert result["total_status"]=="BLOCKED_UNVERIFIED_COMPONENT"


def test_unsuitable_line_order_and_repeated_subtotals_block():
    row=financial_case()
    row["Line"].insert(0,{"DetailType":"SubTotalLineDetail","Amount":15})
    assert a.audit_financial_components(row)["total_status"]=="BLOCKED_UNSUPPORTED_INVOICE"
    row=financial_case()
    row["Line"].append(sales(qty=1,price=2,amount=2))
    assert a.audit_financial_components(row)["total_status"]=="BLOCKED_UNSUPPORTED_INVOICE"


def test_missing_qty_blocks_line_but_keeps_separate_total_reconstruction():
    row=financial_case()
    row["Line"][0]["SalesItemLineDetail"]={}
    assert a.audit_invoice(row)["status"]=="BLOCKED_INCOMPLETE_PRODUCT_LINE"
    assert a.audit_financial_components(row)["total_status"]=="TOTAL_COMPONENTS_MATCH"


def test_financial_summary_counts_components_without_claiming_legal_tax_correctness():
    rows=[financial_case(total=16.2,tax_amount=1.2,taxable_base=15,tax_rate=8),
          financial_case(discount=1.5,total=13.5)]
    rows[1]["Id"]="TEST-ID-2"
    result=a.audit_all(rows)
    assert result["subtotal_match_invoice_count"]==2
    assert result["discount_match_invoice_count"]==1
    assert result["tax_rate_line_match_count"]==1
    assert result["tax_component_match_invoice_count"]==1
    assert result["no_tax_recorded_invoice_count"]==1
    assert result["total_component_match_invoice_count"]==2
    assert result["tax_law_discount_eligibility_delivery_validation"]=="NOT_CHECKED"
    assert result["financial_loss_claimed"] is False
