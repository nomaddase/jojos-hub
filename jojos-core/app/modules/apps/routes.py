import hashlib
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import RELEASES_DIR

router = APIRouter()

APP_FILES = {
    "kso": "jojos-kso-latest.apk",
    "kitchen": "jojos-kitchen-latest.apk",
}


def _release_dir(app_role: str) -> Path:
    role = app_role.strip().lower()
    if role not in APP_FILES:
        raise HTTPException(status_code=404, detail="Unknown application role")
    return RELEASES_DIR / role


def _apk_path(app_role: str) -> Path:
    role = app_role.strip().lower()
    return _release_dir(role) / APP_FILES[role]


def _manifest_path(app_role: str) -> Path:
    return _release_dir(app_role) / "version.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_release_manifest(app_role: str) -> dict | None:
    role = app_role.strip().lower()
    manifest_path = _manifest_path(role)
    apk_path = _apk_path(role)

    if not manifest_path.exists() or not apk_path.exists():
        return None

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Invalid release manifest: {exc}")

    if not isinstance(manifest, dict):
        raise HTTPException(status_code=500, detail="Invalid release manifest")

    actual_size = apk_path.stat().st_size
    expected_size = manifest.get("size_bytes")
    if expected_size is not None and int(expected_size) != actual_size:
        raise HTTPException(status_code=503, detail="Cached APK size does not match manifest")

    expected_sha = str(manifest.get("sha256") or "").lower()
    if expected_sha:
        actual_sha = _sha256(apk_path)
        if actual_sha != expected_sha:
            raise HTTPException(status_code=503, detail="Cached APK checksum does not match manifest")

    return {
        **manifest,
        "app": role,
        "apk_url": f"/api/apps/{role}/apk",
        "size_bytes": actual_size,
    }


@router.get("/api/apps/{app_role}/version")
def app_version(app_role: str):
    manifest = read_release_manifest(app_role)
    if manifest is None:
        raise HTTPException(status_code=404, detail="No APK release cached on this hub")
    return manifest


@router.get("/api/apps/{app_role}/apk")
def app_apk(app_role: str):
    role = app_role.strip().lower()
    manifest = read_release_manifest(role)
    if manifest is None:
        raise HTTPException(status_code=404, detail="No APK release cached on this hub")

    path = _apk_path(role)
    return FileResponse(
        path=str(path),
        media_type="application/vnd.android.package-archive",
        filename=APP_FILES[role],
        headers={
            "ETag": f'"sha256:{manifest.get("sha256", "")}"',
            "Cache-Control": "no-cache",
        },
    )
