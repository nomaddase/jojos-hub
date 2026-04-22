from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.modules.media.service import (
    download_media_asset,
    list_media_assets,
    upsert_media_asset,
)

router = APIRouter()


class MediaAssetUpsertRequest(BaseModel):
    asset_key: str
    asset_type: str
    external_url: str | None = None
    local_path: str | None = None
    mime_type: str | None = None
    checksum: str | None = None
    is_downloaded: bool = False


@router.get("/api/media")
def get_media_assets():
    return {"items": list_media_assets()}


@router.post("/api/media")
def create_or_update_media_asset(payload: MediaAssetUpsertRequest):
    return upsert_media_asset(
        asset_key=payload.asset_key,
        asset_type=payload.asset_type,
        external_url=payload.external_url,
        local_path=payload.local_path,
        mime_type=payload.mime_type,
        checksum=payload.checksum,
        is_downloaded=payload.is_downloaded,
    )


@router.post("/api/media/{asset_key}/download")
def trigger_media_download(asset_key: str):
    try:
        return download_media_asset(asset_key)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
