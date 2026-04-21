from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import MEDIA_DIR, STATIC_DIR
from app.core.db import init_db
from app.modules.catalog.routes import router as catalog_router
from app.modules.display.routes import router as display_router
from app.modules.events.routes import router as events_router
from app.modules.inventory.routes import router as inventory_router
from app.modules.kitchen.routes import router as kitchen_router
from app.modules.media.routes import router as media_router
from app.modules.orders.routes import router as orders_router
from app.modules.printing.routes import router as printing_router
from app.modules.sync.routes import router as sync_router
from app.modules.ui.routes import router as ui_router

app = FastAPI(title="JoJo Core")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

if (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

if MEDIA_DIR.exists():
    app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

app.include_router(catalog_router)
app.include_router(orders_router)
app.include_router(printing_router)
app.include_router(kitchen_router)
app.include_router(display_router)
app.include_router(events_router)
app.include_router(inventory_router)
app.include_router(media_router)
app.include_router(sync_router)
app.include_router(ui_router)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/health")
def api_health():
    return {"status": "ok", "service": "jojos-core"}


@app.get("/health")
def legacy_health():
    return {"status": "ok", "service": "jojos-core"}
