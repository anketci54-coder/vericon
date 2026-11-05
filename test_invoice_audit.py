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
    assert api_calls == [("requests","get"), ("requests","get")]


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


def test_graph_credit_endpoint_validated_but_not_cash_claim():
    i=graph_invoice(71,205,0,(74,72))
    i["CustomerRef"]={"value":"CUSTOMER-1"}
    p=graph_payment(74,[("Invoice",71,100),("CreditMemo",73,100)],0)
    p["CustomerRef"]={"value":"CUSTOMER-1"}
    p2=graph_payment(72,[("Invoice",71,105)],105)
    p2["CustomerRef"]={"value":"CUSTOMER-1"}
    memo={"Id":"73","CurrencyRef":{"value":"USD"},
          "CustomerRef":{"value":"CUSTOMER-1"},"TotalAmt":100,"Balance":0}
    before=a.audit_payment_links([i],[p,p2])
    assert before["status"]=="GRAPH_LINKS_VERIFIED"
    assert before["credit_memo_endpoints_verified"] is False
    result=a.audit_payment_links([i],[p,p2],[memo])
    assert result["status"]=="GRAPH_LINKS_VERIFIED"
    assert result["credit_memo_reference_count"]==1
    assert result["credit_memo_endpoints_verified"] is True
    assert result["cash_received_verified"] is False
    assert result["shopify_order_links_verified"] is False


def test_graph_credit_endpoint_absent_or_wrong_customer_blocks():
    i=graph_invoice(71,100,0,(74,))
    p=graph_payment(74,[("Invoice",71,100),("CreditMemo",73,100)],0)
    p["CustomerRef"]={"value":"C1"}
    assert a.audit_payment_links([i],[p],[])["status"]=="BLOCKED_CREDIT_MEMO_ENDPOINT"
    memo={"Id":"73","CurrencyRef":{"value":"USD"},"CustomerRef":{"value":"C2"},"TotalAmt":100}
    assert a.audit_payment_links([i],[p],[memo])["status"]=="BLOCKED_CREDIT_MEMO_CUSTOMER"
    memo["CustomerRef"]={"value":"C1"}
    memo["TotalAmt"]=50
    assert a.audit_payment_links([i],[p],[memo])["status"]=="BLOCKED_CREDIT_OVERALLOCATION"


def test_credit_reader_rejects_partial_and_duplicate_records(monkeypatch):
    monkeypatch.setattr(a,"load_saved_setup",lambda: object())
    monkeypatch.setattr(a,"get_access_token",lambda config:("FAKE","123"))
    calls=[]
    def read(url,query,headers):
        calls.append(query)
        return {"totalCount":2} if "COUNT(*)" in query else {"CreditMemo":[{"Id":"73"},{"Id":"74"}]}
    monkeypatch.setattr(a,"_get_json",read)
    assert len(a.read_credit_memos())==2
    assert calls==["SELECT COUNT(*) FROM CreditMemo", "SELECT * FROM CreditMemo STARTPOSITION 1 MAXRESULTS 100"]
    monkeypatch.setattr(a,"_get_json",lambda url,query,headers:
                        {"totalCount":2} if "COUNT(*)" in query else {"CreditMemo":[{"Id":"73"},{"Id":"73"}]})
    with pytest.raises(ValueError,match="ambiguous"):
        a.read_credit_memos()



def supplier_txn(identity, *, bill_link=None, item="11", qty=8, unit=10, vendor="46",
                 currency="USD", total=None):
    amount=qty*unit
    txn={"Id":str(identity),"VendorRef":{"value":vendor},
         "CurrencyRef":{"value":currency},
         "TotalAmt":amount if total is None else total,
         "Line":[{"DetailType":"ItemBasedExpenseLineDetail","Amount":amount,
                  "ItemBasedExpenseLineDetail":{"ItemRef":{"value":str(item)},
                                                 "Qty":qty,"UnitPrice":unit}}]}
    if bill_link is not None:
        txn["LinkedTxn"]=[{"TxnType":"Bill","TxnId":str(bill_link)}]
    return txn


def test_supplier_po_bill_exact_link_is_verified_without_loss_claim():
    p=supplier_txn(125,bill_link=126)
    b=supplier_txn(126)
    res=a.audit_supplier_po_bills([p],[b])
    assert res["matched_pairs"]==1
    assert res["review_pairs"]==0
    assert res["pairs"][0]["status"]=="MATCHED_PO_BILL_LINES_AND_TOTAL"
    assert res["financial_loss_claimed"] is False
    assert res["delivery_verified"] is False
    assert res["shopify_order_matching"]=="NOT_CHECKED"


def test_supplier_po_bill_different_qty_or_total_is_review_not_loss():
    p=supplier_txn(125,bill_link=126)
    b=supplier_txn(126,qty=7)
    res=a.audit_supplier_po_bills([p],[b])
    assert res["review_pairs"]==1
    assert res["financial_loss_claimed"] is False
    b=supplier_txn(126,total=81)
    assert a.audit_supplier_po_bills([p],[b])["review_pairs"]==1


def test_supplier_po_bill_unknown_links_never_invent_error():
    p=supplier_txn(125)
    p["LinkedTxn"]=[{"TxnType":"Purchase","TxnId":"115"}]
    res=a.audit_supplier_po_bills([p],[])
    assert res["linked_pairs"]==0
    assert res["review_pairs"]==0
    assert res["pairs"][0]["status"]=="NOT_CHECKED_NO_BILL_LINK"
    p["LinkedTxn"]=[{"TxnType":"Bill","TxnId":"999"}]
    assert a.audit_supplier_po_bills([p],[])["blocked_pairs"]==1
    p["LinkedTxn"]=[{"TxnType":"Bill","TxnId":"126"},{"TxnType":"Bill","TxnId":"127"}]
    assert a.audit_supplier_po_bills([p],[])["blocked_pairs"]==1


def test_supplier_po_bill_vendor_currency_or_line_unknown_blocks():
    po=supplier_txn(125,bill_link=126)
    assert a.audit_supplier_po_bills([po],[supplier_txn(126,vendor="47")])["blocked_pairs"]==1
    assert a.audit_supplier_po_bills([po],[supplier_txn(126,currency="EUR")])["blocked_pairs"]==1
    wrong=supplier_txn(126)
    del wrong["Line"][0]["ItemBasedExpenseLineDetail"]["Qty"]
    assert a.audit_supplier_po_bills([po],[wrong])["blocked_pairs"]==1
    wrong=supplier_txn(126)
    wrong["Line"][0]["Amount"]=81
    assert a.audit_supplier_po_bills([po],[wrong])["review_pairs"]==1


def test_supplier_po_bill_reader_bound_and_get_only(monkeypatch):
    monkeypatch.setattr(a,"load_saved_setup",lambda:object())
    monkeypatch.setattr(a,"get_access_token",lambda cfg:("FAKE","123"))
    queries=[]
    def getter(url,query,headers):
        queries.append(query)
        return {"totalCount":1} if "COUNT(*)" in query else {"Bill":[{"Id":"126"}]}
    monkeypatch.setattr(a,"_get_json",getter)
    assert len(a.read_supplier_documents("Bill"))==1
    assert queries==["SELECT COUNT(*) FROM Bill",
                     "SELECT * FROM Bill STARTPOSITION 1 MAXRESULTS 100"]
    with pytest.raises(ValueError,match="Unsupported"):
        a.read_supplier_documents("Invoice")
    monkeypatch.setattr(a,"_get_json",lambda url,query,headers:
                        {"totalCount":2} if "COUNT(*)" in query else
                        {"Bill":[{"Id":"126"},{"Id":"126"}]})
    with pytest.raises(ValueError,match="ambiguous"):
        a.read_supplier_documents("Bill")


def test_supplier_po_bill_summary_separate_from_payments():
    r=a.audit_all([invoice(sales())], purchase_orders=[supplier_txn(125,bill_link=126)],
                  bills=[supplier_txn(126)])
    assert r["supplier_po_bills"]["matched_pairs"]==1
    assert r["payment_graph"]["status"]=="NOT_CHECKED"
    assert r["financial_loss_claimed"] is False



def test_supplier_po_bill_no_link_is_not_success():
    result=a.audit_supplier_po_bills([supplier_txn(45)],[])
    assert result["status"]=="NOT_CHECKED_NO_LINKED_PO_BILL_PAIRS"
    assert result["matched_pairs"]==0


def test_supplier_po_bill_shared_reference_does_not_count_matches():
    p1=supplier_txn(125,bill_link=126)
    p2=supplier_txn(130,bill_link=126)
    result=a.audit_supplier_po_bills([p1,p2],[supplier_txn(126)])
    assert result["status"]=="PARTIAL_LINKS_BLOCKED"
    assert result["matched_pairs"]==0
    assert result["blocked_pairs"]==2
    assert all(row["status"]=="BLOCKED_SHARED_BILL_REFERENCE" for row in result["pairs"])


def test_shopify_order_number_is_not_a_verified_invoice_reference():
    order={"id":"gid://shopify/Order/123", "name":"#1001",
           "totalPriceSet":{"shopMoney":{"amount":"216", "currencyCode":"TRY"}}}
    inv={"DocNumber":"1001", "CurrencyRef":{"value":"USD"}, "TotalAmt":108}
    result=a.audit_shopify_invoice_link(order,[inv])
    assert result["status"]=="BLOCKED_NO_VERIFIED_ORDER_REFERENCE"
    assert result["same_number_candidates"]==1
    assert result["verified"] is False


def test_explicit_shopify_reference_with_wrong_currency_blocks():
    order={"id":"gid://shopify/Order/123", "name":"#1001",
           "totalPriceSet":{"shopMoney":{"amount":"216", "currencyCode":"TRY"}}}
    inv={"DocNumber":"2002", "CurrencyRef":{"value":"USD"}, "TotalAmt":216,
         "CustomField":[{"Name":"Shopify Order ID", "StringValue":"123"}]}
    result=a.audit_shopify_invoice_link(order,[inv])
    assert result["status"]=="BLOCKED_LINKED_CURRENCY_MISMATCH"
    assert result["verified"] is False


def test_linked_invoice_same_currency_total_still_not_fully_verified():
    order={"id":"gid://shopify/Order/123", "name":"#1001",
           "totalPriceSet":{"shopMoney":{"amount":"216", "currencyCode":"TRY"}}}
    inv={"DocNumber":"2002", "CurrencyRef":{"value":"TRY"}, "TotalAmt":216,
         "CustomField":[{"Name":"Shopify Order ID", "StringValue":"123"}]}
    result=a.audit_shopify_invoice_link(order,[inv])
    assert result["status"]=="REFERENCE_AND_TOTAL_MATCH_LINE_ITEMS_NOT_VERIFIED"
    assert result["verified"] is False


def test_pilot_order_line_checks_fail_closed_on_bad_data():
    from copy import deepcopy
    order={"id":"gid://shopify/Order/123", "name":"#1001",
           "subtotalPriceSet":{"shopMoney":{"amount":"100", "currencyCode":"TRY"}},
           "totalTaxSet":{"shopMoney":{"amount":"0", "currencyCode":"TRY"}},
           "totalPriceSet":{"shopMoney":{"amount":"216", "currencyCode":"TRY"}},
           "lineItems":{"nodes":[{"sku":"VERICON-TEST-001","quantity":1,
             "originalUnitPriceSet":{"shopMoney":{"amount":"100", "currencyCode":"TRY"}},
             "discountedTotalSet":{"shopMoney":{"amount":"100", "currencyCode":"TRY"}}}]},
           "shippingLines":{"nodes":[{"title":"Standart",
             "discountedPriceSet":{"shopMoney":{"amount":"116", "currencyCode":"TRY"}}}]}}
    inv={"Id":"145","DocNumber":"1038","CurrencyRef":{"value":"TRY"},
         "TotalAmt":216,"TxnTaxDetail":{"TotalTax":0},
         "CustomField":[{"Name":"Shopify Order ID","StringValue":"123"}],
         "Line":[{"DetailType":"SalesItemLineDetail","Amount":100,
                   "SalesItemLineDetail":{"ItemRef":{"name":"VERICON-TEST-001"},
                                           "Qty":1,"UnitPrice":100,"TaxCodeRef":{"value":"NON"}}},
                 {"DetailType":"SalesItemLineDetail","Amount":116,
                   "SalesItemLineDetail":{"ItemRef":{"name":"SHIPPING-STANDARD"},
                                           "Qty":1,"UnitPrice":116,"TaxCodeRef":{"value":"NON"}}}]}
    good=a.audit_shopify_invoice_link(order,[inv])
    assert good["status"]=="PILOT_ORDER_INVOICE_VERIFIED" and good["verified"] is True
    q=deepcopy(inv);q["Line"][0]["SalesItemLineDetail"]["Qty"]=2
    assert a.audit_shopify_invoice_link(order,[q])["verified"] is False
    q=deepcopy(inv);q["Line"][1]["Amount"]=117
    assert a.audit_shopify_invoice_link(order,[q])["verified"] is False
    q=deepcopy(inv);q["TxnTaxDetail"]["TotalTax"]=17.28
    assert a.audit_shopify_invoice_link(order,[q])["verified"] is False
    q=deepcopy(inv);q["Line"].append(deepcopy(q["Line"][0]))
    assert a.audit_shopify_invoice_link(order,[q])["verified"] is False
    q=deepcopy(order);q["shippingLines"]["nodes"][0]["title"]="Unknown"
    assert a.audit_shopify_invoice_link(q,[inv])["verified"] is False
    q=deepcopy(order);r=deepcopy(inv)
    q["subtotalPriceSet"]["shopMoney"]["amount"]="-100"
    q["totalPriceSet"]["shopMoney"]["amount"]="16"
    q["lineItems"]["nodes"][0]["originalUnitPriceSet"]["shopMoney"]["amount"]="-100"
    q["lineItems"]["nodes"][0]["discountedTotalSet"]["shopMoney"]["amount"]="-100"
    r["TotalAmt"]=16
    r["Line"][0]["Amount"]=-100
    r["Line"][0]["SalesItemLineDetail"]["UnitPrice"]=-100
    assert a.audit_shopify_invoice_link(q,[r])["status"]=="BLOCKED_NONPOSITIVE_PILOT_SALE"


def test_pilot_payment_is_not_real_cash_or_bank_settlement():
    from copy import deepcopy
    order={"test":True,"displayFinancialStatus":"PAID",
           "totalPriceSet":{"shopMoney":{"amount":"216","currencyCode":"TRY"}},
           "transactions":[{"test":True,"kind":"SALE","status":"SUCCESS",
                            "amountSet":{"shopMoney":{"amount":"216","currencyCode":"TRY"}}}]}
    inv={"TotalAmt":216,"Balance":216,"CurrencyRef":{"value":"TRY"},"LinkedTxn":[]}
    link={"status":"PILOT_ORDER_INVOICE_VERIFIED","verified":True}
    good=a.audit_pilot_payment_accounting(order,inv,link)
    assert good["status"]=="TEST_PAID_QBO_UNPAID_EXPECTED"
    assert good["settlement_verified"] is False and good["real_cash_claimed"] is False
    wrong=deepcopy(order);wrong["transactions"][0]["amountSet"]["shopMoney"]["amount"]="215"
    assert a.audit_pilot_payment_accounting(wrong,inv,link)["status"]=="REVIEW_TEST_GATEWAY_PAYMENT_TOTAL"
    wrong=deepcopy(order);wrong["test"]=False
    assert a.audit_pilot_payment_accounting(wrong,inv,link)["status"]=="NOT_CHECKED_NONTEST_PAYMENT_SETTLEMENT"
    wrong=deepcopy(order);wrong["transactions"][0]["test"]=False
    assert a.audit_pilot_payment_accounting(wrong,inv,link)["status"]=="BLOCKED_PAYMENT_TEST_CLASSIFICATION"
    wrong=deepcopy(inv);wrong["Balance"]=0
    assert a.audit_pilot_payment_accounting(order,wrong,link)["status"]=="REVIEW_QBO_PAYMENT_RECORDS"
    wrong=deepcopy(inv);wrong["Balance"]=217
    assert a.audit_pilot_payment_accounting(order,wrong,link)["status"]=="BLOCKED_INVALID_PAYMENT_TOTALS"
    assert a.audit_pilot_payment_accounting(order,inv,{"verified":False})["status"]=="BLOCKED_ORDER_INVOICE_LINK"


def test_refund_credit_reconciliation_guards():
    from copy import deepcopy
    order={"id":"gid://shopify/Order/123", "test":True,
           "totalPriceSet":{"shopMoney":{"amount":"216","currencyCode":"TRY"}}}
    def refund(ref="gid://shopify/Refund/1",amount="100"):
        return {"id":ref,"order_id":order["id"],"amount":{"value":amount,"currency":"TRY"},
                "transactions":[{"id":ref+"/tx", "kind":"REFUND","status":"SUCCESS",
                                 "test":True,"currency":"TRY","amount":amount}]}
    def credit(ref="gid://shopify/Refund/1",amount="100",ident="C1"):
        return {"id":ident,"shopify_refund_id":ref,"currency":"TRY","amount":amount}
    good=a.audit_refund_credit_links(order,[refund()],[credit()])
    assert good["verified"] is True and good["status"]=="TEST_REFUND_CREDIT_RECORDS_MATCH"
    assert good["bank_settlement_verified"] is False and good["real_cash_claimed"] is False
    cases=[([refund()],[],"BLOCKED_MISSING_CREDIT_MEMO"),
           ([refund(),refund()], [credit()],"BLOCKED_DUPLICATE_OR_INVALID_REFUND_ID"),
           ([refund("gid://shopify/Refund/1","217")],[credit(amount="217")],"REVIEW_REFUNDS_EXCEED_ORDER"),
           ([refund()],[credit(amount="99")],"REVIEW_REFUND_CREDIT_AMOUNT_MISMATCH"),
           ([refund()],[credit(),credit(ident="C2")],"BLOCKED_UNLINKED_OR_DUPLICATE_REFUND_CREDIT"),
           ([refund()],[credit("gid://shopify/Refund/2")],"BLOCKED_UNLINKED_OR_DUPLICATE_REFUND_CREDIT")]
    for rr,cc,status in cases:
        result=a.audit_refund_credit_links(order,rr,cc)
        assert result["status"]==status and result["verified"] is False
    r=refund();r["transactions"][0]["status"]="PENDING"
    assert a.audit_refund_credit_links(order,[r],[credit()])["status"]=="BLOCKED_REFUND_TRANSACTION_NOT_SUCCESSFUL"
    assert a.audit_refund_credit_links(order,[],[])["status"]=="NO_REFUNDS_RECORDED"
    live=deepcopy(order);live["test"]=False
    assert a.audit_refund_credit_links(live,[refund()],[credit()])["status"]=="NOT_CHECKED_REAL_REFUND_SETTLEMENT"
    r2=refund("gid://shopify/Refund/2","50")
    two=a.audit_refund_credit_links(order,[refund(),r2], [credit(),credit(r2["id"],"50","C2")])
    assert two["verified"] is True and two["total"]=="150"
    shared=deepcopy(r2)
    shared["transactions"][0]["id"]=refund()["transactions"][0]["id"]
    duplicate_tx=a.audit_refund_credit_links(order,[refund(),shared],
                                             [credit(),credit(r2["id"],"50","C2")])
    assert duplicate_tx["status"]=="BLOCKED_DUPLICATE_REFUND_TRANSACTION"
    assert duplicate_tx["verified"] is False


def test_duplicate_explicit_shopify_references_block_even_if_first_matches():
    order={"id":"gid://shopify/Order/123", "name":"#1001",
           "totalPriceSet":{"shopMoney":{"amount":"216", "currencyCode":"TRY"}}}
    inv={"DocNumber":"2002", "CurrencyRef":{"value":"TRY"}, "TotalAmt":216,
         "CustomField":[{"Name":"Shopify Order ID", "StringValue":"123"}]}
    result=a.audit_shopify_invoice_link(order,[inv,{**inv,"DocNumber":"2003"}])
    assert result["status"]=="BLOCKED_MULTIPLE_LINKED_INVOICES"
    assert result["verified"] is False
