from __future__ import annotations

from typing import Any

from app.core.config import LABEL_PRINTER_CODEPAGE, LABEL_SIZE_MM

LABEL_CHAR_WIDTH = 28
ITEM_CHAR_WIDTH = 24

# XPrinter ESC/POS table 17 is commonly PC866 Cyrillic. The actual text bytes
# are encoded as cp866 below so Russian/Kazakh-compatible Cyrillic does not get
# sent as UTF-8 garbage to the printer.
ESC_POS_CODEPAGE_ID = 17


def format_service_mode(service_mode: str) -> str:
    return "С СОБОЙ" if service_mode == "takeaway" else "В ЗАЛЕ"


def _clip(text: str, width: int = LABEL_CHAR_WIDTH) -> str:
    value = str(text or "").strip()
    if len(value) <= width:
        return value
    return value[: max(1, width - 1)] + "…"


def _wrap(text: str, width: int = ITEM_CHAR_WIDTH, max_lines: int = 2) -> list[str]:
    value = str(text or "").strip()
    if not value:
        return []
    words = value.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word[:width]
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and len(" ".join(lines)) < len(value):
        lines[-1] = _clip(lines[-1], max(2, width - 1))
    return lines[:max_lines]


def expand_order_to_unit_labels(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand order quantities: qty=10 creates ten physical label payloads."""
    labels: list[dict[str, Any]] = []
    for item in payload.get("items") or []:
        qty = max(1, int(item.get("qty") or 1))
        for unit_no in range(1, qty + 1):
            labels.append(
                {
                    "item_id": item.get("item_id"),
                    "name": item.get("display_name") or item.get("name") or "Позиция",
                    "modifier_lines": list(item.get("modifier_lines") or []),
                    "line_unit_no": unit_no,
                    "line_unit_count": qty,
                }
            )

    total = len(labels)
    for index, label in enumerate(labels, start=1):
        label["label_no"] = index
        label["label_count"] = total
    return labels


def render_unit_label_58x40_text(payload: dict[str, Any], unit: dict[str, Any]) -> str:
    """Human-readable preview persisted in print_jobs for diagnostics/reprints."""
    width_mm, height_mm = LABEL_SIZE_MM
    order_number = str(payload.get("order_number") or "-")
    label_no = int(unit.get("label_no") or 1)
    label_count = int(unit.get("label_count") or 1)
    lines = [
        f"#SIZE:{width_mm}x{height_mm}mm",
        "JOJO'S",
        f"ЗАКАЗ #{order_number}   {label_no}/{label_count}",
        str(unit.get("name") or "Позиция"),
    ]
    for modifier in unit.get("modifier_lines") or []:
        lines.append(f"+ {modifier}")
    lines.append(format_service_mode(str(payload.get("service_mode") or "dine_in")))
    return "\n".join(lines) + "\n"


def _encode(text: str) -> bytes:
    return str(text).encode(LABEL_PRINTER_CODEPAGE, errors="replace")


def render_unit_label_58x40_escpos(payload: dict[str, Any], unit: dict[str, Any]) -> bytes:
    """Render one 58x40 label as ESC/POS bytes for XPrinter XP-365."""
    order_number = str(payload.get("order_number") or "-")
    label_no = int(unit.get("label_no") or 1)
    label_count = int(unit.get("label_count") or 1)
    item_name = str(unit.get("name") or "Позиция")
    modifiers = list(unit.get("modifier_lines") or [])

    out = bytearray()
    out += b"\x1b@"  # initialize
    out += b"\x1bt" + bytes([ESC_POS_CODEPAGE_ID])
    out += b"\x1b2"  # default line spacing

    # Brand/header.
    out += b"\x1ba\x01"  # center
    out += b"\x1bE\x01"  # bold on
    out += _encode("JOJO'S") + b"\n"

    # The order marker is deliberately the largest element on every label.
    out += b"\x1d!\x11"  # double width + double height
    out += _encode(f"#{order_number}") + b"\n"
    out += b"\x1d!\x00"
    out += _encode(f"ЭТИКЕТКА {label_no}/{label_count}") + b"\n"
    out += b"\x1bE\x00"

    # Product and selected add-ons/options.
    out += b"\x1ba\x00"  # left
    out += b"\x1bE\x01"
    for line in _wrap(item_name, ITEM_CHAR_WIDTH, max_lines=2):
        out += _encode(line) + b"\n"
    out += b"\x1bE\x00"

    # Keep the label readable: show up to three modifier lines and clip each.
    for modifier in modifiers[:3]:
        clean = str(modifier).strip()
        if clean.startswith("+"):
            clean = clean[1:].strip()
        out += _encode("+ " + _clip(clean, ITEM_CHAR_WIDTH - 2)) + b"\n"

    out += b"\x1ba\x01"
    out += _encode(format_service_mode(str(payload.get("service_mode") or "dine_in"))) + b"\n"

    # Form feed advances a gap/label-aware ESC/POS printer to the next label.
    # Do not send a cut command: XP-365 is used here as a label printer.
    out += b"\n\x0c"
    return bytes(out)


def render_kitchen_label_58x40_text(payload: dict[str, Any]) -> str:
    """Backward-compatible order preview used by older diagnostics."""
    labels = expand_order_to_unit_labels(payload)
    if not labels:
        return ""
    return "\n--- NEXT LABEL ---\n".join(render_unit_label_58x40_text(payload, unit).rstrip() for unit in labels) + "\n"
