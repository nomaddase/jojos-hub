import json
from pathlib import Path

from fastapi import APIRouter

from app.core.config import PROJECT_DIR
from app.modules.apps.routes import read_release_manifest
from app.modules.devices.routes import list_devices

router = APIRouter()


def read_hub_version() -> dict:
    path = PROJECT_DIR / "version.json"
    if not path.exists():
        return {"version_code": 0, "version_name": "unknown"}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version_code": 0, "version_name": "unknown"}

    return {
        "version_code": int(data.get("version_code") or 0),
        "version_name": str(data.get("version_name") or "unknown"),
    }


def build_version_report() -> dict:
    # Device rows are intentionally retained in the local Hub database as
    # history, but only devices that are actually heartbeating now belong in
    # the Central Base heartbeat. Reporting every historical row caused Base to
    # refresh their last_seen_at every 30 seconds, making every old reinstall
    # look like a currently connected KSO/Kitchen device forever.
    devices = [
        item
        for item in list_devices()
        if item.get("online") and item.get("app_role") in {"kso", "kitchen"}
    ]

    releases = {}
    for role in ("kso", "kitchen"):
        try:
            releases[role] = read_release_manifest(role)
        except Exception as exc:
            releases[role] = {
                "error": str(exc),
            }

    return {
        "hub": read_hub_version(),
        "cached_releases": releases,
        "devices": devices,
    }


@router.get("/api/system/version")
def system_version():
    return build_version_report()
