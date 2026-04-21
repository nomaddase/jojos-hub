from app.core.config import LABEL_SIZE_MM

LABEL_CHAR_WIDTH = 24
ITEM_CHAR_WIDTH = 22


def format_service_mode(service_mode: str) -> str:
    return "TAKEAWAY" if service_mode == "takeaway" else "DINE IN"


def _clip(text: str, width: int = LABEL_CHAR_WIDTH) -> str:
    value = str(text or "").strip()
    if len(value) <= width:
        return value
    return f"{value[: width - 1]}…"


def _wrap_item_line(prefix: str, body: str, width: int = ITEM_CHAR_WIDTH) -> list[str]:
    text = _clip(body, width * 2)
    if len(text) <= width:
        return [f"{prefix}{text}"]
    return [f"{prefix}{text[:width]}", f"  {text[width:width * 2]}"]


def render_kitchen_label_58x40_text(payload: dict) -> str:
    width_mm, height_mm = LABEL_SIZE_MM
    created_raw = str(payload.get("created_at") or "")
    created_at = created_raw[:19].replace("T", " ")
    target_minutes = int(payload.get("target_prep_seconds") or 0) // 60

    lines: list[str] = [
        "=" * LABEL_CHAR_WIDTH,
        "JOJO'S KITCHEN",
        _clip(f"ORDER #{payload.get('order_number', '-')}", LABEL_CHAR_WIDTH),
        _clip(f"MODE: {format_service_mode(payload.get('service_mode') or 'dine_in')}", LABEL_CHAR_WIDTH),
        _clip(f"CREATED: {created_at}", LABEL_CHAR_WIDTH),
        _clip(f"TARGET: {target_minutes} min", LABEL_CHAR_WIDTH),
        "-" * LABEL_CHAR_WIDTH,
    ]

    for item in payload.get("items", []):
        qty = int(item.get("qty") or 1)
        name = item.get("display_name") or item.get("name") or "Item"
        lines.extend(_wrap_item_line(f"{qty}x ", str(name), ITEM_CHAR_WIDTH))

        for mod in item.get("modifier_lines", []):
            lines.extend(_wrap_item_line(" +", str(mod), ITEM_CHAR_WIDTH))

    lines.extend([
        "-" * LABEL_CHAR_WIDTH,
        "KITCHEN COPY / PROD",
        "",
        "",
    ])

    content = "\n".join(lines)
    return f"#SIZE:{width_mm}x{height_mm}mm\n{content}\n"
