from contextlib import closing

from fastapi import APIRouter

from app.core.config import READY_VISIBLE_SECONDS
from app.core.db import get_conn
from app.modules.orders.service import seconds_since

router = APIRouter()


def build_display_payload():
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
        if visible_for is None or visible_for > READY_VISIBLE_SECONDS:
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
    }


@router.get("/api/display/orders")
def get_display_orders():
    return build_display_payload()


@router.get("/display/orders")
def legacy_display_orders():
    return build_display_payload()
