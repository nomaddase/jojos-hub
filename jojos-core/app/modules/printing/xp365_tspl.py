from __future__ import annotations

from typing import Any

from app.modules.printing.label_template_58x40 import _render_label_bitmap

DPI = 203
DOTS_PER_MM = DPI / 25.4

# XP-365B is an 80 mm-class printer with a 76 mm maximum printable width.
# Our 58 mm media is centered in the paper path, therefore x=0 of the
# printhead is not the left edge of the physical sticker. Center the 58 mm
# bitmap inside the 76 mm printable area so no content disappears off the
# left edge.
PRINTHEAD_WIDTH_MM = 76
LABEL_WIDTH_MM = 58
LABEL_HEIGHT_MM = 40
PRINTHEAD_WIDTH_DOTS = round(PRINTHEAD_WIDTH_MM * DOTS_PER_MM)
LABEL_WIDTH_DOTS = round(LABEL_WIDTH_MM * DOTS_PER_MM)
LABEL_HEIGHT_DOTS = round(LABEL_HEIGHT_MM * DOTS_PER_MM)
LABEL_X_DOTS = max(0, (PRINTHEAD_WIDTH_DOTS - LABEL_WIDTH_DOTS) // 2)
LABEL_WIDTH_BYTES = (LABEL_WIDTH_DOTS + 7) // 8


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
    """
    Render one 58x40 sticker for XP-365 label mode.

    The printer accepted ESC/POS status commands but did not commit raster
    labels in receipt mode. XP-365 label mode is therefore driven with TSPL.
    We still rasterize the whole sticker so Cyrillic and layout are identical
    on every printer and do not depend on built-in code pages/fonts.
    """
    image = _render_label_bitmap(payload, unit)
    bitmap = _image_to_tspl_bitmap(image)

    if image.width != LABEL_WIDTH_DOTS or image.height != LABEL_HEIGHT_DOTS:
        raise ValueError(
            f"Unexpected label bitmap size {image.width}x{image.height}; "
            f"expected {LABEL_WIDTH_DOTS}x{LABEL_HEIGHT_DOTS}"
        )

    prefix = (
        f"SIZE {PRINTHEAD_WIDTH_MM} mm,{LABEL_HEIGHT_MM} mm\r\n"
        "GAP 3 mm,0 mm\r\n"
        "DIRECTION 1,0\r\n"
        "REFERENCE 0,0\r\n"
        "DENSITY 8\r\n"
        "CLS\r\n"
        f"BITMAP {LABEL_X_DOTS},0,{LABEL_WIDTH_BYTES},{LABEL_HEIGHT_DOTS},0,"
    ).encode("ascii")

    return prefix + bitmap + b"\r\nPRINT 1,1\r\n"
