from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = APP_DIR.parent

DB_PATH = PROJECT_DIR / "jojos_core.db"
STATIC_DIR = PROJECT_DIR / "static"
DATA_DIR = PROJECT_DIR / "data"
MEDIA_DIR = DATA_DIR / "media"
CONFIG_DIR = PROJECT_DIR / "config"

READY_VISIBLE_SECONDS = 300
