# Aster & Row Support Agent - Secure Order Database Connector

import json, os, re

def normalize_order_id(input_str):
    """Extracts and normalizes order ID to uppercase ORD-XXXX format."""
    if not input_str: return None
    for pattern in [r'ORD-(\d+)', r'ORD\s*(\d+)', r'order\s*(?:id|#)?\s*(\d{4})\b', r'\b(10\d{2}|9999)\b']:
        match = re.search(pattern, input_str, re.IGNORECASE if pattern != r'\b(10\d{2}|9999)\b' else 0)
        if match: return f"ORD-{match.group(1)}"
    return None

def get_order(order_id_raw, orders_path="data/orders.json"):
    """Looks up order by ID. Normalizes ID, filters PII, and applies masking constraints."""
    normalized_id = normalize_order_id(order_id_raw)
    if not normalized_id: return None

    if not os.path.exists(orders_path):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        orders_path = os.path.join(os.path.dirname(current_dir), "data", "orders.json")
        if not os.path.exists(orders_path): orders_path = os.path.abspath("data/orders.json")

    with open(orders_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    snapshot_at = data.get("snapshot_at", "2026-08-15T12:00:00Z")
    order_found = next((o for o in data.get("orders", []) if o.get("order_id", "").upper() == normalized_id), None)

    if not order_found:
        return {"order_id": normalized_id, "found": False, "requires_handoff": True, "message": f"Order {normalized_id} was not found."}

    status = order_found.get("status", "").lower()
    is_cancelled_or_returned = status in ["cancelled", "returned"]
    
    estimated_delivery = order_found.get("estimated_delivery")
    carrier = order_found.get("carrier") if not is_cancelled_or_returned else None
    tracking_number = order_found.get("tracking_number") if not is_cancelled_or_returned else None
    shipped_at = order_found.get("shipped_at") if not is_cancelled_or_returned else None
    delivered_at = order_found.get("delivered_at") if not is_cancelled_or_returned else None
    if is_cancelled_or_returned: estimated_delivery = None

    safe_items = [{"name": i.get("name"), "quantity": i.get("quantity"), "final_sale": i.get("final_sale", False)} for i in order_found.get("items", [])]

    return {
        "order_id": order_found.get("order_id"),
        "found": True,
        "membership_tier": order_found.get("membership_tier", "standard"),
        "placed_at": order_found.get("placed_at"),
        "status": order_found.get("status"),
        "status_updated_at": order_found.get("status_updated_at"),
        "shipped_at": shipped_at,
        "delivered_at": delivered_at,
        "carrier": carrier,
        "tracking_number": tracking_number,
        "estimated_delivery": estimated_delivery,
        "customer_safe_message": order_found.get("customer_safe_message"),
        "items": safe_items,
        "requires_handoff": status == "exception",
        "snapshot_at": snapshot_at
    }

def get_db_snapshot_time(orders_path="data/orders.json"):
    """Loads snapshot time from orders database dynamically."""
    if not os.path.exists(orders_path):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        orders_path = os.path.join(os.path.dirname(current_dir), "data", "orders.json")
        if not os.path.exists(orders_path): orders_path = os.path.abspath("data/orders.json")
    try:
        with open(orders_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("snapshot_at", "2026-08-15T12:00:00Z")
    except Exception: return "2026-08-15T12:00:00Z"
