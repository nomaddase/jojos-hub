from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.modules.inventory.service import list_inventory_items, upsert_inventory_item

router = APIRouter()


class InventoryUpdateRequest(BaseModel):
    item_id: str
    available_qty: int = Field(ge=0)
    is_available: bool


@router.get("/api/inventory")
def get_inventory():
    return {"items": list_inventory_items()}


@router.post("/api/inventory")
def update_inventory(payload: InventoryUpdateRequest):
    return upsert_inventory_item(
        item_id=payload.item_id,
        available_qty=payload.available_qty,
        is_available=payload.is_available,
    )
