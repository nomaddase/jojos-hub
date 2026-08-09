from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.modules.settings.service import get_effective_settings

DPI = 203
DOTS_PER_MM = DPI / 25.4
LABEL_WIDTH_MM = 58
LABEL_HEIGHT_MM = 40
LABEL_WIDTH_PX = round(LABEL_WIDTH_MM * DOTS_PER_MM)
LABEL_HEIGHT_PX = round(LABEL_HEIGHT_MM * DOTS_PER_MM)

DEFAULT_TEMPLATE = {
    "calibration": {"x_offset_mm": 0.0, "y_offset_mm": 0.0, "gap_mm": 3.0, "density": 8, "invert_bitmap": False},
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

FONT_REGULAR = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
]
FONT_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
]


def _merge(base: dict, override: dict) -> dict:
    result = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def get_label_template() -> dict:
    settings = get_effective_settings()
    network = settings.get("network") if isinstance(settings.get("network"), dict) else {}
    printer = settings.get("printer") if isinstance(settings.get("printer"), dict) else {}
    override = network.get("label_template") or printer.get("label_template") or {}
    return _merge(DEFAULT_TEMPLATE, override if isinstance(override, dict) else {})


def _font(size: int, bold: bool):
    for candidate in (FONT_BOLD if bold else FONT_REGULAR):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=max(8, int(size)))
    return ImageFont.load_default()


def _mm(value: Any) -> int:
    try:
        return round(float(value) * DOTS_PER_MM)
    except Exception:
        return 0


def _fit(draw: ImageDraw.ImageDraw, text: str, max_width: int, size: int, bold: bool):
    current = max(8, int(size))
    while current > 8:
        font = _font(current, bold)
        box = draw.textbbox((0, 0), text, font=font)
        if box[2] - box[0] <= max_width:
            return font
        current -= 1
    return _font(8, bold)


def _draw_text(draw: ImageDraw.ImageDraw, text: str, cfg: dict, ox: float, oy: float, *, fill: int = 0):
    if cfg.get("visible", True) is False:
        return
    x = _mm(float(cfg.get("x") or 0) + ox)
    y = _mm(float(cfg.get("y") or 0) + oy)
    width = max(1, _mm(cfg.get("w") or 20))
    font = _fit(draw, text, width, int(cfg.get("font_size") or 16), bool(cfg.get("bold")))
    box = draw.textbbox((0, 0), text, font=font)
    text_width = box[2] - box[0]
    align = str(cfg.get("align") or "left")
    if align == "center":
        tx = x + max(0, (width - text_width) // 2)
    elif align == "right":
        tx = x + max(0, width - text_width)
    else:
        tx = x
    draw.text((tx, y), text, font=font, fill=fill)


def _created_at(value: Any) -> str:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone().strftime("%d.%m %H:%M")
    except Exception:
        return str(value or "")[:16]


def _wrap(draw: ImageDraw.ImageDraw, text: str, width_px: int, font_size: int, bold: bool, max_lines: int) -> list[tuple[str, Any]]:
    words = str(text or "").split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        font = _font(font_size, bold)
        if draw.textbbox((0, 0), candidate, font=font)[2] <= width_px:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    result = []
    for line in lines[:max_lines]:
        result.append((line, _fit(draw, line, width_px, font_size, bold)))
    return result


def render_label_bitmap(payload: dict[str, Any], unit: dict[str, Any]) -> Image.Image:
    template = get_label_template()
    calibration = template.get("calibration") or {}
    fields = template.get("fields") or {}
    ox = float(calibration.get("x_offset_mm") or 0)
    oy = float(calibration.get("y_offset_mm") or 0)

    image = Image.new("1", (LABEL_WIDTH_PX, LABEL_HEIGHT_PX), 1)
    draw = ImageDraw.Draw(image)

    _draw_text(draw, "JOJO'S", fields.get("brand", {}), ox, oy)
    _draw_text(draw, _created_at(payload.get("created_at")), fields.get("datetime", {}), ox, oy)
    _draw_text(draw, f"#{payload.get('order_number') or '-'}", fields.get("order", {}), ox, oy)
    _draw_text(draw, f"{int(unit.get('label_no') or 1)} / {int(unit.get('label_count') or 1)}", fields.get("sequence", {}), ox, oy)

    product_cfg = fields.get("product", {})
    if product_cfg.get("visible", True) is not False:
        x = _mm(float(product_cfg.get("x") or 0) + ox)
        y = _mm(float(product_cfg.get("y") or 0) + oy)
        width = max(1, _mm(product_cfg.get("w") or 54))
        size = int(product_cfg.get("font_size") or 23)
        bold = bool(product_cfg.get("bold", True))
        for line, font in _wrap(draw, str(unit.get("name") or "Позиция"), width, size, bold, 2):
            draw.text((x, y), line, font=font, fill=0)
            y += max(15, draw.textbbox((0, 0), line, font=font)[3] + 2)

    modifiers_cfg = fields.get("modifiers", {})
    if modifiers_cfg.get("visible", True) is not False:
        x = _mm(float(modifiers_cfg.get("x") or 0) + ox)
        y = _mm(float(modifiers_cfg.get("y") or 0) + oy)
        width = max(1, _mm(modifiers_cfg.get("w") or 54))
        size = int(modifiers_cfg.get("font_size") or 15)
        bold = bool(modifiers_cfg.get("bold", False))
        for raw in list(unit.get("modifier_lines") or [])[:3]:
            text = str(raw).strip()
            if text and not text.startswith("+"):
                text = "+ " + text
            font = _fit(draw, text, width, size, bold)
            draw.text((x, y), text, font=font, fill=0)
            y += max(13, draw.textbbox((0, 0), text, font=font)[3] + 2)

    service_cfg = fields.get("service", {})
    if service_cfg.get("visible", True) is not False:
        x = _mm(float(service_cfg.get("x") or 0) + ox)
        y = _mm(float(service_cfg.get("y") or 0) + oy)
        w = max(1, _mm(service_cfg.get("w") or 54))
        h = max(1, _mm(service_cfg.get("h") or 5))
        takeaway = str(payload.get("service_mode") or "dine_in") == "takeaway"
        text = "С СОБОЙ" if takeaway else "В ЗАЛЕ"
        font = _fit(draw, text, w - 6, int(service_cfg.get("font_size") or 17), bool(service_cfg.get("bold", True)))
        box = draw.textbbox((0, 0), text, font=font)
        tx = x + max(0, (w - (box[2] - box[0])) // 2)
        ty = y + max(0, (h - (box[3] - box[1])) // 2) - 1
        if takeaway:
            draw.rectangle((x, y, min(LABEL_WIDTH_PX - 1, x + w), min(LABEL_HEIGHT_PX - 1, y + h)), fill=0)
            draw.text((tx, ty), text, font=font, fill=1)
        else:
            draw.text((tx, ty), text, font=font, fill=0)

    if bool(calibration.get("invert_bitmap", False)):
        image = ImageOps.invert(image.convert("L")).convert("1")
    return image
