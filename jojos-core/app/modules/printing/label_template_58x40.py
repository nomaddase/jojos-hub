from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.core.config import LABEL_SIZE_MM
from app.modules.settings.service import get_setting_value

LABEL_CHAR_WIDTH = 28
ITEM_CHAR_WIDTH = 24
DPI = 203
DOTS_PER_MM = DPI / 25.4
LABEL_WIDTH_PX = round(LABEL_SIZE_MM[0] / 25.4 * DPI)
LABEL_HEIGHT_PX = round(LABEL_SIZE_MM[1] / 25.4 * DPI)
MARGIN_X = 18
MARGIN_Y = 10

DEFAULT_LABEL_TEMPLATE = {
    "version": 1,
    "width_mm": 58,
    "height_mm": 40,
    "calibration": {
        "x_offset_mm": 0.0,
        "y_offset_mm": 0.0,
        "gap_mm": 3.0,
        "density": 8,
        "invert_bitmap": False,
    },
    "fields": {
        "brand": {"x": 2.0, "y": 1.0, "w": 28.0, "font_size": 18, "bold": True, "align": "left", "visible": True},
        "datetime": {"x": 31.0, "y": 1.0, "w": 25.0, "font_size": 13, "bold": False, "align": "right", "visible": True},
        "order": {"x": 2.0, "y": 6.0, "w": 54.0, "font_size": 48, "bold": True, "align": "center", "visible": True},
        "sequence": {"x": 2.0, "y": 14.5, "w": 54.0, "font_size": 18, "bold": True, "align": "center", "visible": True},
        "product": {"x": 2.0, "y": 19.0, "w": 54.0, "font_size": 23, "bold": True, "align": "left", "visible": True},
        "modifiers": {"x": 2.0, "y": 27.0, "w": 54.0, "font_size": 15, "bold": False, "align": "left", "visible": True},
        "service": {"x": 2.0, "y": 34.0, "w": 54.0, "h": 5.0, "font_size": 17, "bold": True, "align": "center", "visible": True},
    },
}

FONT_CANDIDATES = {
    "regular": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ],
    "bold": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    ],
}


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
    return lines[:max_lines]


def _font(size: int, *, bold: bool = False):
    key = "bold" if bold else "regular"
    for candidate in FONT_CANDIDATES[key]:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=max(8, int(size)))
    return ImageFont.load_default()


def _fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, start_size: int, min_size: int = 8, *, bold: bool = False):
    size = max(min_size, int(start_size))
    while size > min_size:
        font = _font(size, bold=bold)
        box = draw.textbbox((0, 0), text, font=font)
        if box[2] - box[0] <= max_width:
            return font
        size -= 1
    return _font(min_size, bold=bold)


def _center_x(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return max(MARGIN_X, (LABEL_WIDTH_PX - (box[2] - box[0])) // 2)


def _merge_dict(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def get_runtime_label_template() -> dict:
    """Read the centrally managed label template mirrored by Hub bootstrap."""
    try:
        network = get_setting_value("network", {})
        if isinstance(network, dict):
            saved = network.get("label_template")
            if isinstance(saved, dict):
                return _merge_dict(DEFAULT_LABEL_TEMPLATE, saved)
    except Exception:
        pass
    return deepcopy(DEFAULT_LABEL_TEMPLATE)


def _mm(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _px(mm: Any) -> int:
    return round(_mm(mm) * DOTS_PER_MM)


def _align(value: Any) -> str:
    value = str(value or "left").lower()
    return value if value in {"left", "center", "right"} else "left"


def _format_created_at(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.strftime("%d.%m %H:%M")
    except Exception:
        return raw[:16].replace("T", " ")


def _field_lines(key: str, payload: dict[str, Any], unit: dict[str, Any]) -> list[str]:
    if key == "brand":
        return ["JOJO'S"]
    if key == "datetime":
        return [_format_created_at(payload.get("created_at"))]
    if key == "order":
        return [f"#{payload.get('order_number') or '-'}"]
    if key == "sequence":
        return [f"{int(unit.get('label_no') or 1)} / {int(unit.get('label_count') or 1)}"]
    if key == "product":
        return _wrap(str(unit.get("name") or "Позиция"), 28, max_lines=2) or ["Позиция"]
    if key == "modifiers":
        result = []
        for modifier in list(unit.get("modifier_lines") or [])[:3]:
            clean = str(modifier).strip()
            if clean.startswith("+"):
                clean = clean[1:].strip()
            result.append(_clip("+ " + clean, 35))
        return result
    if key == "service":
        return [format_service_mode(str(payload.get("service_mode") or "dine_in"))]
    return []


def _line_x(draw: ImageDraw.ImageDraw, text: str, font, x: int, width: int, align: str) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    text_width = max(0, box[2] - box[0])
    if align == "right":
        return x + max(0, width - text_width)
    if align == "center":
        return x + max(0, (width - text_width) // 2)
    return x


def _draw_template_field(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    key: str,
    cfg: dict[str, Any],
    payload: dict[str, Any],
    unit: dict[str, Any],
    offset_x: int,
    offset_y: int,
) -> None:
    if cfg.get("visible", True) is False:
        return

    x = _px(cfg.get("x")) + offset_x
    y = _px(cfg.get("y")) + offset_y
    width = max(1, _px(cfg.get("w", 20)))
    height = max(0, _px(cfg.get("h", 0)))
    align = _align(cfg.get("align"))
    bold = bool(cfg.get("bold", False))
    font_size = max(8, int(_mm(cfg.get("font_size"), 16)))
    lines = _field_lines(key, payload, unit)
    if not lines:
        return

    if key == "service" and height > 0:
        x2 = min(LABEL_WIDTH_PX - 1, x + width)
        y2 = min(LABEL_HEIGHT_PX - 1, y + height)
        if str(payload.get("service_mode") or "dine_in") == "takeaway":
            draw.rectangle((x, y, x2, y2), fill=0)
            fill = 1
        else:
            draw.rectangle((x, y, x2, y2), fill=1)
            fill = 0
    else:
        fill = 0

    cursor_y = y
    for line in lines:
        font = _fit_text(draw, line, width, font_size, 8, bold=bold)
        box = draw.textbbox((0, 0), line, font=font)
        line_height = max(1, box[3] - box[1])
        line_x = _line_x(draw, line, font, x, width, align)
        if key == "service" and height > 0:
            line_y = y + max(0, (height - line_height) // 2) - box[1]
        else:
            line_y = cursor_y
        draw.text((line_x, line_y), line, font=font, fill=fill)
        cursor_y += line_height + 3
        if cursor_y >= LABEL_HEIGHT_PX:
            break


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


def _render_label_bitmap(payload: dict[str, Any], unit: dict[str, Any]) -> Image.Image:
    """Render the complete label from the centrally managed 58x40 template."""
    template = get_runtime_label_template()
    calibration = template.get("calibration") if isinstance(template.get("calibration"), dict) else {}
    offset_x = _px(calibration.get("x_offset_mm", 0))
    offset_y = _px(calibration.get("y_offset_mm", 0))

    image = Image.new("1", (LABEL_WIDTH_PX, LABEL_HEIGHT_PX), 1)
    draw = ImageDraw.Draw(image)
    fields = template.get("fields") if isinstance(template.get("fields"), dict) else {}

    for key in ("brand", "datetime", "order", "sequence", "product", "modifiers", "service"):
        cfg = fields.get(key)
        if isinstance(cfg, dict):
            _draw_template_field(image, draw, key, cfg, payload, unit, offset_x, offset_y)

    if bool(calibration.get("invert_bitmap", False)):
        image = ImageOps.invert(image.convert("L")).convert("1")
    return image


def _image_to_gs_v0(image: Image.Image) -> bytes:
    """Encode a 1-bit Pillow image as the widely supported ESC/POS GS v 0 raster command."""
    mono = image.convert("1")
    width, height = mono.size
    width_bytes = (width + 7) // 8
    data = bytearray(width_bytes * height)
    pixels = mono.load()

    for y in range(height):
        row_offset = y * width_bytes
        for x in range(width):
            if pixels[x, y] == 0:
                data[row_offset + (x // 8)] |= 0x80 >> (x % 8)

    x_l = width_bytes & 0xFF
    x_h = (width_bytes >> 8) & 0xFF
    y_l = height & 0xFF
    y_h = (height >> 8) & 0xFF
    return b"\x1d\x76\x30\x00" + bytes((x_l, x_h, y_l, y_h)) + bytes(data)


def render_unit_label_58x40_escpos(payload: dict[str, Any], unit: dict[str, Any]) -> bytes:
    """Render one physical 58x40 label for XP-365 in ESC/POS mode."""
    image = _render_label_bitmap(payload, unit)
    out = bytearray()
    out += b"\x1b@"
    out += b"\x1ba\x00"
    out += _image_to_gs_v0(image)
    out += b"\x0a"
    out += b"\x1bd\x02"
    return bytes(out)


def render_kitchen_label_58x40_text(payload: dict[str, Any]) -> str:
    """Backward-compatible order preview used by diagnostics."""
    labels = expand_order_to_unit_labels(payload)
    if not labels:
        return ""
    return "\n--- NEXT LABEL ---\n".join(render_unit_label_58x40_text(payload, unit).rstrip() for unit in labels) + "\n"
