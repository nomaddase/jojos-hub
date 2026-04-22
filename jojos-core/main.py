from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
import uuid
import sqlite3
from contextlib import closing

app = FastAPI(title="JoJo Core")
app.mount("/assets", StaticFiles(directory="/home/admini/jojos-core/static/assets"), name="assets")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*" ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "/home/admini/jojos-core/jojos_core.db"
ALLOWED_STATUSES = {"created", "in_progress", "ready", "completed", "cancelled"}
READY_VISIBLE_SECONDS = 300  # 5 minutes


class OrderItemOption(BaseModel):
    group_id: str
    option_id: str
    name: Optional[str] = None


class OrderItem(BaseModel):
    item_id: str
    name: str
    qty: int = Field(gt=0)
    price: int = Field(ge=0)
    options: List[OrderItemOption] = []


class CreateOrderRequest(BaseModel):
    source: str = "kso"
    items: List[OrderItem]


class UpdateOrderStatusRequest(BaseModel):
    status: str


class OrderResponse(BaseModel):
    id: str
    number: str
    source: str
    status: str
    created_at: str
    accepted_at: Optional[str] = None
    ready_at: Optional[str] = None
    cancelled_at: Optional[str] = None
    total: int
    target_prep_seconds: int
    contains_sandwich: bool
    items: List[OrderItem]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso(dt: Optional[str]) -> Optional[datetime]:
    if not dt:
        return None
    return datetime.fromisoformat(dt.replace("Z", "+00:00"))


def seconds_since(dt: Optional[str]) -> Optional[int]:
    parsed = parse_iso(dt)
    if not parsed:
        return None
    return int((datetime.now(timezone.utc) - parsed).total_seconds())


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    rows = cur.fetchall()
    return any(row["name"] == column for row in rows)


def init_db():
    with closing(get_conn()) as conn:
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            number TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            total INTEGER NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            name TEXT NOT NULL,
            qty INTEGER NOT NULL,
            price INTEGER NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS order_item_options (
            id TEXT PRIMARY KEY,
            order_item_id TEXT NOT NULL,
            group_id TEXT NOT NULL,
            option_id TEXT NOT NULL,
            name TEXT,
            FOREIGN KEY(order_item_id) REFERENCES order_items(id)
        )
        """)

        # migrations for existing db
        needed_columns = [
            ("accepted_at", "TEXT"),
            ("ready_at", "TEXT"),
            ("cancelled_at", "TEXT"),
            ("target_prep_seconds", "INTEGER NOT NULL DEFAULT 120"),
            ("contains_sandwich", "INTEGER NOT NULL DEFAULT 0"),
        ]

        for col_name, col_type in needed_columns:
            if not column_exists(conn, "orders", col_name):
                cur.execute(f"ALTER TABLE orders ADD COLUMN {col_name} {col_type}")

        conn.commit()


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok", "service": "jojos-core"}


@app.get("/config")
def config():
    return {
        "device_id": "121154",
        "location": "test-point",
        "wifi_ssid": "KSO_CORE",
        "mode": "local-core",
        "display": {
            "ready_visible_seconds": READY_VISIBLE_SECONDS,
            "layout": "1920x1080"
        },
        "kitchen": {
            "default_prep_seconds": 120,
            "sandwich_prep_seconds": 240
        }
    }


@app.get("/catalog")
def catalog():
    return {
        "groups": [
            {
                "id": "pizza",
                "name": "Пицца",
                "items": [
                    {"id": "pizza23", "name": "Пицца 23 см", "price": 2400},
                    {"id": "pizza30", "name": "Пицца 30 см", "price": 3200},
                    {"id": "pizza45", "name": "Пицца 45 см", "price": 4700},
                ],
            },
            {
                "id": "drinks",
                "name": "Напитки",
                "items": [
                    {"id": "lemonade", "name": "Лимонад", "price": 1100},
                    {"id": "hotdrink", "name": "Горячий напиток", "price": 1250},
                    {"id": "water", "name": "Вода", "price": 500},
                ],
            },
            {
                "id": "sandwich",
                "name": "Сэндвичи",
                "items": [
                    {"id": "sandwich_meat", "name": "Сэндвич мясной", "price": 1100},
                    {"id": "sandwich_chicken", "name": "Сэндвич куриный", "price": 1100},
                    {"id": "sandwich_vegan", "name": "Сэндвич веган", "price": 1100},
                ],
            },
        ]
    }


def order_contains_sandwich(items: List[OrderItem]) -> bool:
    for item in items:
        item_id = item.item_id.lower()
        item_name = item.name.lower()
        if "sandwich" in item_id or "сэндвич" in item_name:
            return True
    return False


def build_order_response(order_id: str) -> dict:
    with closing(get_conn()) as conn:
        cur = conn.cursor()

        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order = cur.fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        cur.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
        item_rows = cur.fetchall()

        items = []
        for item in item_rows:
            cur.execute(
                "SELECT group_id, option_id, name FROM order_item_options WHERE order_item_id = ?",
                (item["id"],)
            )
            options = [
                {
                    "group_id": opt["group_id"],
                    "option_id": opt["option_id"],
                    "name": opt["name"],
                }
                for opt in cur.fetchall()
            ]

            items.append({
                "item_id": item["item_id"],
                "name": item["name"],
                "qty": item["qty"],
                "price": item["price"],
                "options": options,
            })

        return {
            "id": order["id"],
            "number": order["number"],
            "source": order["source"],
            "status": order["status"],
            "created_at": order["created_at"],
            "accepted_at": order["accepted_at"],
            "ready_at": order["ready_at"],
            "cancelled_at": order["cancelled_at"],
            "total": order["total"],
            "target_prep_seconds": order["target_prep_seconds"],
            "contains_sandwich": bool(order["contains_sandwich"]),
            "items": items,
        }


def build_kitchen_order(order_id: str) -> dict:
    order = build_order_response(order_id)
    elapsed = seconds_since(order["created_at"]) or 0
    target = order["target_prep_seconds"]
    ratio = elapsed / target if target > 0 else 0

    if ratio >= 1:
        time_state = "overdue"
    elif ratio >= 0.7:
        time_state = "warning"
    else:
        time_state = "normal"

    return {
        **order,
        "elapsed_seconds": elapsed,
        "progress_ratio": round(ratio, 2),
        "time_state": time_state,
    }


def mark_in_progress_if_created(order_id: str):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT status, accepted_at FROM orders WHERE id = ?", (order_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Order not found")

        if row["status"] == "created":
            accepted_at = row["accepted_at"] or utc_now_iso()
            cur.execute(
                "UPDATE orders SET status = ?, accepted_at = ? WHERE id = ?",
                ("in_progress", accepted_at, order_id),
            )
            conn.commit()


@app.post("/orders", response_model=OrderResponse)
def create_order(payload: CreateOrderRequest):
    order_id = str(uuid.uuid4())
    order_number = str(100000 + int(datetime.now(timezone.utc).timestamp()) % 900000)
    created_at = utc_now_iso()
    total = sum(item.qty * item.price for item in payload.items)
    contains_sandwich = order_contains_sandwich(payload.items)
    target_prep_seconds = 240 if contains_sandwich else 120

    with closing(get_conn()) as conn:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO orders (
                id, number, source, status, created_at, total,
                accepted_at, ready_at, cancelled_at,
                target_prep_seconds, contains_sandwich
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                order_number,
                payload.source,
                "created",
                created_at,
                total,
                None,
                None,
                None,
                target_prep_seconds,
                1 if contains_sandwich else 0,
            ),
        )

        for item in payload.items:
            order_item_id = str(uuid.uuid4())

            cur.execute(
                "INSERT INTO order_items (id, order_id, item_id, name, qty, price) VALUES (?, ?, ?, ?, ?, ?)",
                (order_item_id, order_id, item.item_id, item.name, item.qty, item.price),
            )

            for option in item.options:
                cur.execute(
                    "INSERT INTO order_item_options (id, order_item_id, group_id, option_id, name) VALUES (?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), order_item_id, option.group_id, option.option_id, option.name),
                )

        conn.commit()

    return build_order_response(order_id)


@app.get("/orders", response_model=List[OrderResponse])
def get_orders():
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM orders ORDER BY created_at DESC")
        rows = cur.fetchall()

    return [build_order_response(row["id"]) for row in rows]


@app.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: str):
    return build_order_response(order_id)


@app.patch("/orders/{order_id}/status", response_model=OrderResponse)
def update_order_status(order_id: str, payload: UpdateOrderStatusRequest):
    if payload.status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        exists = cur.fetchone()

        if not exists:
            raise HTTPException(status_code=404, detail="Order not found")

        accepted_at = exists["accepted_at"]
        ready_at = exists["ready_at"]
        cancelled_at = exists["cancelled_at"]

        if payload.status == "in_progress" and not accepted_at:
            accepted_at = utc_now_iso()

        if payload.status == "ready":
            if not accepted_at:
                accepted_at = utc_now_iso()
            ready_at = utc_now_iso()

        if payload.status == "cancelled":
            cancelled_at = utc_now_iso()

        cur.execute(
            """
            UPDATE orders
            SET status = ?, accepted_at = ?, ready_at = ?, cancelled_at = ?
            WHERE id = ?
            """,
            (payload.status, accepted_at, ready_at, cancelled_at, order_id),
        )
        conn.commit()

    return build_order_response(order_id)


@app.post("/orders/{order_id}/ready", response_model=OrderResponse)
def set_order_ready(order_id: str):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Order not found")

        accepted_at = row["accepted_at"] or utc_now_iso()
        ready_at = utc_now_iso()

        cur.execute(
            """
            UPDATE orders
            SET status = ?, accepted_at = ?, ready_at = ?
            WHERE id = ?
            """,
            ("ready", accepted_at, ready_at, order_id),
        )
        conn.commit()

    return build_order_response(order_id)


@app.post("/orders/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(order_id: str):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Order not found")

        cancelled_at = utc_now_iso()

        cur.execute(
            """
            UPDATE orders
            SET status = ?, cancelled_at = ?
            WHERE id = ?
            """,
            ("cancelled", cancelled_at, order_id),
        )
        conn.commit()

    return build_order_response(order_id)


@app.get("/kitchen/orders")
def get_kitchen_orders():
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id FROM orders
            WHERE status IN (?, ?)
            ORDER BY created_at ASC
            """,
            ("created", "in_progress"),
        )
        rows = cur.fetchall()

    result = []
    for row in rows:
        order_id = row["id"]
        mark_in_progress_if_created(order_id)
        result.append(build_kitchen_order(order_id))

    return result


@app.get("/display/orders")
def get_display_orders():
    with closing(get_conn()) as conn:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, number, created_at, status
            FROM orders
            WHERE status IN (?, ?)
            ORDER BY created_at ASC
            """,
            ("created", "in_progress"),
        )
        accepted_rows = cur.fetchall()

        cur.execute(
            """
            SELECT id, number, created_at, ready_at, status
            FROM orders
            WHERE status = ?
            ORDER BY ready_at ASC
            """,
            ("ready",),
        )
        ready_rows = cur.fetchall()

    accepted_orders = [
        {
            "id": row["id"],
            "number": row["number"],
            "status": row["status"],
            "wait_seconds": seconds_since(row["created_at"]) or 0,
        }
        for row in accepted_rows
    ]

    ready_orders = []
    for row in ready_rows:
        visible_for = seconds_since(row["ready_at"])
        if visible_for is None or visible_for > READY_VISIBLE_SECONDS:
            continue

        ready_orders.append(
            {
                "id": row["id"],
                "number": row["number"],
                "status": row["status"],
                "wait_seconds": visible_for,
            }
        )

    return {
        "accepted_orders": accepted_orders,
        "ready_orders": ready_orders,
    }
@app.get("/")
def root_ui():
    return FileResponse("/home/admini/jojos-core/static/index.html")


@app.get("/kitchen")
def kitchen_ui():
    return FileResponse("/home/admini/jojos-core/static/index.html")


@app.get("/display")
def display_ui():
    return FileResponse("/home/admini/jojos-core/static/index.html")
