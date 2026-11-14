"""SQLite schema + connection helpers (idempotent init)."""
import os, re, sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kasir.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS menu (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  price INTEGER NOT NULL,
  category TEXT NOT NULL DEFAULT 'Umum',
  slug TEXT UNIQUE NOT NULL
);
CREATE TABLE IF NOT EXISTS tables (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL,
  status TEXT NOT NULL DEFAULT 'free'
);
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  table_id INTEGER,
  status TEXT NOT NULL DEFAULT 'active',
  total INTEGER NOT NULL DEFAULT 0,
  payment_method TEXT,
  cash_received INTEGER,
  change_idr INTEGER,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS order_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL,
  menu_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  price INTEGER NOT NULL,
  qty INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'pending'
);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def slugify(s):
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "item"


def init_db():
    conn = get_conn()
    with conn:
        conn.executescript(SCHEMA)
    conn.close()

    conn = get_conn()
    if conn.execute("SELECT COUNT(*) FROM menu").fetchone()[0] == 0:
        items = [
            ("Espresso", 15000, "Kopi"), ("Americano", 18000, "Kopi"),
            ("Cappuccino", 22000, "Kopi"), ("Kopi Susu Gula Aren", 20000, "Kopi"),
            ("Teh Tarik", 12000, "Non-Kopi"), ("Air Mineral", 5000, "Non-Kopi"),
        ]
        with conn:
            for name, price, cat in items:
                conn.execute("INSERT INTO menu (name, price, category, slug) VALUES (?,?,?,?)",
                             (name, price, cat, slugify(name)))
    if conn.execute("SELECT COUNT(*) FROM tables").fetchone()[0] == 0:
        with conn:
            for i in range(1, 7):
                conn.execute("INSERT INTO tables (name) VALUES (?)", (f"Meja {i}",))
    conn.close()