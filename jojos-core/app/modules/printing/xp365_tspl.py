from __future__ import annotations

from typing import Any

from app.modules.printing.dynamic_label import (
    DPI,
    LABEL_HEIGHT_MM,
    LABEL_HEIGHT_PX,
    LABEL_WIDTH_MM,
    LABEL_WIDTH_PX,
    get_label_template,
    render_label_bitmap,
)

DOTS_PER_MM = DPI / 25.4
LABEL_WIDTH_BYTES = (LABEL_WIDTH_PX + 7) // 8


def _image_to_tspl_bitmap(image) -> bytes:
    """Pack a 1-bit Pillow image for the TSPL BITMAP command (1 = black)."""
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

    return bytes(data)


def render_unit_label_58x40_tspl(payload: dict[str, Any], unit: dict[str, Any]) -> bytes:
    """Render one physical 58x40 label for XP-365 in TSPL label mode."""
    template = get_label_template()
    calibration = template.get("calibration") or {}
    image = render_label_bitmap(payload, unit)
    bitmap = _image_to_tspl_bitmap(image)

    if image.width != LABEL_WIDTH_PX or image.height != LABEL_HEIGHT_PX:
        raise ValueError(
            f"Unexpected label bitmap size {image.width}x{image.height}; "
            f"expected {LABEL_WIDTH_PX}x{LABEL_HEIGHT_PX}"
        )

    gap_mm = max(0.0, min(10.0, float(calibration.get("gap_mm") or 3.0)))
    density = max(1, min(15, int(calibration.get("density") or 8)))

    # IMPORTANT: XP-365 must be told the actual media size. The previous 76 mm
    # virtual page caused the 58 mm bitmap to be positioned as if the paper were
    # much wider, which produced the visible left shift / large blank right edge.
    prefix = (
        f"SIZE {LABEL_WIDTH_MM} mm,{LABEL_HEIGHT_MM} mm\r\n"
        f"GAP {gap_mm:g} mm,0 mm\r\n"
        "DIRECTION 1,0\r\n"
        "REFERENCE 0,0\r\n"
        f"DENSITY {density}\r\n"
        "CLS\r\n"
        f"BITMAP 0,0,{LABEL_WIDTH_BYTES},{LABEL_HEIGHT_PX},0,"
    ).encode("ascii")

    return prefix + bitmap + b"\r\nPRINT 1,1\r\n"
