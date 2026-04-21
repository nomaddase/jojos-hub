from contextlib import closing
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.core.db import get_conn


class OrderItemOption(BaseModel):
    group_id: str
    option_id: str
    name: str
    price: int = 0


class OrderItem(BaseModel):
    item_id: str
    name: str
    qty: int = Field(gt=0)
    price: int = Field(ge=0)
    options: List[OrderItemOption] = []


class CreateOrderRequest(BaseModel):
    source: str = "kso"
    service_mode: str = "dine_in"
    items: List[OrderItem]


class OrderResponse(BaseModel):
    id: str
    number: str
    source: str
    status: str
    created_at: str
    accepted_at: Optional[str] = None
    ready_at: Optional[str] = None
    cancelled_at: Optional[str] = None
    total: int
    target_prep_seconds: int
    contains_sandwich: bool
    service_mode: str
    actual_prep_seconds: Optional[int] = None
    is_overdue: bool
    order_snapshot: Optional[dict] = None
    items: List[dict]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso(dt: Optional[str]):
    if not dt:
        return None
    return datetime.fromisoformat(dt.replace("Z", "+00:00"))


def seconds_since(dt: Optional[str]) -> Optional[int]:
    parsed = parse_iso(dt)
    if not parsed:
        return None
    return int((datetime.now(timezone.utc) - parsed).total_seconds())


def seconds_between(dt_from: Optional[str], dt_to: Optional[str]) -> Optional[int]:
    start = parse_iso(dt_from)
    end = parse_iso(dt_to)
    if not start or not end:
        return None
    return int((end - start).total_seconds())


def order_contains_sandwich(items: List[OrderItem]) -> bool:
    for item in items:
        item_id = item.item_id.lower()
        item_name = item.name.lower()
        if "sandwich" in item_id or "сэндвич" in item_name:
            return True
    return False


def build_modifier_lines(options: list[dict]) -> list[str]:
    lines = []
    for opt in options:
        name = (opt.get("name") or "").strip()
        if not name:
            continue
        price = int(opt.get("price") or 0)
        if price > 0:
            lines.append(f"+ {name} (+{price} ₸)")
        else:
            lines.append(f"+ {name}")
    return lines


def build_full_item_text(qty: int, name: str, modifier_lines: list[str]) -> str:
    first_line = f"{qty} × {name}"
    if not modifier_lines:
        return first_line
    return "\n".join([first_line, *modifier_lines])


def build_order_response(order_id: str) -> dict:
    with closing(get_conn()) as conn:
        cur = conn.cursor()

        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order = cur.fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        cur.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
        item_rows = cur.fetchall()

        items = []
        for item in item_rows:
            cur.execute(
                "SELECT group_id, option_id, name, price FROM order_item_options WHERE order_item_id = ?",
                (item["id"],),
            )
            options = [
                {
                    "group_id": opt["group_id"],
                    "option_id": opt["option_id"],
                    "name": opt["name"],
                    "price": opt["price"],
                }
                for opt in cur.fetchall()
            ]

            modifier_lines = build_modifier_lines(options)
            display_name = item["name"]
            full_item_text = build_full_item_text(item["qty"], display_name, modifier_lines)

            items.append(
                {
                    "item_id": item["item_id"],
                    "name": item["name"],
                    "display_name": display_name,
                    "qty": item["qty"],
                    "price": item["price"],
                    "options": options,
                    "modifier_lines": modifier_lines,
                    "full_item_text": full_item_text,
                }
            )

        return {
            "id": order["id"],
            "number": order["number"],
            "source": order["source"],
            "status": order["status"],
            "created_at": order["created_at"],
            "accepted_at": order["accepted_at"],
            "ready_at": order["ready_at"],
            "cancelled_at": order["cancelled_at"],
            "total": order["total"],
            "target_prep_seconds": order["target_prep_seconds"],
            "contains_sandwich": bool(order["contains_sandwich"]),
            "service_mode": order["service_mode"] or "dine_in",
            "actual_prep_seconds": order["actual_prep_seconds"],
            "is_overdue": bool(order["is_overdue"]),
            "order_snapshot": _parse_json(order["order_snapshot_json"]),
            "items": items,
        }


def mark_in_progress_if_created(order_id: str):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT status, accepted_at FROM orders WHERE id = ?", (order_id,))
        row = cur.fetchone()

        if not row:
            return

        if row["status"] == "created":
            accepted_at = row["accepted_at"] or utc_now_iso()
            cur.execute(
                "UPDATE orders SET status = ?, accepted_at = ? WHERE id = ?",
                ("in_progress", accepted_at, order_id),
            )
            conn.commit()


def _parse_json(raw: Optional[str]):
    if not raw:
        return None
    try:
        import json

        return json.loads(raw)
    except Exception:
        return None
