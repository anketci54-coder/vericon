#!/usr/bin/env python3
"""VERICON: single-SKU read-only inventory quantity comparison.

Consumes two already-fetched records via stdin; this does NOT call Shopify or QBO.
"""
import json
import sys
from decimal import Decimal, InvalidOperation


def qty(value, name):
    if value is None or isinstance(value, bool):
        raise ValueError(f"{name}: numeric value required")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{name}: invalid number") from None
    if not result.is_finite():
        raise ValueError(f"{name}: finite number required")
    return result


def compare(data):
    shopify = data["shopify"]
    qbo = data["quickbooks"]
    sku = shopify.get("sku")
    if not sku or sku != qbo.get("Sku"):
        return {"status": "BLOCKED_SKU_MISMATCH", "shopify_sku": sku, "qbo_sku": qbo.get("Sku")}
    if qbo.get("Type") != "Inventory" or qbo.get("TrackQtyOnHand") is not True:
        return {"status": "BLOCKED_NOT_TRACKED_INVENTORY", "sku": sku}

    stock_shopify = qty(shopify.get("onHand"), "shopify.onHand")
    stock_qbo = qty(qbo.get("QtyOnHand"), "quickbooks.QtyOnHand")
    delta = stock_shopify - stock_qbo
    is_test = data.get("testMode") is True

    return {
        "sku": sku,
        "shopify_on_hand": str(stock_shopify),
        "qbo_qty_on_hand": str(stock_qbo),
        "delta_shopify_minus_qbo": str(delta),
        "status": "TEST_DIFFERENCE" if is_test and delta else
                  "TEST_MATCH" if is_test else
                  "REVIEW_SNAPSHOT_AND_LOCATION" if delta else "MATCH_NEEDS_SNAPSHOT_VALIDATION",
        "data_origin": "provided_api_outputs_no_live_qbo_connection",
        "note": "Not proof of financial loss. Align stock meaning, location, and snapshot times."
    }


if __name__ == "__main__":
    try:
        result = compare(json.load(sys.stdin))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        if result["status"].startswith("BLOCKED_"):
            sys.exit(2)
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED_INVALID_INPUT", "error": str(exc)}))
        sys.exit(2)
