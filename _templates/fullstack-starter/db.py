"""SQLite schema + connection helpers (idempotent init)."""
import os, re, sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "store.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  is_admin INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  price INTEGER NOT NULL,
  stock INTEGER NOT NULL DEFAULT 0,
  slug TEXT UNIQUE NOT NULL,
  image TEXT
);
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  status TEXT NOT NULL DEFAULT 'pending',
  total INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS order_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL,
  product_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  price INTEGER NOT NULL,
  qty INTEGER NOT NULL
);
"""


def get_conn():
    """Selalu buka koneksi BARU. Jangan panggil get_conn() dua kali utk satu operasi
    tulis+commit — commit di koneksi beda = write ilang diam-diam."""
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
    # seed produk awal kalau kosong
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if n == 0:
        rows = [("Kopi Susu", 18000, 50), ("Americano", 15000, 50), ("Latte", 20000, 50)]
        with conn:
            for name, price, stock in rows:
                conn.execute(
                    "INSERT INTO products (name, price, stock, slug) VALUES (?,?,?,?)",
                    (name, price, stock, slugify(name)),
                )
    conn.close()