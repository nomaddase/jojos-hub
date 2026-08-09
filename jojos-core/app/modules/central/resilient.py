"""Resilient Base <-> Hub synchronization.

Core business flows (catalog/bootstrap and durable sales outbox) must not stop
because optional fleet telemetry fails. A stale Hub credential is also repaired
by re-enrolling the same physical installation on HTTP 401 only.
"""

from app.modules.central import service
from app.modules.central.outbox import pending_count
from app.modules.sync.service import set_sync_status


def _is_unauthorized(exc: Exception) -> bool:
    return "Base HTTP 401" in str(exc)


def _reenroll(base_url: str, identity: dict) -> dict:
    # Enrollment is keyed by immutable installation_id on Base, so this rotates
    # the credential for the same physical Hub without changing its assignment.
    identity = dict(identity)
    identity.pop("token", None)
    return service._enroll(base_url, identity)


def _heartbeat_core(base_url: str, identity: dict) -> tuple[dict, str | None]:
    report = service.build_version_report()
    cached = report.get("cached_releases") or {}
    payload = {
        "hub_version": report.get("hub") or {"version_code": 0, "version_name": "unknown"},
        "schema_version": "sqlite-v1",
        "outbox_pending": pending_count(),
        "last_pull_revision": 0,
        "cached_releases": {k: v for k, v in cached.items() if v is not None},
        "devices": report.get("devices") or [],
    }
    response = service._request_json(
        "POST",
        f"{base_url}/api/v1/hubs/{identity['hub_id']}/heartbeat",
        payload,
        token=identity["token"],
    )

    # Fleet telemetry is useful but must never block catalog pull or sales push.
    telemetry_error = None
    try:
        service._request_json(
            "POST",
            f"{base_url}/api/v1/hubs/{identity['hub_id']}/telemetry",
            {"cached_releases": cached},
            token=identity["token"],
        )
    except Exception as exc:  # optional channel
        telemetry_error = str(exc)

    identity["status"] = response.get("hub_status")
    identity["store_id"] = response.get("store_id")
    identity["desired_apps"] = response.get("desired_apps") or {}
    identity["last_heartbeat_at"] = service.now_iso()
    identity["last_error"] = None
    if telemetry_error:
        identity["last_telemetry_error"] = telemetry_error
        identity["last_telemetry_error_at"] = service.now_iso()
    else:
        identity.pop("last_telemetry_error", None)
        identity.pop("last_telemetry_error_at", None)
    service._save_identity(identity)
    return response, telemetry_error


def _heartbeat_with_recovery(base_url: str, identity: dict) -> tuple[dict, dict, str | None]:
    try:
        response, telemetry_error = _heartbeat_core(base_url, identity)
        return identity, response, telemetry_error
    except Exception as exc:
        if not _is_unauthorized(exc):
            raise
        identity = _reenroll(base_url, identity)
        response, telemetry_error = _heartbeat_core(base_url, identity)
        return identity, response, telemetry_error


def _push_with_recovery(base_url: str, identity: dict) -> tuple[dict, dict]:
    try:
        return identity, service._push_outbox(base_url, identity)
    except Exception as exc:
        if not _is_unauthorized(exc):
            raise
        identity = _reenroll(base_url, identity)
        return identity, service._push_outbox(base_url, identity)


def _bootstrap_with_recovery(base_url: str, identity: dict) -> tuple[dict, dict]:
    def fetch(current: dict) -> dict:
        return service._request_json(
            "GET",
            f"{base_url}/api/v1/hubs/{current['hub_id']}/bootstrap",
            token=current["token"],
        )

    try:
        return identity, fetch(identity)
    except Exception as exc:
        if not _is_unauthorized(exc):
            raise
        identity = _reenroll(base_url, identity)
        return identity, fetch(identity)


def sync_once() -> dict:
    with service._lock:
        base_url = (service.get_central_config().get("base_url") or "").rstrip("/")
        identity = service.get_identity()
        if not base_url:
            return {
                "status": "not_configured",
                "identity": {k: v for k, v in identity.items() if k != "token"},
            }

        errors: dict[str, str] = {}
        telemetry_error = None
        heartbeat = None
        outbox = None
        bootstrap_applied = False

        try:
            if not identity.get("hub_id") or not identity.get("token"):
                identity = service._enroll(base_url, identity)

            try:
                identity, heartbeat, telemetry_error = _heartbeat_with_recovery(base_url, identity)
            except Exception as exc:
                errors["heartbeat"] = str(exc)

            # Durable order events are a core flow and are attempted even when
            # heartbeat/fleet telemetry is temporarily unhealthy.
            try:
                identity, outbox = _push_with_recovery(base_url, identity)
            except Exception as exc:
                errors["outbox"] = str(exc)

            # Pull catalog/inventory whenever the Hub is known to be assigned.
            known_status = (heartbeat or {}).get("hub_status") or identity.get("status")
            known_store = (heartbeat or {}).get("store_id") or identity.get("store_id")
            if known_status == "active" and known_store:
                try:
                    identity, payload = _bootstrap_with_recovery(base_url, identity)
                    service._apply_bootstrap(payload)
                    identity["last_bootstrap_at"] = service.now_iso()
                    identity["status"] = "active"
                    identity["store_id"] = (payload.get("store") or {}).get("id") or known_store
                    service._save_identity(identity)
                    bootstrap_applied = True
                except Exception as exc:
                    errors["bootstrap"] = str(exc)

            # Telemetry is deliberately a warning, not a business-sync error.
            if telemetry_error:
                errors["telemetry"] = telemetry_error

            core_errors = {k: v for k, v in errors.items() if k != "telemetry"}
            status = "ok" if not core_errors else "degraded"
            if core_errors and not bootstrap_applied and outbox is None and heartbeat is None:
                status = "error"

            identity["last_error"] = None if status == "ok" else "; ".join(f"{k}: {v}" for k, v in core_errors.items())
            if identity.get("last_error"):
                identity["last_error_at"] = service.now_iso()
            service._save_identity(identity)
            set_sync_status("ok" if status in {"ok", "degraded"} else "error", identity.get("last_error"), push=outbox is not None, pull=bootstrap_applied)

            return {
                "status": status,
                "hub_id": identity.get("hub_id"),
                "hub_status": (heartbeat or {}).get("hub_status") or identity.get("status"),
                "store_id": (heartbeat or {}).get("store_id") or identity.get("store_id"),
                "desired_apps": (heartbeat or {}).get("desired_apps") or identity.get("desired_apps") or {},
                "outbox": outbox,
                "bootstrap": "applied" if bootstrap_applied else "not_applied",
                "warnings": {"telemetry": telemetry_error} if telemetry_error else {},
                "errors": core_errors,
                "error": "; ".join(f"{k}: {v}" for k, v in core_errors.items()) if core_errors else None,
            }
        except Exception as exc:
            identity["last_error"] = str(exc)
            identity["last_error_at"] = service.now_iso()
            service._save_identity(identity)
            set_sync_status("error", str(exc))
            return {
                "status": "error",
                "error": str(exc),
                "hub_id": identity.get("hub_id"),
                "outbox_pending": pending_count(),
            }


def pull_bootstrap() -> dict:
    with service._lock:
        base_url = (service.get_central_config().get("base_url") or "").rstrip("/")
        if not base_url:
            raise RuntimeError("Central Base URL is not configured")
        identity = service.get_identity()
        if not identity.get("hub_id") or not identity.get("token"):
            identity = service._enroll(base_url, identity)
        identity, payload = _bootstrap_with_recovery(base_url, identity)
        service._apply_bootstrap(payload)
        identity["last_bootstrap_at"] = service.now_iso()
        identity["status"] = "active"
        identity["store_id"] = (payload.get("store") or {}).get("id")
        identity["last_error"] = None
        service._save_identity(identity)
        return payload


def central_status() -> dict:
    return service.central_status()


def set_central_config(base_url: str) -> dict:
    return service.set_central_config(base_url)


# The background worker in service.py resolves this global at runtime. Replacing
# it here means both API-triggered and periodic synchronization use the same
# resilient implementation once central.routes imports this module.
service.sync_once = sync_once
