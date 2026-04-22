import json
from contextlib import closing
from datetime import datetime, timezone

from app.core.config import CONFIG_DIR
from app.core.db import get_conn
from app.modules.inventory.service import upsert_inventory_item
from app.modules.media.service import upsert_media_asset


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_sync_status():
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT last_pull_at, last_push_at, last_status, last_error
            FROM sync_status
            WHERE id = 1
        """)
        row = cur.fetchone()

    return {
        "last_pull_at": row["last_pull_at"] if row else None,
        "last_push_at": row["last_push_at"] if row else None,
        "last_status": row["last_status"] if row else None,
        "last_error": row["last_error"] if row else None,
    }


def set_sync_status(last_status: str, last_error: str | None = None, pull: bool = False, push: bool = False):
    now = utc_now_iso()

    with closing(get_conn()) as conn:
        cur = conn.cursor()

        if pull:
            cur.execute("""
                UPDATE sync_status
                SET last_pull_at = ?, last_status = ?, last_error = ?
                WHERE id = 1
            """, (now, last_status, last_error))
        elif push:
            cur.execute("""
                UPDATE sync_status
                SET last_push_at = ?, last_status = ?, last_error = ?
                WHERE id = 1
            """, (now, last_status, last_error))
        else:
            cur.execute("""
                UPDATE sync_status
                SET last_status = ?, last_error = ?
                WHERE id = 1
            """, (last_status, last_error))

        conn.commit()


def set_setting(key: str, value: str):
    now = utc_now_iso()
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
        """, (key, value, now))
        conn.commit()


def list_settings():
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT key, value, updated_at FROM settings ORDER BY key")
        rows = cur.fetchall()

    return [
        {
            "key": row["key"],
            "value": row["value"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def pull_from_mock_center():
    mock_file = CONFIG_DIR / "central_mock.json"
    if not mock_file.exists():
        raise FileNotFoundError("central_mock.json not found")

    with open(mock_file, "r", encoding="utf-8") as f:
        payload = json.load(f)

    set_setting("client_code", payload.get("client_code", ""))
    set_setting("point_code", payload.get("point_code", ""))

    settings = payload.get("settings", {})
    for key, value in settings.items():
        set_setting(f"setting:{key}", json.dumps(value, ensure_ascii=False))

    for item in payload.get("inventory", []):
        upsert_inventory_item(
            item_id=item["item_id"],
            available_qty=item.get("available_qty", 0),
            is_available=item.get("is_available", True),
        )

    for media in payload.get("media", []):
        upsert_media_asset(
            asset_key=media["asset_key"],
            asset_type=media["asset_type"],
            external_url=media.get("external_url"),
            local_path=media.get("local_path"),
            mime_type=media.get("mime_type"),
            checksum=media.get("checksum"),
            is_downloaded=False,
        )

    set_sync_status("ok", None, pull=True)

    return {
        "status": "ok",
        "client_code": payload.get("client_code"),
        "point_code": payload.get("point_code"),
        "inventory_count": len(payload.get("inventory", [])),
        "media_count": len(payload.get("media", [])),
        "settings_count": len(settings),
    }
