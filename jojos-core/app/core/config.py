import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = APP_DIR.parent

DB_PATH = PROJECT_DIR / "jojos_core.db"
STATIC_DIR = PROJECT_DIR / "static"
DATA_DIR = PROJECT_DIR / "data"
MEDIA_DIR = DATA_DIR / "media"
CONFIG_DIR = PROJECT_DIR / "config"
RELEASES_DIR = Path(
    os.environ.get("JOJOS_RELEASES_DIR", str(PROJECT_DIR.parent / "jojos-releases"))
)

READY_VISIBLE_SECONDS = 300

# JoJo production label printer.
# XPrinter XP-365, Wi-Fi, ESC/POS over the standard RAW TCP printing port.
# The address is reserved on every Hub LAN so the printer configuration is the
# same at every point.
LABEL_PRINTER_MODEL = "XPrinter XP-365"
LABEL_PRINTER_PROTOCOL = "escpos"
LABEL_PRINTER_HOST = os.environ.get("JOJOS_LABEL_PRINTER_HOST", "192.168.50.100")
LABEL_PRINTER_PORT = int(os.environ.get("JOJOS_LABEL_PRINTER_PORT", "9100"))
LABEL_SIZE_MM = (58, 40)
LABEL_PRINTER_CODEPAGE = "cp866"
