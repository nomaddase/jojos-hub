import json
from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from app.core.db import get_conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def enqueue_event(cur, event_type: str, payload: dict, event_id: str | None = None) -> str:
    event_id = event_id or str(uuid4())
    cur.execute(
        """
        INSERT OR IGNORE INTO central_outbox (
            event_id, event_type, payload_json, created_at,
            delivered_at, attempt_count, last_attempt_at, last_error
        ) VALUES (?, ?, ?, ?, NULL, 0, NULL, NULL)
        """,
        (event_id, event_type, json.dumps(payload, ensure_ascii=False), now_iso()),
    )
    return event_id


def pending_count() -> int:
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM central_outbox WHERE delivered_at IS NULL").fetchone()
        return int(row["n"] if row else 0)


def pending_events(limit: int = 100) -> list[dict]:
    with closing(get_conn()) as conn:
        rows = conn.execute(
            """
            SELECT event_id, event_type, payload_json, created_at, attempt_count
            FROM central_outbox
            WHERE delivered_at IS NULL
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (max(1, min(int(limit), 500)),),
        ).fetchall()
    result = []
    for row in rows:
        try:
            payload = json.loads(row["payload_json"])
        except Exception:
            payload = {}
        result.append(
            {
                "event_id": row["event_id"],
                "type": row["event_type"],
                "created_at": row["created_at"],
                "payload": payload,
                "attempt_count": int(row["attempt_count"] or 0),
            }
        )
    return result


def mark_push_result(accepted: list[str], rejected: list[dict]) -> None:
    now = now_iso()
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        for event_id in accepted or []:
            cur.execute(
                """
                UPDATE central_outbox
                SET delivered_at = ?, attempt_count = attempt_count + 1,
                    last_attempt_at = ?, last_error = NULL
                WHERE event_id = ? AND delivered_at IS NULL
                """,
                (now, now, event_id),
            )
        for item in rejected or []:
            event_id = item.get("event_id")
            if not event_id:
                continue
            cur.execute(
                """
                UPDATE central_outbox
                SET attempt_count = attempt_count + 1,
                    last_attempt_at = ?, last_error = ?
                WHERE event_id = ? AND delivered_at IS NULL
                """,
                (now, str(item.get("reason") or "rejected")[:1000], event_id),
            )
        conn.commit()


def mark_batch_error(event_ids: list[str], error: str) -> None:
    if not event_ids:
        return
    now = now_iso()
    message = str(error)[:1000]
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        for event_id in event_ids:
            cur.execute(
                """
                UPDATE central_outbox
                SET attempt_count = attempt_count + 1,
                    last_attempt_at = ?, last_error = ?
                WHERE event_id = ? AND delivered_at IS NULL
                """,
                (now, message, event_id),
            )
        conn.commit()


def prune_delivered(keep_last: int = 1000) -> None:
    # Keep recent acknowledged rows for local support/audit while preventing
    # unbounded growth on a long-running store Hub.
    keep_last = max(100, int(keep_last))
    with closing(get_conn()) as conn:
        conn.execute(
            """
            DELETE FROM central_outbox
            WHERE delivered_at IS NOT NULL
              AND event_id NOT IN (
                  SELECT event_id FROM central_outbox
                  WHERE delivered_at IS NOT NULL
                  ORDER BY delivered_at DESC
                  LIMIT ?
              )
            """,
            (keep_last,),
        )
        conn.commit()
