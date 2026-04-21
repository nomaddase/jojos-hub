from contextlib import closing

from fastapi import APIRouter

from app.core.db import get_conn
from app.modules.orders.service import (
    build_order_response,
    mark_in_progress_if_created,
    seconds_since,
)
from app.modules.settings.service import get_effective_settings

router = APIRouter()


def build_kitchen_payload():
    warning_ratio = float(get_effective_settings().get("kitchen", {}).get("warning_ratio", 0.7))

    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM orders WHERE status IN (?, ?) ORDER BY created_at ASC",
            ("created", "in_progress"),
        )
        rows = cur.fetchall()

    result = []
    for row in rows:
        order_id = row["id"]
        mark_in_progress_if_created(order_id)
        order = build_order_response(order_id)

        elapsed = seconds_since(order["created_at"]) or 0
        target = order["target_prep_seconds"]
        ratio = elapsed / target if target > 0 else 0

        if ratio >= 1:
            time_state = "overdue"
        elif ratio >= warning_ratio:
            time_state = "warning"
        else:
            time_state = "normal"

        result.append(
            {
                **order,
                "elapsed_seconds": elapsed,
                "progress_ratio": round(ratio, 2),
                "time_state": time_state,
            }
        )

    return result


@router.get("/api/kitchen/orders")
def get_kitchen_orders():
    return build_kitchen_payload()


@router.get("/kitchen/orders")
def legacy_kitchen_orders():
    return build_kitchen_payload()
