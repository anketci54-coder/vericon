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


def graph_invoice(iid, total, balance, payment_ids=(), extra_refs=()):
    return {"Id": str(iid), "CurrencyRef": {"value": "USD"},
            "TotalAmt": total, "Balance": balance,
            "LinkedTxn": [{"TxnType": "Payment", "TxnId": str(pid)} for pid in payment_ids]
                         + list(extra_refs)}


def graph_payment(pid, links, total=None):
    return {"Id": str(pid), "CurrencyRef": {"value": "USD"},
            "TotalAmt": total, "Line": [
                {"Amount": amt, "LinkedTxn": [{"TxnType": kind, "TxnId": str(iid)}]}
                for kind, iid, amt in links]}


def test_graph_one_to_many_partial_and_credit_memo_are_not_cash_proof():
    invoices=[graph_invoice(1, 150, 30, (10, 11)), graph_invoice(2, 100, 0, (12,))]
    payments=[graph_payment(10, [("Invoice",1,40)],40),
              graph_payment(11, [("Invoice",1,80)],80),
              graph_payment(12, [("Invoice",2,100),("CreditMemo",33,100)],0)]
    res=a.audit_payment_links(invoices, payments)
    assert res["status"] == "GRAPH_LINKS_VERIFIED"
    assert res["invoice_nodes"] == 2 and res["payment_nodes"] == 3
    assert res["verified_edges"] == 3
    assert res["invoices_with_multiple_payment_links"] == 1
    assert res["partial_balance_invoice_ids"] == ["1"]
    assert res["credit_memo_related_payment_ids"] == ["12"]
    assert res["cash_received_verified"] is False
    assert res["credit_memo_endpoints_verified"] is False
    assert res["shopify_order_links_verified"] is False


def test_graph_nonreciprocal_or_missing_payment_does_not_claim_success():
    invoice=graph_invoice(1,20,0,(10,))
    assert a.audit_payment_links([invoice],[])["status"] == "BLOCKED_NONRECIPROCAL_LINKS"
    payment=graph_payment(10,[("Invoice",1,20)],20)
    assert a.audit_payment_links([graph_invoice(1,20,0)], [payment])["status"] == "BLOCKED_NONRECIPROCAL_LINKS"


def test_graph_ambiguous_payment_line_fails_closed():
    invoice=graph_invoice(1,20,0,(10,))
    payment=graph_payment(10,[("Invoice",1,20)],20)
    payment["Line"][0]["LinkedTxn"].append({"TxnType":"CreditMemo","TxnId":"33"})
    assert a.audit_payment_links([invoice],[payment])["status"] == "BLOCKED_AMBIGUOUS_ALLOCATION"


def test_graph_mismatched_applied_amount_is_blocked_not_financial_loss():
    invoice=graph_invoice(1,20,1,(10,))
    payment=graph_payment(10,[("Invoice",1,20)],20)
    res=a.audit_payment_links([invoice],[payment])
    assert res["status"] == "BLOCKED_BALANCE_ALLOCATION_MISMATCH"
    assert res["invoice_balance_mismatch_ids"] == ["1"]
    assert res["cash_received_verified"] is False


def test_graph_other_link_types_not_counted_as_payment():
    invoice=graph_invoice(1,50,50,extra_refs=[{"TxnType":"Estimate","TxnId":"90"}])
    res=a.audit_payment_links([invoice],[])
    assert res["status"] == "GRAPH_LINKS_VERIFIED"
    assert res["verified_edges"] == 0
    assert res["invoices_with_payment_links"] == 0


def test_graph_currency_or_duplicate_edges_fail():
    invoice=graph_invoice(1,20,0,(10,))
    payment=graph_payment(10,[("Invoice",1,20)],20)
    payment["CurrencyRef"]["value"]="EUR"
    assert a.audit_payment_links([invoice],[payment])["status"] == "BLOCKED_GRAPH_CURRENCY"
    payment["CurrencyRef"]["value"]="USD"
    invoice["LinkedTxn"].append({"TxnType":"Payment","TxnId":"10"})
    assert a.audit_payment_links([invoice],[payment])["status"] == "BLOCKED_DUPLICATE_EDGE"


def test_graph_payment_reader_get_only_and_rejects_partial_or_duplicate(monkeypatch):
    monkeypatch.setattr(a,"load_saved_setup",lambda: object())
    monkeypatch.setattr(a,"get_access_token",lambda config: ("FAKE","123"))
    calls=[]
    def response(url,query,headers):
        calls.append(query)
        if "COUNT(*)" in query:return {"totalCount":2}
        return {"Payment":[{"Id":"10"},{"Id":"11"}]}
    monkeypatch.setattr(a,"_get_json",response)
    assert len(a.read_payments())==2
    assert calls==["SELECT COUNT(*) FROM Payment", "SELECT * FROM Payment STARTPOSITION 1 MAXRESULTS 100"]
    monkeypatch.setattr(a,"_get_json",lambda url,query,headers:
                        {"totalCount":2} if "COUNT(*)" in query else {"Payment":[{"Id":"10"},{"Id":"10"}]})
    with pytest.raises(ValueError,match="ambiguous"):
        a.read_payments()
    monkeypatch.setattr(a,"_get_json",lambda url,query,headers:
                        {"totalCount":101} if "COUNT(*)" in query else {"Payment":[]})
    with pytest.raises(ValueError,match="limit"):
        a.read_payments()


def test_graph_summary_is_separate_from_invoice_arithmetic():
    invoice=graph_invoice(1,50,30,(10,))
    payment=graph_payment(10,[("Invoice",1,20)],20)
    inv={**invoice, "Line":[sales(qty=10,price=5,amount=50)]}
    summary=a.audit_all([inv],[payment])
    assert summary["payment_graph"]["status"] == "GRAPH_LINKS_VERIFIED"
    assert summary["financial_loss_claimed"] is False
    assert summary["cross_system_order_matching"].startswith("NOT_CHECKED_")
