import json
import os
import sqlite3
import time

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "kasir.db")
CATALOG_PATH = os.path.join(BASE, "catalog.json")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT,
    role TEXT NOT NULL DEFAULT 'kasir',
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    emoji TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    price_idr INTEGER NOT NULL,
    emoji TEXT DEFAULT '',
    active INTEGER DEFAULT 1,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'free'
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id INTEGER,
    user_id INTEGER,
    status TEXT NOT NULL DEFAULT 'active',
    total_idr INTEGER NOT NULL DEFAULT 0,
    payment_method TEXT,
    cash_received INTEGER,
    change_idr INTEGER,
    crypto_symbol TEXT,
    created_at INTEGER NOT NULL,
    paid_at INTEGER,
    done_at INTEGER
);
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    qty INTEGER NOT NULL,
    price_idr INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at INTEGER NOT NULL
);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def fetchone(sql, params=()):
    conn = get_conn()
    try:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def fetchall(sql, params=()):
    conn = get_conn()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def execute(sql, params=()):
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def load_catalog():
    if os.path.exists(CATALOG_PATH):
        try:
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception as e:
            print("catalog.json error:", e)
    return {"categories": [], "products": []}


def init_db():
    if os.path.exists(DB_PATH):
        return False
    conn = get_conn()
    conn.executescript(SCHEMA)
    now = int(time.time())
    data = load_catalog()
    cat_ids = {}
    for c in data.get("categories", []):
        cur = conn.execute("INSERT INTO categories (name, emoji) VALUES (?,?)",
                           (c["name"], c.get("emoji", "")))
        cat_ids[c["name"]] = cur.lastrowid
    for p in data.get("products", []):
        cid = cat_ids.get(p.get("category", ""))
        if cid is None:
            continue
        conn.execute(
            "INSERT INTO products (name, category_id, price_idr, emoji, active, created_at) VALUES (?,?,?,?,1,?)",
            (p["name"], cid, int(p.get("price_idr", 0)), p.get("emoji", ""), now),
        )
    for i in range(1, 7):
        conn.execute("INSERT INTO tables (name, status) VALUES (?,?)", (f"Meja {i}", "free"))
    conn.commit()
    conn.close()
    return True


if __name__ == "__main__":
    created = init_db()
    print("DB created" if created else "DB already exists", "at", DB_PATH)