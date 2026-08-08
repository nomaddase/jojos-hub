import hashlib
import html
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from app.core.config import RELEASES_DIR

router = APIRouter()

APP_FILES = {
    "kso": "jojos-kso-latest.apk",
    "kitchen": "jojos-kitchen-latest.apk",
}

APP_TITLES = {
    "kso": "JoJo KSO",
    "kitchen": "JoJo Kitchen",
}

_verified: dict[str, tuple[int, int, str]] = {}


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


def _validate_apk(role: str, apk_path: Path, expected_sha: str) -> None:
    stat = apk_path.stat()
    fingerprint = (stat.st_mtime_ns, stat.st_size, expected_sha)
    if _verified.get(role) == fingerprint:
        return
    actual_sha = _sha256(apk_path)
    if actual_sha != expected_sha:
        raise HTTPException(status_code=503, detail="Cached APK checksum does not match manifest")
    _verified[role] = fingerprint


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
        _validate_apk(role, apk_path, expected_sha)

    return {
        **manifest,
        "app": role,
        "apk_url": f"/api/apps/{role}/apk",
        "download_page_url": f"/download/{role}",
        "size_bytes": actual_size,
    }


def _apk_response(role: str):
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
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="{APP_FILES[role]}"',
        },
    )


def _download_page(role: str) -> str:
    role = role.strip().lower()
    if role not in APP_FILES:
        raise HTTPException(status_code=404, detail="Unknown application role")

    title = APP_TITLES[role]
    manifest = read_release_manifest(role)

    if manifest is None:
        release_block = """
        <div class="empty">
          APK пока не загружен на этот Hub.<br>
          Страница обновится автоматически через 3 секунды.
        </div>
        <script>setTimeout(function(){location.reload()},3000)</script>
        """
    else:
        version_name = html.escape(str(manifest.get("version_name") or "unknown"))
        version_code = html.escape(str(manifest.get("version_code") or "-"))
        sha = html.escape(str(manifest.get("sha256") or ""))
        size_mb = float(manifest.get("size_bytes") or 0) / 1024 / 1024
        release_block = f"""
        <div class="version">Версия <strong>{version_name}</strong> &nbsp; build #{version_code}</div>
        <a class="download" href="/download/{role}.apk" download>Скачать APK</a>
        <div class="meta">Размер: {size_mb:.1f} MB</div>
        <div class="meta sha">SHA-256: {sha}</div>
        """

    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Cache-Control" content="no-store">
<title>{title} — APK</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center; background:#fff7f8; color:#1d1d1f; font-family:Roboto,Arial,sans-serif; padding:24px; }}
  .card {{ width:min(620px,100%); background:#fff; border:1px solid #f0dadd; border-radius:24px; padding:34px; box-shadow:0 18px 55px rgba(60,0,8,.09); }}
  .brand {{ color:#e30613; font-size:14px; font-weight:900; letter-spacing:.15em; }}
  h1 {{ margin:10px 0 8px; font-size:34px; }}
  .hint {{ color:#70686a; line-height:1.5; margin-bottom:28px; }}
  .version {{ font-size:18px; margin-bottom:18px; }}
  .download {{ display:block; width:100%; padding:18px 22px; border-radius:14px; background:#e30613; color:#fff; text-decoration:none; text-align:center; font-weight:900; font-size:20px; box-shadow:0 8px 22px rgba(227,6,19,.20); }}
  .download:active {{ transform:scale(.99); background:#c40018; }}
  .meta {{ color:#81787a; font-size:13px; margin-top:14px; }}
  .sha {{ overflow-wrap:anywhere; }}
  .empty {{ padding:22px; border-radius:14px; background:#fff0f2; color:#6e343b; line-height:1.6; border:1px solid #ffd7dc; }}
  .links {{ margin-top:24px; display:flex; gap:12px; flex-wrap:wrap; }}
  .links a {{ color:#c40018; text-decoration:none; font-weight:700; }}
</style>
</head>
<body>
  <main class="card">
    <div class="brand">JOJO HUB</div>
    <h1>{title}</h1>
    <div class="hint">Локальная установка. APK скачивается напрямую с Hub, интернет не нужен.</div>
    {release_block}
    <div class="links">
      <a href="/download/kso">KSO</a>
      <a href="/download/kitchen">Kitchen</a>
      <a href="/api/health">Проверка Hub</a>
    </div>
  </main>
</body>
</html>"""


@router.get("/api/apps/{app_role}/version")
def app_version(app_role: str):
    manifest = read_release_manifest(app_role)
    if manifest is None:
        raise HTTPException(status_code=404, detail="No APK release cached on this hub")
    return manifest


@router.get("/api/apps/{app_role}/apk")
def app_apk(app_role: str):
    role = app_role.strip().lower()
    if role not in APP_FILES:
        raise HTTPException(status_code=404, detail="Unknown application role")
    return _apk_response(role)


@router.get("/download/{app_role}", response_class=HTMLResponse)
def app_download_page(app_role: str):
    return HTMLResponse(_download_page(app_role), headers={"Cache-Control": "no-store"})


@router.get("/download/{app_role}.apk")
def short_apk_download(app_role: str):
    role = app_role.strip().lower()
    if role not in APP_FILES:
        raise HTTPException(status_code=404, detail="Unknown application role")
    return _apk_response(role)
