import json
import os
import re
import sqlite3
import time

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "store.db")
CATALOG_PATH = os.path.join(BASE, "catalog.json")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT,
    is_admin INTEGER DEFAULT 0,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT,
    description TEXT DEFAULT '',
    price_idr INTEGER NOT NULL,
    category TEXT DEFAULT '',
    image_url TEXT DEFAULT '',
    emoji TEXT DEFAULT '',
    stock INTEGER DEFAULT 99,
    active INTEGER DEFAULT 1,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    total_idr INTEGER NOT NULL,
    crypto_symbol TEXT,
    crypto_amount REAL,
    deposit_address TEXT,
    tx_hash TEXT,
    created_at INTEGER NOT NULL,
    paid_at INTEGER
);
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    qty INTEGER NOT NULL,
    price_idr INTEGER NOT NULL
);
"""


def slugify(s):
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_catalog():
    if os.path.exists(CATALOG_PATH):
        try:
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                return data
        except Exception as e:
            print("catalog.json error:", e)
    return [
        {"name": "Kopi Gayo 250g", "description": "Kopi arabika Gayo Aceh, 250 gram.", "price_idr": 78000, "category": "Makanan & Minuman", "image_url": "https://picsum.photos/seed/kopi/600/400", "stock": 80},
        {"name": "Tumbler Stainless 500ml", "description": "Botol minum stainless, tahan panas & dingin.", "price_idr": 125000, "category": "Rumah Tangga", "image_url": "https://picsum.photos/seed/tumbler/600/400", "stock": 120},
        {"name": "TWS Earbuds Pro", "description": "Earbuds bluetooth noise-cancelling.", "price_idr": 349000, "category": "Elektronik", "image_url": "https://picsum.photos/seed/tws/600/400", "stock": 50},
        {"name": "Kaos Oversize Hitam", "description": "Kaos katun premium, size M-XXL.", "price_idr": 99000, "category": "Fashion", "image_url": "https://picsum.photos/seed/kaos/600/400", "stock": 200},
        {"name": "Sandaran HP Kayu", "description": "Stand holder kayu buatan tangan.", "price_idr": 45000, "category": "Hobi & Kreatif", "image_url": "https://picsum.photos/seed/stand/600/400", "stock": 150},
        {"name": "Gelang Paracord", "description": "Gelang anyam paracord survival.", "price_idr": 35000, "category": "Aksesoris", "image_url": "https://picsum.photos/seed/paracord/600/400", "stock": 180},
    ]


def init_db():
    if os.path.exists(DB_PATH):
        return False
    conn = get_conn()
    conn.executescript(SCHEMA)
    now = int(time.time())
    for p in load_catalog():
        conn.execute(
            "INSERT INTO products (name,slug,description,price_idr,category,image_url,emoji,stock,active,created_at) VALUES (?,?,?,?,?,?,?,?,1,?)",
            (p["name"], slugify(p["name"]), p.get("description", ""), int(p.get("price_idr", 0)), p.get("category", ""), p.get("image_url", ""), p.get("emoji", ""), int(p.get("stock", 99)), now),
        )
    conn.commit()
    conn.close()
    return True


if __name__ == "__main__":
    created = init_db()
    print("DB created" if created else "DB already exists", "at", DB_PATH)