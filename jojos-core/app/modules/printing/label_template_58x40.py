from app.core.config import LABEL_SIZE_MM


def format_service_mode(service_mode: str) -> str:
    return "TAKEAWAY" if service_mode == "takeaway" else "DINE IN"


def render_kitchen_label_58x40_text(payload: dict) -> str:
    width_mm, height_mm = LABEL_SIZE_MM
    lines: list[str] = [
        "=" * 24,
        "JOJO'S KITCHEN LABEL",
        f"ORDER #{payload['order_number']}",
        f"MODE: {format_service_mode(payload.get('service_mode') or 'dine_in')}",
        f"CREATED: {payload['created_at'][:19].replace('T', ' ')}",
        f"TARGET: {int(payload.get('target_prep_seconds') or 0) // 60} min",
        "-" * 24,
    ]

    for item in payload.get("items", []):
        lines.append(f"{item.get('qty', 1)}x {item.get('display_name') or item.get('name') or 'Item'}")
        for mod in item.get("modifier_lines", []):
            lines.append(f"  {mod}"[:42])

    lines.extend(["-" * 24, "KITCHEN COPY", "", ""])
    content = "\n".join(lines)
    return f"#SIZE:{width_mm}x{height_mm}mm\n{content}\n"
