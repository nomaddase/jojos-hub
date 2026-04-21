import json
from contextlib import closing
from copy import deepcopy
from typing import Any

from app.core.db import get_conn

DEFAULT_SETTINGS = {
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
    result = deepcopy(DEFAULT_SETTINGS)

    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM settings WHERE key LIKE 'setting:%'")
        rows = cur.fetchall()

    for row in rows:
        raw_key = row["key"][len("setting:") :]
        parsed = _parse_setting_value(row["value"])
        _set_nested(result, raw_key, parsed)

    return result
