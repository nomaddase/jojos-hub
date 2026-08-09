import threading
import time
from contextlib import closing

from app.core.db import get_conn
from app.modules.central.outbox import enqueue_event
from app.modules.orders.service import build_order_response

_started = False
_lock = threading.Lock()


def _wire_payload(order: dict, status: str | None = None) -> dict:
    return {
        "order_id": order["id"],
        "order_number": order["number"],
        "status": status or order.get("status") or "created",
        "source": order.get("source") or "kso",
        "service_mode": order.get("service_mode") or "dine_in",
        "created_at": order.get("created_at"),
        "accepted_at": order.get("accepted_at"),
        "ready_at": order.get("ready_at"),
        "cancelled_at": order.get("cancelled_at"),
        "total": int(order.get("total") or 0),
        "items": order.get("items") or [],
    }


def _ensure_state_table(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS central_order_exports (
            order_id TEXT PRIMARY KEY,
            created_queued INTEGER NOT NULL DEFAULT 0,
            last_status TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def export_orders_once() -> dict:
    """Queue missing order events exactly once, including orders created before this fix."""
    with _lock:
        with closing(get_conn()) as conn:
            cur = conn.cursor()
            _ensure_state_table(cur)
            rows = cur.execute("SELECT id, status FROM orders ORDER BY created_at ASC").fetchall()
            conn.commit()

        created_count = 0
        status_count = 0
        for row in rows:
            order_id = row["id"]
            try:
                order = build_order_response(order_id)
            except Exception:
                continue
            current_status = str(order.get("status") or "created")

            with closing(get_conn()) as conn:
                cur = conn.cursor()
                _ensure_state_table(cur)
                state = cur.execute(
                    "SELECT created_queued, last_status FROM central_order_exports WHERE order_id = ?",
                    (order_id,),
                ).fetchone()
                created_queued = bool(state["created_queued"]) if state else False
                last_status = str(state["last_status"] or "") if state else ""

                if not created_queued:
                    created_payload = _wire_payload(order, "created")
                    created_payload["ready_at"] = None
                    created_payload["cancelled_at"] = None
                    enqueue_event(cur, "order.created", created_payload, event_id=f"order:{order_id}:created")
                    created_count += 1
                    created_queued = True

                if current_status != "created" and current_status != last_status:
                    event_type = {
                        "in_progress": "order.in_progress",
                        "ready": "order.ready",
                        "cancelled": "order.cancelled",
                    }.get(current_status, f"order.{current_status}")
                    enqueue_event(
                        cur,
                        event_type,
                        _wire_payload(order, current_status),
                        event_id=f"order:{order_id}:{current_status}",
                    )
                    status_count += 1

                cur.execute(
                    """
                    INSERT INTO central_order_exports(order_id, created_queued, last_status, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(order_id) DO UPDATE SET
                        created_queued = excluded.created_queued,
                        last_status = excluded.last_status,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (order_id, 1 if created_queued else 0, current_status),
                )
                conn.commit()

        return {"orders": len(rows), "created_queued": created_count, "status_queued": status_count}


def _worker():
    while True:
        try:
            export_orders_once()
        except Exception:
            pass
        time.sleep(5)


def start_order_export():
    global _started
    if _started:
        return
    _started = True
    # Run once immediately so historical test orders are sent without waiting.
    try:
        export_orders_once()
    except Exception:
        pass
    threading.Thread(target=_worker, name="jojos-order-export", daemon=True).start()
