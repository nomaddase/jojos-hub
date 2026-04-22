from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import STATIC_DIR

router = APIRouter()


def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend build not found")
    return FileResponse(str(index_file))


@router.get("/")
def root_ui():
    return serve_index()


@router.get("/kso")
def kso_ui():
    return serve_index()


@router.get("/kitchen")
def kitchen_ui():
    return serve_index()


@router.get("/display")
def display_ui():
    return serve_index()
