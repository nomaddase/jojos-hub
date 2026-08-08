import json
from copy import deepcopy

from fastapi import APIRouter

from app.core.config import CONFIG_DIR
from app.modules.catalog.service import get_catalog_data
from app.modules.inventory.service import get_inventory_map

router = APIRouter()


def _catalog_source():
    cache = CONFIG_DIR / "catalog_cache.json"
    if cache.exists():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("groups"), list):
                return data
        except Exception:
            pass
    return get_catalog_data()


def _stock_blocks(stock: dict | None, required_qty: float = 1.0) -> bool:
    if stock is None:
        return False
    if stock.get("is_available") is False:
        return True
    qty = stock.get("available_qty")
    if qty is None:
        return False
    try:
        return float(qty) + 1e-9 < float(required_qty)
    except (TypeError, ValueError):
        return False


def _bom_stop_reason(item: dict, inventory_map: dict) -> dict | None:
    """Return the first missing ingredient for one menu unit, if any."""
    for line in item.get("bom") or []:
        component_id = str(line.get("component_id") or "").strip()
        if not component_id:
            continue
        try:
            required = float(line.get("qty") or 0)
        except (TypeError, ValueError):
            required = 0.0
        if required <= 0:
            continue
        stock = inventory_map.get(component_id)
        if _stock_blocks(stock, required):
            return {
                "component_id": component_id,
                "name": line.get("name") or component_id,
                "required_qty": required,
                "available_qty": None if stock is None else stock.get("available_qty"),
                "unit": line.get("unit") or "",
            }
    return None


@router.get("/api/catalog")
def get_catalog():
    data = deepcopy(_catalog_source())
    inventory_map = get_inventory_map()
    filtered_groups = []

    for group in data.get("groups", []):
        filtered_items = []
        for item in group.get("items", []):
            # Legacy/direct product stock remains supported.
            stock = inventory_map.get(item["id"])
            if _stock_blocks(stock, 1):
                continue

            # Primary stop-list rule: the product is hidden from KSO when the
            # point cannot make even one unit from its current ingredient stock.
            if _bom_stop_reason(item, inventory_map) is not None:
                continue

            option_groups = []
            for option_group in item.get("options", []):
                option_items = []
                for option_item in option_group.get("items", []):
                    option_stock = inventory_map.get(option_item["id"]) or inventory_map.get(
                        f"{item['id']}:{option_group['id']}:{option_item['id']}"
                    )
                    if _stock_blocks(option_stock, 1):
                        continue
                    option_items.append(option_item)
                if option_items:
                    option_group["items"] = option_items
                    option_groups.append(option_group)

            item["options"] = option_groups
            item["inventory"] = stock or {
                "item_id": item["id"],
                "available_qty": None,
                "is_available": True,
                "updated_at": None,
            }
            filtered_items.append(item)

        if filtered_items:
            group["items"] = filtered_items
            filtered_groups.append(group)

    data["groups"] = filtered_groups
    return data
