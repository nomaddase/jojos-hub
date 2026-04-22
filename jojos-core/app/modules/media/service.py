from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import shutil
import urllib.request

from app.core.config import MEDIA_DIR
from app.core.db import get_conn


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def list_media_assets():
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, asset_key, asset_type, external_url, local_path, mime_type,
                   checksum, is_downloaded, updated_at
            FROM media_assets
            ORDER BY id DESC
        """)
        rows = cur.fetchall()

    return [
        {
            "id": row["id"],
            "asset_key": row["asset_key"],
            "asset_type": row["asset_type"],
            "external_url": row["external_url"],
            "local_path": row["local_path"],
            "mime_type": row["mime_type"],
            "checksum": row["checksum"],
            "is_downloaded": bool(row["is_downloaded"]),
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def upsert_media_asset(
    asset_key: str,
    asset_type: str,
    external_url: str | None = None,
    local_path: str | None = None,
    mime_type: str | None = None,
    checksum: str | None = None,
    is_downloaded: bool = False,
):
    now = utc_now_iso()

    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO media_assets (
                asset_key, asset_type, external_url, local_path, mime_type,
                checksum, is_downloaded, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(asset_key) DO UPDATE SET
                asset_type = excluded.asset_type,
                external_url = excluded.external_url,
                local_path = excluded.local_path,
                mime_type = excluded.mime_type,
                checksum = excluded.checksum,
                is_downloaded = excluded.is_downloaded,
                updated_at = excluded.updated_at
            """,
            (
                asset_key,
                asset_type,
                external_url,
                local_path,
                mime_type,
                checksum,
                1 if is_downloaded else 0,
                now,
            ),
        )
        conn.commit()

    return {
        "asset_key": asset_key,
        "asset_type": asset_type,
        "external_url": external_url,
        "local_path": local_path,
        "mime_type": mime_type,
        "checksum": checksum,
        "is_downloaded": is_downloaded,
        "updated_at": now,
    }


def download_media_asset(asset_key: str):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT asset_key, asset_type, external_url, local_path, mime_type,
                   checksum, is_downloaded
            FROM media_assets
            WHERE asset_key = ?
        """, (asset_key,))
        row = cur.fetchone()

    if not row:
        raise ValueError("Media asset not found")

    if not row["external_url"]:
        raise ValueError("Media asset has no external_url")

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    filename = Path(row["external_url"]).name or f"{asset_key}.bin"
    destination = MEDIA_DIR / filename

    with urllib.request.urlopen(row["external_url"]) as response, open(destination, "wb") as out_file:
        shutil.copyfileobj(response, out_file)

    relative_local_path = str(destination.relative_to(MEDIA_DIR.parent))

    return upsert_media_asset(
        asset_key=row["asset_key"],
        asset_type=row["asset_type"],
        external_url=row["external_url"],
        local_path=relative_local_path,
        mime_type=row["mime_type"],
        checksum=row["checksum"],
        is_downloaded=True,
    )
