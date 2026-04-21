from contextlib import closing

from fastapi import APIRouter

from app.core.db import get_conn
from app.modules.orders.service import seconds_since
from app.modules.settings.service import get_effective_settings

router = APIRouter()


def build_display_payload():
    ready_visible_seconds = int(get_effective_settings().get("display", {}).get("ready_visibility_seconds", 300))

    with closing(get_conn()) as conn:
        cur = conn.cursor()

        cur.execute(
            "SELECT id, number, created_at, status FROM orders WHERE status IN (?, ?) ORDER BY created_at ASC",
            ("created", "in_progress"),
        )
        accepted_rows = cur.fetchall()

        cur.execute(
            "SELECT id, number, created_at, ready_at, status FROM orders WHERE status = ? ORDER BY ready_at ASC",
            ("ready",),
        )
        ready_rows = cur.fetchall()

    accepted_orders = [
        {
            "id": row["id"],
            "number": row["number"],
            "status": row["status"],
            "wait_seconds": seconds_since(row["created_at"]) or 0,
        }
        for row in accepted_rows
    ]

    ready_orders = []
    for row in ready_rows:
        visible_for = seconds_since(row["ready_at"])
        if visible_for is None or visible_for > ready_visible_seconds:
            continue

        ready_orders.append(
            {
                "id": row["id"],
                "number": row["number"],
                "status": row["status"],
                "wait_seconds": visible_for,
            }
        )

    return {
        "accepted_orders": accepted_orders,
        "ready_orders": ready_orders,
        "ready_visibility_seconds": ready_visible_seconds,
    }


@router.get("/api/display/orders")
def get_display_orders():
    return build_display_payload()


@router.get("/display/orders")
def legacy_display_orders():
    return build_display_payload()
