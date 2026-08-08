import json
import os
import socket
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from app.core.config import CONFIG_DIR
from app.modules.central.outbox import (
    mark_batch_error,
    mark_push_result,
    pending_count,
    pending_events,
    prune_delivered,
)
from app.modules.inventory.service import upsert_inventory_item
from app.modules.system.routes import build_version_report
from app.modules.sync.service import set_setting, set_sync_status

CONFIG_PATH = CONFIG_DIR / "central.json"
IDENTITY_PATH = CONFIG_DIR / "central_identity.json"
BOOTSTRAP_PATH = CONFIG_DIR / "central_bootstrap.json"
CATALOG_PATH = CONFIG_DIR / "catalog_cache.json"

_lock = threading.Lock()
_started = False


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path, default: dict | None = None) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(default or {})


def _write_json(path: Path, value: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    os.chmod(path, 0o600)


def get_central_config() -> dict:
    return _read_json(CONFIG_PATH, {"base_url": ""})


def set_central_config(base_url: str) -> dict:
    value = {"base_url": base_url.rstrip("/")}
    _write_json(CONFIG_PATH, value)
    return value


def get_identity() -> dict:
    identity = _read_json(IDENTITY_PATH)
    if not identity.get("installation_id"):
        identity["installation_id"] = str(uuid4())
        identity["created_at"] = now_iso()
        _write_json(IDENTITY_PATH, identity)
    return identity


def _save_identity(identity: dict):
    _write_json(IDENTITY_PATH, identity)


def _request_json(method: str, url: str, payload: dict | None = None, token: str | None = None, timeout: int = 10) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url=url, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Base HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Base connection error: {exc.reason}") from exc


def _enroll(base_url: str, identity: dict) -> dict:
    report = build_version_report()
    hub_version = report.get("hub") or {}
    response = _request_json(
        "POST",
        f"{base_url}/api/v1/hubs/enroll",
        {
            "installation_id": identity["installation_id"],
            "hostname": socket.gethostname(),
            "software_version": hub_version.get("version_name", "unknown"),
            "version_code": int(hub_version.get("version_code") or 0),
            "schema_version": "sqlite-v1",
            "capabilities": [
                "orders",
                "inventory",
                "printing",
                "apk-cache",
                "device-telemetry",
                "durable-outbox",
            ],
        },
    )
    identity.update({
        "hub_id": response["hub_id"],
        "token": response["credential"],
        "status": response.get("status"),
        "store_id": response.get("store_id"),
        "enrolled_at": identity.get("enrolled_at") or now_iso(),
        "last_error": None,
    })
    _save_identity(identity)
    return identity


def _heartbeat(base_url: str, identity: dict) -> dict:
    report = build_version_report()
    cached = report.get("cached_releases") or {}
    payload = {
        "hub_version": report.get("hub") or {"version_code": 0, "version_name": "unknown"},
        "schema_version": "sqlite-v1",
        "outbox_pending": pending_count(),
        "last_pull_revision": 0,
        "cached_releases": {k: v for k, v in cached.items() if v is not None},
        "devices": report.get("devices") or [],
    }
    response = _request_json(
        "POST",
        f"{base_url}/api/v1/hubs/{identity['hub_id']}/heartbeat",
        payload,
        token=identity["token"],
    )
    _request_json(
        "POST",
        f"{base_url}/api/v1/hubs/{identity['hub_id']}/telemetry",
        {"cached_releases": cached},
        token=identity["token"],
    )
    identity["status"] = response.get("hub_status")
    identity["store_id"] = response.get("store_id")
    identity["desired_apps"] = response.get("desired_apps") or {}
    identity["last_heartbeat_at"] = now_iso()
    identity["last_error"] = None
    _save_identity(identity)
    return response


def _push_outbox(base_url: str, identity: dict) -> dict:
    events = pending_events(100)
    if not events:
        return {"pending_before": 0, "accepted": 0, "rejected": 0, "pending_after": 0}
    event_ids = [event["event_id"] for event in events]
    wire_events = [
        {
            "event_id": event["event_id"],
            "type": event["type"],
            "created_at": event["created_at"],
            "payload": event["payload"],
        }
        for event in events
    ]
    try:
        response = _request_json(
            "POST",
            f"{base_url}/api/v1/hubs/{identity['hub_id']}/events",
            {"events": wire_events},
            token=identity["token"],
            timeout=15,
        )
    except Exception as exc:
        mark_batch_error(event_ids, str(exc))
        raise
    accepted = response.get("accepted") or []
    rejected = response.get("rejected") or []
    mark_push_result(accepted, rejected)
    prune_delivered()
    return {
        "pending_before": len(events),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "pending_after": pending_count(),
    }


def _apply_bootstrap(payload: dict):
    _write_json(BOOTSTRAP_PATH, payload)
    catalog = payload.get("catalog")
    if isinstance(catalog, dict):
        _write_json(CATALOG_PATH, catalog)

    # Base is authoritative for the point's ingredient balances. Mirror them
    # into the local Hub inventory table so /api/catalog can calculate the
    # stop list from each product BOM even while the KSO itself stays offline.
    for row in payload.get("inventory") or []:
        component_id = str(row.get("component_id") or "").strip()
        if not component_id:
            continue
        try:
            qty = float(row.get("qty") or 0)
        except (TypeError, ValueError):
            qty = 0.0
        upsert_inventory_item(component_id, qty, qty > 0)

    store = payload.get("store") or {}
    if store:
        set_setting("central:store_id", str(store.get("id") or ""))
        set_setting("central:store_code", str(store.get("code") or ""))
        set_setting("central:store_name", str(store.get("name") or ""))
    for key, value in (payload.get("settings") or {}).items():
        set_setting(f"setting:{key}", json.dumps(value, ensure_ascii=False))
    set_sync_status("ok", None, pull=True)


def pull_bootstrap() -> dict:
    with _lock:
        base_url = (get_central_config().get("base_url") or "").rstrip("/")
        if not base_url:
            raise RuntimeError("Central Base URL is not configured")
        identity = get_identity()
        if not identity.get("hub_id") or not identity.get("token"):
            identity = _enroll(base_url, identity)
        payload = _request_json("GET", f"{base_url}/api/v1/hubs/{identity['hub_id']}/bootstrap", token=identity["token"])
        _apply_bootstrap(payload)
        identity["last_bootstrap_at"] = now_iso()
        identity["status"] = "active"
        identity["store_id"] = (payload.get("store") or {}).get("id")
        identity["last_error"] = None
        _save_identity(identity)
        return payload


def sync_once() -> dict:
    with _lock:
        base_url = (get_central_config().get("base_url") or "").rstrip("/")
        identity = get_identity()
        if not base_url:
            return {"status": "not_configured", "identity": {k: v for k, v in identity.items() if k != "token"}}
        try:
            if not identity.get("hub_id") or not identity.get("token"):
                identity = _enroll(base_url, identity)
            heartbeat = _heartbeat(base_url, identity)
            outbox = _push_outbox(base_url, identity)
            result = {
                "status": "ok",
                "hub_id": identity.get("hub_id"),
                "hub_status": heartbeat.get("hub_status"),
                "store_id": heartbeat.get("store_id"),
                "desired_apps": heartbeat.get("desired_apps") or {},
                "outbox": outbox,
            }
            if heartbeat.get("hub_status") == "active" and heartbeat.get("store_id"):
                payload = _request_json("GET", f"{base_url}/api/v1/hubs/{identity['hub_id']}/bootstrap", token=identity["token"])
                _apply_bootstrap(payload)
                identity["last_bootstrap_at"] = now_iso()
                _save_identity(identity)
                result["bootstrap"] = "applied"
            set_sync_status("ok", None, push=True)
            return result
        except Exception as exc:
            identity["last_error"] = str(exc)
            identity["last_error_at"] = now_iso()
            _save_identity(identity)
            set_sync_status("error", str(exc))
            return {"status": "error", "error": str(exc), "hub_id": identity.get("hub_id"), "outbox_pending": pending_count()}


def central_status() -> dict:
    config = get_central_config()
    identity = get_identity()
    return {
        "configured": bool(config.get("base_url")),
        "base_url": config.get("base_url") or "",
        "identity": {k: v for k, v in identity.items() if k != "token"},
        "has_credential": bool(identity.get("token")),
        "bootstrap_cached": BOOTSTRAP_PATH.exists(),
        "catalog_cached": CATALOG_PATH.exists(),
        "outbox_pending": pending_count(),
    }


def _worker():
    while True:
        try:
            sync_once()
        except Exception:
            pass
        time.sleep(30)


def start_central_sync():
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_worker, name="jojos-central-sync", daemon=True).start()
