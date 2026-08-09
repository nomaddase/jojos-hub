from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.core.config import LABEL_SIZE_MM

LABEL_CHAR_WIDTH = 28
ITEM_CHAR_WIDTH = 24
DPI = 203
LABEL_WIDTH_PX = round(LABEL_SIZE_MM[0] / 25.4 * DPI)
LABEL_HEIGHT_PX = round(LABEL_SIZE_MM[1] / 25.4 * DPI)
MARGIN_X = 18
MARGIN_Y = 10

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
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, start_size: int, min_size: int = 14, *, bold: bool = False):
    size = start_size
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
    """Render the complete label to pixels so Cyrillic does not depend on printer codepages."""
    image = Image.new("1", (LABEL_WIDTH_PX, LABEL_HEIGHT_PX), 1)
    draw = ImageDraw.Draw(image)
    usable_width = LABEL_WIDTH_PX - MARGIN_X * 2

    order_number = str(payload.get("order_number") or "-")
    label_no = int(unit.get("label_no") or 1)
    label_count = int(unit.get("label_count") or 1)
    item_name = str(unit.get("name") or "Позиция").strip()
    modifiers = list(unit.get("modifier_lines") or [])[:3]

    y = MARGIN_Y

    brand = "JOJO'S"
    brand_font = _font(21, bold=True)
    draw.text((_center_x(draw, brand, brand_font), y), brand, font=brand_font, fill=0)
    y += 24

    marker = f"#{order_number}"
    marker_font = _fit_text(draw, marker, usable_width, 54, 34, bold=True)
    draw.text((_center_x(draw, marker, marker_font), y), marker, font=marker_font, fill=0)
    marker_box = draw.textbbox((0, 0), marker, font=marker_font)
    y += marker_box[3] - marker_box[1] + 3

    seq = f"ЭТИКЕТКА {label_no}/{label_count}"
    seq_font = _fit_text(draw, seq, usable_width, 19, 14, bold=True)
    draw.text((_center_x(draw, seq, seq_font), y), seq, font=seq_font, fill=0)
    y += 24

    draw.line((MARGIN_X, y, LABEL_WIDTH_PX - MARGIN_X, y), fill=0, width=2)
    y += 7

    product_lines = _wrap(item_name, 28, max_lines=2) or ["Позиция"]
    product_font = _font(25, bold=True)
    for line in product_lines:
        line_font = _fit_text(draw, line, usable_width, 25, 17, bold=True)
        draw.text((MARGIN_X, y), line, font=line_font, fill=0)
        box = draw.textbbox((0, 0), line, font=line_font)
        y += box[3] - box[1] + 4

    modifier_font = _font(18, bold=False)
    for modifier in modifiers:
        clean = str(modifier).strip()
        if clean.startswith("+"):
            clean = clean[1:].strip()
        text = "+ " + clean
        text = _clip(text, 35)
        line_font = _fit_text(draw, text, usable_width, 18, 14, bold=False)
        if y + 22 >= LABEL_HEIGHT_PX - 34:
            break
        draw.text((MARGIN_X, y), text, font=line_font, fill=0)
        y += 22

    service = format_service_mode(str(payload.get("service_mode") or "dine_in"))
    service_font = _fit_text(draw, service, usable_width, 20, 15, bold=True)
    service_y = LABEL_HEIGHT_PX - 31
    draw.rectangle((MARGIN_X, service_y - 3, LABEL_WIDTH_PX - MARGIN_X, LABEL_HEIGHT_PX - 7), outline=0, width=2)
    draw.text((_center_x(draw, service, service_font), service_y), service, font=service_font, fill=0)

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
    """
    Render one physical 58x40 label for XP-365 in ESC/POS mode.

    Raster output is intentionally used instead of printer fonts/codepages: it
    makes Russian text deterministic and matches the exact 58x40 canvas. The
    final ESC d feed command forces the printer to commit the raster buffer and
    move off the printed label instead of merely accepting bytes on TCP/9100.
    """
    image = _render_label_bitmap(payload, unit)
    out = bytearray()
    out += b"\x1b@"           # ESC @: reset to standard mode
    out += b"\x1ba\x00"      # left alignment
    out += _image_to_gs_v0(image)
    out += b"\x0a"            # LF: commit raster line
    out += b"\x1bd\x02"      # ESC d 2: explicit print-and-feed
    return bytes(out)


def render_kitchen_label_58x40_text(payload: dict[str, Any]) -> str:
    """Backward-compatible order preview used by diagnostics."""
    labels = expand_order_to_unit_labels(payload)
    if not labels:
        return ""
    return "\n--- NEXT LABEL ---\n".join(render_unit_label_58x40_text(payload, unit).rstrip() for unit in labels) + "\n"
