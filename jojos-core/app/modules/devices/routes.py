import json
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.config import CONFIG_DIR
from app.core.db import get_conn

router = APIRouter()

ALLOWED_APP_ROLES = {"kso", "kitchen", "display"}
ONLINE_WINDOW_SECONDS = 90
IDENTITY_PATH = CONFIG_DIR / "central_identity.json"


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
    hub_installation_id: Optional[str] = None
    binding_id: Optional[str] = None


class DeviceBindRequest(BaseModel):
    device_id: str = Field(min_length=3, max_length=128)
    app_role: str
    version_code: int = Field(ge=1)
    version_name: str = Field(min_length=1, max_length=64)
    android_version: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    build_fingerprint: Optional[str] = None
    previous_hub_installation_id: Optional[str] = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_identity() -> dict:
    try:
        value = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            value = {}
    except Exception:
        value = {}

    if not value.get("installation_id"):
        value["installation_id"] = str(uuid4())
        value["created_at"] = utc_now_iso()
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = Path(str(IDENTITY_PATH) + ".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(IDENTITY_PATH)
    return value


def hub_identity_public() -> dict:
    identity = _read_identity()
    return {
        "installation_id": identity["installation_id"],
        "hub_id": identity.get("hub_id"),
        "store_id": identity.get("store_id"),
        "hub_status": identity.get("status"),
    }


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
                hub_installation_id,
                binding_id,
                bound_at,
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


def _validate_role(role: str) -> str:
    normalized = role.strip().lower()
    if normalized not in ALLOWED_APP_ROLES:
        raise HTTPException(status_code=400, detail="Unsupported app role")
    return normalized


@router.get("/api/hub/identity")
def get_hub_identity():
    """Public LAN identity used by Android clients to detect a different physical Hub."""
    return hub_identity_public()


@router.post("/api/devices/bind")
def bind_device(payload: DeviceBindRequest, request: Request):
    app_role = _validate_role(payload.app_role)
    identity = hub_identity_public()
    installation_id = identity["installation_id"]
    now = utc_now_iso()
    last_ip = request.client.host if request.client else None

    previous_hub = (payload.previous_hub_installation_id or "").strip() or None
    rebound = previous_hub is not None and previous_hub != installation_id

    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT binding_id, hub_installation_id, first_seen_at, bound_at FROM devices WHERE device_id = ?",
            (payload.device_id,),
        )
        existing = cur.fetchone()

        if existing and existing["hub_installation_id"] == installation_id and existing["binding_id"]:
            binding_id = existing["binding_id"]
            bound_at = existing["bound_at"] or now
            first_seen_at = existing["first_seen_at"] or now
        else:
            binding_id = str(uuid4())
            bound_at = now
            first_seen_at = existing["first_seen_at"] if existing else now

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
                hub_installation_id,
                binding_id,
                bound_at,
                first_seen_at,
                last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                app_role = excluded.app_role,
                version_code = excluded.version_code,
                version_name = excluded.version_name,
                android_version = excluded.android_version,
                model = excluded.model,
                manufacturer = excluded.manufacturer,
                build_fingerprint = excluded.build_fingerprint,
                last_ip = excluded.last_ip,
                hub_installation_id = excluded.hub_installation_id,
                binding_id = excluded.binding_id,
                bound_at = excluded.bound_at,
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
                "current",
                None,
                last_ip,
                installation_id,
                binding_id,
                bound_at,
                first_seen_at,
                now,
            ),
        )
        conn.commit()

    return {
        "status": "ok",
        "device_id": payload.device_id,
        "app_role": app_role,
        "hub_installation_id": installation_id,
        "hub_id": identity.get("hub_id"),
        "store_id": identity.get("store_id"),
        "hub_status": identity.get("hub_status"),
        "binding_id": binding_id,
        "rebound": rebound,
        "server_time": now,
        "heartbeat_interval_seconds": 30,
    }


@router.post("/api/devices/heartbeat")
def device_heartbeat(payload: DeviceHeartbeatRequest, request: Request):
    app_role = _validate_role(payload.app_role)
    identity = hub_identity_public()
    installation_id = identity["installation_id"]

    if payload.hub_installation_id and payload.hub_installation_id != installation_id:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "hub_rebind_required",
                "hub_installation_id": installation_id,
                "hub_id": identity.get("hub_id"),
                "store_id": identity.get("store_id"),
            },
        )

    now = utc_now_iso()
    last_ip = request.client.host if request.client else None

    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT binding_id, hub_installation_id FROM devices WHERE device_id = ?",
            (payload.device_id,),
        )
        existing = cur.fetchone()

        if payload.binding_id:
            if (
                not existing
                or existing["binding_id"] != payload.binding_id
                or existing["hub_installation_id"] != installation_id
            ):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "device_binding_required",
                        "hub_installation_id": installation_id,
                    },
                )

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
                hub_installation_id,
                binding_id,
                bound_at,
                first_seen_at,
                last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                installation_id if payload.hub_installation_id else None,
                payload.binding_id,
                now if payload.binding_id else None,
                now,
                now,
            ),
        )
        conn.commit()

    return {
        "status": "ok",
        "server_time": now,
        "hub_installation_id": installation_id,
        "hub_id": identity.get("hub_id"),
        "store_id": identity.get("store_id"),
        "heartbeat_interval_seconds": 30,
    }


@router.get("/api/devices")
def get_devices():
    devices = list_devices()
    return {
        "hub": hub_identity_public(),
        "items": devices,
        "total": len(devices),
        "online": sum(1 for item in devices if item["online"]),
    }
