import uuid
import json
from contextlib import closing
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException

from app.core.db import get_conn
from app.modules.catalog.service import get_catalog_data
from app.modules.settings.service import get_effective_settings
from app.modules.orders.service import (
    CreateOrderRequest,
    OrderResponse,
    build_order_response,
    order_contains_sandwich,
    seconds_between,
    seconds_since,
    utc_now_iso,
)

router = APIRouter()


def build_prep_index():
    result = {}
    for group in get_catalog_data()["groups"]:
        for item in group["items"]:
            result[item["id"]] = int(item.get("prep_seconds") or 120)
    return result


def calculate_order_target_prep_seconds(items) -> int:
    prep_index = build_prep_index()
    total = 0
    for item in items:
        prep = prep_index.get(item.item_id, 120)
        total += prep * int(item.qty)
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
    order_target = calculate_order_target_prep_seconds(payload.items)
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
    enabled_modes = settings.get("service_modes", {}).get("enabled", ["dine_in", "takeaway"])
    normalized_mode = (payload.service_mode or "dine_in").strip().lower()
    if normalized_mode not in enabled_modes:
        raise HTTPException(status_code=400, detail="Unsupported service_mode")

    total = 0
    for item in payload.items:
        total += item.qty * item.price
        for opt in item.options:
            total += item.qty * opt.price

    contains_sandwich = order_contains_sandwich(payload.items)
    target_prep_seconds = calculate_order_target_prep_seconds(payload.items)

    snapshot_items = []
    for item in payload.items:
        snapshot_options = [
            {
                "group_id": option.group_id,
                "option_id": option.option_id,
                "name": option.name,
                "price": option.price,
            }
            for option in item.options
        ]
        snapshot_items.append(
            {
                "item_id": item.item_id,
                "name": item.name,
                "qty": item.qty,
                "base_price": item.price,
                "options": snapshot_options,
                "line_total": (item.price + sum(int(opt["price"] or 0) for opt in snapshot_options)) * item.qty,
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

        for item in payload.items:
            order_item_id = str(uuid.uuid4())

            cur.execute(
                "INSERT INTO order_items (id, order_id, item_id, name, qty, price) VALUES (?, ?, ?, ?, ?, ?)",
                (order_item_id, order_id, item.item_id, item.name, item.qty, item.price),
            )

            for option in item.options:
                cur.execute(
                    "INSERT INTO order_item_options (id, order_item_id, group_id, option_id, name, price) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        str(uuid.uuid4()),
                        order_item_id,
                        option.group_id,
                        option.option_id,
                        option.name,
                        option.price,
                    ),
                )

        conn.commit()

    return build_order_response(order_id)


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

        accepted_at = row["accepted_at"] or utc_now_iso()
        ready_at = utc_now_iso()
        actual_prep_seconds = seconds_between(accepted_at, ready_at)
        target_prep_seconds = row["target_prep_seconds"] or 120
        is_overdue = 1 if (actual_prep_seconds is not None and actual_prep_seconds > target_prep_seconds) else 0

        cur.execute(
            """
            UPDATE orders
            SET status = ?, accepted_at = ?, ready_at = ?, actual_prep_seconds = ?, is_overdue = ?
            WHERE id = ?
            """,
            ("ready", accepted_at, ready_at, actual_prep_seconds, is_overdue, order_id),
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

        cancelled_at = utc_now_iso()

        cur.execute(
            "UPDATE orders SET status = ?, cancelled_at = ? WHERE id = ?",
            ("cancelled", cancelled_at, order_id),
        )
        conn.commit()

    return build_order_response(order_id)
