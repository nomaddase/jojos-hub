from datetime import datetime, timedelta, timezone
from contextlib import closing

from fastapi import APIRouter, HTTPException

from app.core.db import get_conn
from app.modules.settings.service import get_effective_settings
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
    return {
        "items": list_settings(),
        "effective": get_effective_settings(),
    }


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
            SELECT
                id,
                number,
                service_mode,
                target_prep_seconds,
                actual_prep_seconds,
                is_overdue,
                status,
                created_at,
                ready_at,
                cancelled_at,
                accepted_at
            FROM orders
            WHERE created_at >= ? AND created_at < ?
            ORDER BY created_at ASC
            """,
            (
                start_dt.isoformat().replace("+00:00", "Z"),
                end_dt.isoformat().replace("+00:00", "Z"),
            ),
        )
        rows = cur.fetchall()

    total = len(rows)
    ready_rows = [r for r in rows if r["status"] == "ready"]
    cancelled_rows = [r for r in rows if r["status"] == "cancelled"]
    completed_rows = [r for r in rows if r["status"] in ("ready", "cancelled")]

    overdue_ready_count = sum(1 for r in ready_rows if r["is_overdue"])
    prep_values = [r["actual_prep_seconds"] for r in ready_rows if r["actual_prep_seconds"] is not None]
    avg_prep = int(sum(prep_values) / len(prep_values)) if prep_values else 0

    target_values = [int(r["target_prep_seconds"] or 0) for r in ready_rows]
    avg_target = int(sum(target_values) / len(target_values)) if target_values else 0

    variance_values = [
        int(r["actual_prep_seconds"] or 0) - int(r["target_prep_seconds"] or 0)
        for r in ready_rows
        if r["actual_prep_seconds"] is not None
    ]
    avg_variance = int(sum(variance_values) / len(variance_values)) if variance_values else 0

    return {
        "date": str(day),
        "summary": {
            "orders_total": total,
            "orders_ready": len(ready_rows),
            "orders_cancelled": len(cancelled_rows),
            "orders_completed": len(completed_rows),
            "avg_prep_sec": avg_prep,
            "avg_target_prep_sec": avg_target,
            "avg_prep_variance_sec": avg_variance,
            "overdue_count": overdue_ready_count,
            "overdue_ratio": (overdue_ready_count / len(ready_rows)) if ready_rows else 0,
            "cancelled_ratio": (len(cancelled_rows) / total) if total else 0,
        },
        "orders": [
            {
                "id": r["id"],
                "number": r["number"],
                "service_mode": r["service_mode"] or "dine_in",
                "target_prep_sec": r["target_prep_seconds"],
                "actual_prep_sec": r["actual_prep_seconds"],
                "prep_variance_sec": None
                if r["actual_prep_seconds"] is None
                else int(r["actual_prep_seconds"] or 0) - int(r["target_prep_seconds"] or 0),
                "is_overdue": bool(r["is_overdue"]),
                "status": r["status"],
                "created_at": r["created_at"],
                "accepted_at": r["accepted_at"],
                "ready_at": r["ready_at"],
                "cancelled_at": r["cancelled_at"],
            }
            for r in rows
        ],
    }
