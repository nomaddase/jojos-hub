from copy import deepcopy

from fastapi import APIRouter

from app.modules.catalog.service import get_catalog_data
from app.modules.inventory.service import get_inventory_map

router = APIRouter()


@router.get("/api/catalog")
def get_catalog():
    data = deepcopy(get_catalog_data())
    inventory_map = get_inventory_map()

    filtered_groups = []
    for group in data["groups"]:
        filtered_items = []

        for item in group["items"]:
            stock = inventory_map.get(item["id"])
            if stock is not None and (stock["is_available"] is False or int(stock.get("available_qty") or 0) == 0):
                continue

            option_groups = []
            for option_group in item.get("options", []):
                option_items = []
                for option_item in option_group.get("items", []):
                    option_stock = inventory_map.get(option_item["id"]) or inventory_map.get(
                        f"{item['id']}:{option_group['id']}:{option_item['id']}"
                    )
                    if option_stock is not None and (
                        option_stock["is_available"] is False or int(option_stock.get("available_qty") or 0) == 0
                    ):
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
