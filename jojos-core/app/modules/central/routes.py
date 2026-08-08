from fastapi import APIRouter
from pydantic import BaseModel

from app.modules.central.service import central_status, pull_bootstrap, set_central_config, sync_once

router = APIRouter()


class CentralConfigRequest(BaseModel):
    base_url: str


@router.get("/api/central/status")
def status():
    return central_status()


@router.post("/api/central/config")
def configure(payload: CentralConfigRequest):
    return {"status": "ok", "config": set_central_config(payload.base_url), "sync": sync_once()}


@router.post("/api/central/sync")
def sync_now():
    return sync_once()


@router.post("/api/central/bootstrap")
def bootstrap_now():
    return pull_bootstrap()
