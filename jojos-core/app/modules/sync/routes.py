from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone, timedelta
from contextlib import closing

from app.core.db import get_conn
from app.modules.sync.service import get_sync_status, list_settings, pull_from_mock_center

router = APIRouter()


@router.get("/api/sync/status")
def sync_status():
    return get_sync_status()


@router.post("/api/sync/pull")
def sync_pull():
    try:
        return pull_from_mock_center()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/settings")
def get_settings():
    return {"items": list_settings()}


@router.get("/api/analytics/kitchen/daily")
def kitchen_daily_summary(date: str | None = None):
    if date:
        day = datetime.fromisoformat(date).date()
    else:
        day = datetime.now(timezone.utc).date()

    start_dt = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(days=1)

    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, number, service_mode, target_prep_seconds, actual_prep_seconds, is_overdue, status, ready_at
            FROM orders
            WHERE ready_at >= ? AND ready_at < ?
            ORDER BY ready_at ASC
            """,
            (
                start_dt.isoformat().replace("+00:00", "Z"),
                end_dt.isoformat().replace("+00:00", "Z"),
            ),
        )
        rows = cur.fetchall()

    total = len(rows)
    ready = sum(1 for r in rows if r["status"] == "ready")
    overdue_count = sum(1 for r in rows if r["is_overdue"])
    prep_values = [r["actual_prep_seconds"] for r in rows if r["actual_prep_seconds"] is not None]
    avg_prep = int(sum(prep_values) / len(prep_values)) if prep_values else 0

    return {
        "date": str(day),
        "summary": {
            "orders_total": total,
            "orders_ready": ready,
            "avg_prep_sec": avg_prep,
            "overdue_count": overdue_count,
            "overdue_ratio": (overdue_count / total) if total else 0,
        },
        "orders": [
            {
                "id": r["id"],
                "number": r["number"],
                "service_mode": r["service_mode"] or "dine_in",
                "target_prep_sec": r["target_prep_seconds"],
                "actual_prep_sec": r["actual_prep_seconds"],
                "is_overdue": bool(r["is_overdue"]),
                "status": r["status"],
            }
            for r in rows
        ],
    }
