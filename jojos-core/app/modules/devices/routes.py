from datetime import datetime, timezone
from contextlib import closing
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.db import get_conn

router = APIRouter()

ALLOWED_APP_ROLES = {"kso", "kitchen", "display"}
ONLINE_WINDOW_SECONDS = 90


class DeviceHeartbeatRequest(BaseModel):
    device_id: str = Field(min_length=3, max_length=128)
    app_role: str
    version_code: int = Field(ge=1)
    version_name: str = Field(min_length=1, max_length=64)
    android_version: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    build_fingerprint: Optional[str] = None
    update_status: Optional[str] = None
    update_error: Optional[str] = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_online(last_seen_at: str | None) -> bool:
    if not last_seen_at:
        return False
    try:
        seen = datetime.fromisoformat(last_seen_at.replace("Z", "+00:00"))
    except Exception:
        return False
    return (datetime.now(timezone.utc) - seen).total_seconds() <= ONLINE_WINDOW_SECONDS


def list_devices() -> list[dict]:
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                device_id,
                app_role,
                version_code,
                version_name,
                android_version,
                model,
                manufacturer,
                build_fingerprint,
                update_status,
                update_error,
                last_ip,
                first_seen_at,
                last_seen_at
            FROM devices
            ORDER BY app_role, device_id
            """
        )
        rows = cur.fetchall()

    return [
        {
            **dict(row),
            "online": _is_online(row["last_seen_at"]),
        }
        for row in rows
    ]


@router.post("/api/devices/heartbeat")
def device_heartbeat(payload: DeviceHeartbeatRequest, request: Request):
    app_role = payload.app_role.strip().lower()
    if app_role not in ALLOWED_APP_ROLES:
        raise HTTPException(status_code=400, detail="Unsupported app role")

    now = utc_now_iso()
    last_ip = request.client.host if request.client else None

    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO devices (
                device_id,
                app_role,
                version_code,
                version_name,
                android_version,
                model,
                manufacturer,
                build_fingerprint,
                update_status,
                update_error,
                last_ip,
                first_seen_at,
                last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                app_role = excluded.app_role,
                version_code = excluded.version_code,
                version_name = excluded.version_name,
                android_version = excluded.android_version,
                model = excluded.model,
                manufacturer = excluded.manufacturer,
                build_fingerprint = excluded.build_fingerprint,
                update_status = excluded.update_status,
                update_error = excluded.update_error,
                last_ip = excluded.last_ip,
                last_seen_at = excluded.last_seen_at
            """,
            (
                payload.device_id,
                app_role,
                payload.version_code,
                payload.version_name,
                payload.android_version,
                payload.model,
                payload.manufacturer,
                payload.build_fingerprint,
                payload.update_status,
                payload.update_error,
                last_ip,
                now,
                now,
            ),
        )
        conn.commit()

    return {
        "status": "ok",
        "server_time": now,
        "heartbeat_interval_seconds": 30,
    }


@router.get("/api/devices")
def get_devices():
    devices = list_devices()
    return {
        "items": devices,
        "total": len(devices),
        "online": sum(1 for item in devices if item["online"]),
    }
