import sqlite3
from contextlib import closing

from app.core.config import DB_PATH


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
            price INTEGER NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS order_item_options (
            id TEXT PRIMARY KEY,
            order_item_id TEXT NOT NULL,
            group_id TEXT NOT NULL,
            option_id TEXT NOT NULL,
            name TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS inventory_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT NOT NULL UNIQUE,
            available_qty INTEGER NOT NULL DEFAULT 0,
            is_available INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS media_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_key TEXT NOT NULL UNIQUE,
            asset_type TEXT NOT NULL,
            external_url TEXT,
            local_path TEXT,
            mime_type TEXT,
            checksum TEXT,
            is_downloaded INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS sync_status (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_pull_at TEXT,
            last_push_at TEXT,
            last_status TEXT,
            last_error TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS print_jobs (
            id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            job_type TEXT NOT NULL,
            printer_host TEXT NOT NULL,
            printer_port INTEGER NOT NULL,
            status TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL,
            rendered_label TEXT NOT NULL,
            created_at TEXT NOT NULL,
            sent_at TEXT,
            last_error TEXT
        )
        """)

        cur.execute("INSERT OR IGNORE INTO sync_status (id) VALUES (1)")

        order_needed_columns = [
            ("accepted_at", "TEXT"),
            ("ready_at", "TEXT"),
            ("cancelled_at", "TEXT"),
            ("target_prep_seconds", "INTEGER NOT NULL DEFAULT 120"),
            ("contains_sandwich", "INTEGER NOT NULL DEFAULT 0"),
            ("service_mode", "TEXT DEFAULT 'dine_in'"),
            ("actual_prep_seconds", "INTEGER"),
            ("is_overdue", "INTEGER NOT NULL DEFAULT 0"),
            ("order_snapshot_json", "TEXT"),
        ]

        for col_name, col_type in order_needed_columns:
            if not column_exists(conn, "orders", col_name):
                cur.execute(f"ALTER TABLE orders ADD COLUMN {col_name} {col_type}")

        option_needed_columns = [
            ("price", "INTEGER NOT NULL DEFAULT 0"),
        ]

        for col_name, col_type in option_needed_columns:
            if not column_exists(conn, "order_item_options", col_name):
                cur.execute(f"ALTER TABLE order_item_options ADD COLUMN {col_name} {col_type}")

        conn.commit()
