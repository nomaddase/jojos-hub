import json
import uuid
from contextlib import closing
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException

from app.core.db import get_conn
from app.modules.catalog.service import get_catalog_data
from app.modules.inventory.service import get_inventory_map
from app.modules.orders.service import (
    CreateOrderRequest,
    OrderResponse,
    _parse_json,
    build_order_response,
    order_contains_sandwich,
    seconds_between,
    seconds_since,
    utc_now_iso,
)
from app.modules.printing.service import create_kitchen_label_job
from app.modules.settings.service import get_effective_settings

router = APIRouter()


def build_catalog_index():
    index = {}
    for group in get_catalog_data()["groups"]:
        for item in group["items"]:
            options_index = {}
            for option_group in item.get("options", []):
                option_items = {}
                for option in option_group.get("items", []):
                    option_items[option["id"]] = {
                        "id": option["id"],
                        "name": option["name"],
                        "price": int(option.get("price") or 0),
                    }

                options_index[option_group["id"]] = {
                    "id": option_group["id"],
                    "name": option_group["name"],
                    "mode": option_group.get("mode") or "multi",
                    "items": option_items,
                }

            index[item["id"]] = {
                "id": item["id"],
                "name": item["name"],
                "price": int(item.get("price") or 0),
                "prep_seconds": int(item.get("prep_seconds") or 120),
                "options": options_index,
            }
    return index


def _assert_inventory_available(inventory_map: dict, item_id: str, required_qty: int, label: str):
    stock = inventory_map.get(item_id)
    if not stock:
        return
    if not bool(stock.get("is_available", True)):
        raise HTTPException(status_code=409, detail=f"{label} unavailable")

    available_qty = stock.get("available_qty")
    if available_qty is not None and int(available_qty) < required_qty:
        raise HTTPException(status_code=409, detail=f"{label} out of stock")


def _consume_inventory(cur, inventory_map: dict, item_id: str, used_qty: int):
    stock = inventory_map.get(item_id)
    if not stock:
        return

    available_qty = stock.get("available_qty")
    if available_qty is None:
        return

    next_qty = max(0, int(available_qty) - int(used_qty))
    next_available = 1 if bool(stock.get("is_available", True)) and next_qty > 0 else 0

    cur.execute(
        "UPDATE inventory_items SET available_qty = ?, is_available = ? WHERE item_id = ?",
        (next_qty, next_available, item_id),
    )
    stock["available_qty"] = next_qty
    stock["is_available"] = bool(next_available)


def normalize_order_items(payload_items):
    catalog_index = build_catalog_index()
    inventory_map = get_inventory_map()

    normalized_items = []
    for payload_item in payload_items:
        catalog_item = catalog_index.get(payload_item.item_id)
        if not catalog_item:
            raise HTTPException(status_code=400, detail=f"Unknown item_id: {payload_item.item_id}")

        item_qty = int(payload_item.qty)
        _assert_inventory_available(inventory_map, payload_item.item_id, item_qty, catalog_item["name"])

        normalized_options = []
        grouped_counts = {}
        for option in payload_item.options:
            catalog_group = catalog_item["options"].get(option.group_id)
            if not catalog_group:
                raise HTTPException(status_code=400, detail=f"Unknown option group: {option.group_id}")

            catalog_option = catalog_group["items"].get(option.option_id)
            if not catalog_option:
                raise HTTPException(status_code=400, detail=f"Unknown option_id: {option.option_id}")

            grouped_counts[option.group_id] = grouped_counts.get(option.group_id, 0) + 1
            option_stock_key = f"{payload_item.item_id}:{option.group_id}:{option.option_id}"
            _assert_inventory_available(inventory_map, option.option_id, item_qty, catalog_option["name"])
            _assert_inventory_available(inventory_map, option_stock_key, item_qty, catalog_option["name"])

            normalized_options.append(
                {
                    "group_id": option.group_id,
                    "option_id": option.option_id,
                    "name": catalog_option["name"],
                    "price": int(catalog_option["price"]),
                }
            )

        for group_id, group_def in catalog_item["options"].items():
            if group_def["mode"] == "single" and grouped_counts.get(group_id, 0) > 1:
                raise HTTPException(status_code=400, detail=f"Multiple selections for single-choice group: {group_id}")

        normalized_items.append(
            {
                "item_id": payload_item.item_id,
                "name": catalog_item["name"],
                "qty": item_qty,
                "price": int(catalog_item["price"]),
                "prep_seconds": int(catalog_item["prep_seconds"]),
                "options": normalized_options,
            }
        )

    return normalized_items, inventory_map


def calculate_order_target_prep_seconds(items) -> int:
    total = 0
    for item in items:
        prep = int(item.get("prep_seconds") or 120)
        total += prep * int(item.get("qty") or 1)
    return max(total, 60)


def calculate_queue_remaining_seconds() -> int:
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT created_at, accepted_at, target_prep_seconds
            FROM orders
            WHERE status IN (?, ?)
            ORDER BY created_at ASC
            """,
            ("created", "in_progress"),
        )
        rows = cur.fetchall()

    total_remaining = 0
    for row in rows:
        start_dt = row["accepted_at"] or row["created_at"]
        elapsed = seconds_since(start_dt) or 0
        target = int(row["target_prep_seconds"] or 120)
        remaining = max(target - elapsed, 0)
        total_remaining += remaining

    return total_remaining


@router.get("/api/orders/eta/current")
def get_current_eta():
    queue_remaining = calculate_queue_remaining_seconds()
    return {
        "queue_remaining_seconds": queue_remaining,
        "approx_wait_seconds": queue_remaining,
    }


@router.post("/api/orders/eta/preview")
def preview_order_eta(payload: CreateOrderRequest):
    normalized_items, _ = normalize_order_items(payload.items)
    order_target = calculate_order_target_prep_seconds(normalized_items)
    queue_remaining = calculate_queue_remaining_seconds()
    eta_seconds = queue_remaining + order_target

    return {
        "queue_remaining_seconds": queue_remaining,
        "order_target_prep_seconds": order_target,
        "eta_seconds": eta_seconds,
    }


@router.post("/api/orders", response_model=OrderResponse)
def create_order(payload: CreateOrderRequest):
    order_id = str(uuid.uuid4())
    order_number = str(100000 + int(datetime.now(timezone.utc).timestamp()) % 900000)
    created_at = utc_now_iso()

    settings = get_effective_settings()
    service_modes = settings.get("service_modes", {})
    enabled_modes = service_modes.get("enabled", ["dine_in", "takeaway"])
    default_mode = service_modes.get("default", "dine_in")
    normalized_mode = (payload.service_mode or default_mode).strip().lower()
    if normalized_mode not in enabled_modes:
        raise HTTPException(status_code=400, detail="Unsupported service_mode")

    normalized_items, inventory_map = normalize_order_items(payload.items)

    total = 0
    for item in normalized_items:
        total += int(item["qty"]) * int(item["price"])
        for opt in item["options"]:
            total += int(item["qty"]) * int(opt["price"])

    contains_sandwich = order_contains_sandwich(normalized_items)
    target_prep_seconds = calculate_order_target_prep_seconds(normalized_items)

    snapshot_items = []
    for item in normalized_items:
        snapshot_options = [
            {
                "group_id": option["group_id"],
                "option_id": option["option_id"],
                "name": option["name"],
                "price": option["price"],
            }
            for option in item["options"]
        ]

        modifier_lines = []
        for option in snapshot_options:
            option_price = int(option.get("price") or 0)
            if option_price > 0:
                modifier_lines.append(f"+ {option['name']} (+{option_price} ₸)")
            else:
                modifier_lines.append(f"+ {option['name']}")

        snapshot_items.append(
            {
                "item_id": item["item_id"],
                "name": item["name"],
                "display_name": item["name"],
                "qty": item["qty"],
                "base_price": item["price"],
                "options": snapshot_options,
                "modifier_lines": modifier_lines,
                "kitchen_text": "\n".join([f"{item['qty']} × {item['name']}", *modifier_lines])
                if modifier_lines
                else f"{item['qty']} × {item['name']}",
                "line_total": (item["price"] + sum(int(opt["price"] or 0) for opt in snapshot_options)) * item["qty"],
            }
        )

    order_snapshot = {
        "order_id": order_id,
        "order_number": order_number,
        "source": payload.source,
        "service_mode": normalized_mode,
        "created_at": created_at,
        "target_prep_seconds": target_prep_seconds,
        "total": total,
        "currency": "KZT",
        "printing": {
            "receipt_type": "kitchen+guest",
            "timezone": "UTC",
            "reprint_count": 0,
        },
        "fulfillment": {
            "status": "created",
            "accepted_at": None,
            "ready_at": None,
            "cancelled_at": None,
        },
        "items": snapshot_items,
    }

    with closing(get_conn()) as conn:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO orders (
                id, number, source, status, created_at, total,
                accepted_at, ready_at, cancelled_at,
                target_prep_seconds, contains_sandwich, service_mode,
                actual_prep_seconds, is_overdue, order_snapshot_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                order_number,
                payload.source,
                "created",
                created_at,
                total,
                None,
                None,
                None,
                target_prep_seconds,
                1 if contains_sandwich else 0,
                normalized_mode,
                None,
                0,
                json.dumps(order_snapshot, ensure_ascii=False),
            ),
        )

        for item in normalized_items:
            order_item_id = str(uuid.uuid4())

            cur.execute(
                "INSERT INTO order_items (id, order_id, item_id, name, qty, price) VALUES (?, ?, ?, ?, ?, ?)",
                (order_item_id, order_id, item["item_id"], item["name"], item["qty"], item["price"]),
            )
            _consume_inventory(cur, inventory_map, item["item_id"], item["qty"])

            for option in item["options"]:
                cur.execute(
                    "INSERT INTO order_item_options (id, order_item_id, group_id, option_id, name, price) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        str(uuid.uuid4()),
                        order_item_id,
                        option["group_id"],
                        option["option_id"],
                        option["name"],
                        option["price"],
                    ),
                )
                option_stock_key = f"{item['item_id']}:{option['group_id']}:{option['option_id']}"
                _consume_inventory(cur, inventory_map, option["option_id"], item["qty"])
                _consume_inventory(cur, inventory_map, option_stock_key, item["qty"])

        conn.commit()

    result = build_order_response(order_id)
    auto_print = bool(settings.get("printer", {}).get("auto_print_kitchen_label_on_create", True))
    if auto_print:
        result["print_result"] = create_kitchen_label_job(order_id)
    return result


@router.get("/api/orders", response_model=List[OrderResponse])
def get_orders():
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM orders ORDER BY created_at DESC")
        rows = cur.fetchall()

    return [build_order_response(row["id"]) for row in rows]


@router.get("/api/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: str):
    return build_order_response(order_id)


@router.post("/api/orders/{order_id}/ready", response_model=OrderResponse)
def set_order_ready(order_id: str):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Order not found")
        if row["status"] in ("ready", "cancelled"):
            raise HTTPException(status_code=409, detail=f"Order already {row['status']}")

        accepted_at = row["accepted_at"] or utc_now_iso()
        ready_at = utc_now_iso()
        actual_prep_seconds = seconds_between(accepted_at, ready_at)
        target_prep_seconds = row["target_prep_seconds"] or 120
        is_overdue = 1 if (actual_prep_seconds is not None and actual_prep_seconds > target_prep_seconds) else 0

        snapshot = _parse_json(row["order_snapshot_json"]) or {}
        snapshot.setdefault("fulfillment", {})
        snapshot["fulfillment"].update({"status": "ready", "accepted_at": accepted_at, "ready_at": ready_at})

        cur.execute(
            """
            UPDATE orders
            SET status = ?, accepted_at = ?, ready_at = ?, actual_prep_seconds = ?, is_overdue = ?, order_snapshot_json = ?
            WHERE id = ?
            """,
            ("ready", accepted_at, ready_at, actual_prep_seconds, is_overdue, json.dumps(snapshot, ensure_ascii=False), order_id),
        )
        conn.commit()

    return build_order_response(order_id)


@router.post("/api/orders/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(order_id: str):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Order not found")
        if row["status"] in ("ready", "cancelled"):
            raise HTTPException(status_code=409, detail=f"Order already {row['status']}")

        cancelled_at = utc_now_iso()
        accepted_at = row["accepted_at"] or row["created_at"]
        actual_prep_seconds = seconds_between(accepted_at, cancelled_at)

        snapshot = _parse_json(row["order_snapshot_json"]) or {}
        snapshot.setdefault("fulfillment", {})
        snapshot["fulfillment"].update(
            {"status": "cancelled", "accepted_at": row["accepted_at"], "cancelled_at": cancelled_at}
        )

        cur.execute(
            """
            UPDATE orders
            SET status = ?, cancelled_at = ?, actual_prep_seconds = ?, order_snapshot_json = ?
            WHERE id = ?
            """,
            ("cancelled", cancelled_at, actual_prep_seconds, json.dumps(snapshot, ensure_ascii=False), order_id),
        )
        conn.commit()

    return build_order_response(order_id)
