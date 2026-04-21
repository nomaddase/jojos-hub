import json
from contextlib import closing
from copy import deepcopy
from typing import Any

from app.core.db import get_conn

RUNTIME_DEFAULTS = {
    "languages": ["ru", "kz", "en"],
    "default_language": "ru",
    "idle_timeout_seconds": 30,
    "branding": {
        "name": "JoJo’s",
    },
    "kitchen": {
        "warning_ratio": 0.7,
    },
    "display": {
        "ready_visibility_seconds": 300,
    },
    "service_modes": {
        "enabled": ["dine_in", "takeaway"],
        "default": "dine_in",
    },
    "printer": {
        "label_host": "192.168.0.240",
        "label_port": 9100,
        "auto_print_kitchen_label_on_create": True,
    },
}


def _parse_setting_value(value: str | None) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value


def _set_nested(target: dict, dotted_key: str, value: Any):
    parts = dotted_key.split(".")
    node = target
    for key in parts[:-1]:
        if key not in node or not isinstance(node[key], dict):
            node[key] = {}
        node = node[key]
    node[parts[-1]] = value


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _normalize_language(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_mode(value: Any) -> str:
    return str(value or "").strip().lower()


def _sanitize_effective_settings(raw_settings: dict) -> dict:
    result = deepcopy(raw_settings)

    languages = result.get("languages")
    if not isinstance(languages, list) or not languages:
        languages = deepcopy(RUNTIME_DEFAULTS["languages"])
    languages = [lang for lang in (_normalize_language(v) for v in languages) if lang]
    if not languages:
        languages = deepcopy(RUNTIME_DEFAULTS["languages"])
    result["languages"] = languages

    default_language = _normalize_language(result.get("default_language"))
    if default_language not in languages:
        default_language = languages[0]
    result["default_language"] = default_language

    idle_timeout_seconds = int(result.get("idle_timeout_seconds") or RUNTIME_DEFAULTS["idle_timeout_seconds"])
    result["idle_timeout_seconds"] = int(_clamp(idle_timeout_seconds, 10, 600))

    kitchen = result.get("kitchen") if isinstance(result.get("kitchen"), dict) else {}
    warning_ratio = float(kitchen.get("warning_ratio", RUNTIME_DEFAULTS["kitchen"]["warning_ratio"]))
    kitchen["warning_ratio"] = _clamp(warning_ratio, 0.1, 0.95)
    result["kitchen"] = kitchen

    display = result.get("display") if isinstance(result.get("display"), dict) else {}
    visibility = int(display.get("ready_visibility_seconds", RUNTIME_DEFAULTS["display"]["ready_visibility_seconds"]))
    display["ready_visibility_seconds"] = int(_clamp(visibility, 30, 1800))
    result["display"] = display

    service_modes = result.get("service_modes") if isinstance(result.get("service_modes"), dict) else {}
    enabled = service_modes.get("enabled") if isinstance(service_modes.get("enabled"), list) else []
    enabled = [mode for mode in (_normalize_mode(v) for v in enabled) if mode]
    if not enabled:
        enabled = deepcopy(RUNTIME_DEFAULTS["service_modes"]["enabled"])

    default_mode = _normalize_mode(service_modes.get("default"))
    if default_mode not in enabled:
        default_mode = enabled[0]

    service_modes["enabled"] = enabled
    service_modes["default"] = default_mode
    result["service_modes"] = service_modes

    printer = result.get("printer") if isinstance(result.get("printer"), dict) else {}
    printer["label_host"] = str(printer.get("label_host") or RUNTIME_DEFAULTS["printer"]["label_host"]).strip()
    printer["label_port"] = int(_clamp(float(printer.get("label_port") or RUNTIME_DEFAULTS["printer"]["label_port"]), 1, 65535))
    printer["auto_print_kitchen_label_on_create"] = bool(
        printer.get("auto_print_kitchen_label_on_create", RUNTIME_DEFAULTS["printer"]["auto_print_kitchen_label_on_create"])
    )
    result["printer"] = printer

    return result


def get_setting_value(key: str, default: Any = None) -> Any:
    setting_key = key if key.startswith("setting:") else f"setting:{key}"

    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = ?", (setting_key,))
        row = cur.fetchone()

    if not row:
        return default

    parsed = _parse_setting_value(row["value"])
    return default if parsed is None else parsed


def get_effective_settings() -> dict:
    result = deepcopy(RUNTIME_DEFAULTS)

    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM settings WHERE key LIKE 'setting:%'")
        rows = cur.fetchall()

    for row in rows:
        raw_key = row["key"][len("setting:") :]
        parsed = _parse_setting_value(row["value"])
        _set_nested(result, raw_key, parsed)

    return _sanitize_effective_settings(result)
