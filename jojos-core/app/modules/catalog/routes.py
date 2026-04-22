from copy import deepcopy

from fastapi import APIRouter

from app.modules.catalog.service import CATALOG
from app.modules.inventory.service import get_inventory_map

router = APIRouter()


@router.get("/api/catalog")
def get_catalog():
    data = deepcopy(CATALOG)
    inventory_map = get_inventory_map()

    filtered_groups = []
    for group in data["groups"]:
        filtered_items = []

        for item in group["items"]:
            stock = inventory_map.get(item["id"])
            if stock is not None and stock["is_available"] is False:
                continue

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
