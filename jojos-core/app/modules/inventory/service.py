from contextlib import closing
from datetime import datetime, timezone

from app.core.db import get_conn


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_inventory_map():
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT item_id, available_qty, is_available, updated_at FROM inventory_items")
        rows = cur.fetchall()

    result = {}
    for row in rows:
        result[row["item_id"]] = {
            "item_id": row["item_id"],
            "available_qty": row["available_qty"],
            "is_available": bool(row["is_available"]),
            "updated_at": row["updated_at"],
        }
    return result


def list_inventory_items():
    return list(get_inventory_map().values())


def upsert_inventory_item(item_id: str, available_qty: int, is_available: bool):
    now = utc_now_iso()

    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO inventory_items (item_id, available_qty, is_available, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(item_id) DO UPDATE SET
                available_qty = excluded.available_qty,
                is_available = excluded.is_available,
                updated_at = excluded.updated_at
            """,
            (item_id, available_qty, 1 if is_available else 0, now),
        )
        conn.commit()

    return {
        "item_id": item_id,
        "available_qty": available_qty,
        "is_available": is_available,
        "updated_at": now,
    }
