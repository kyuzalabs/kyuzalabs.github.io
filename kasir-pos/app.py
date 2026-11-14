import json
import os
import secrets
import time
import datetime
from functools import wraps
from zoneinfo import ZoneInfo

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

import db

app = Flask(__name__)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
if os.environ.get("FORCE_HTTPS"):
    app.config["SESSION_COOKIE_SECURE"] = True

WIB = ZoneInfo("Asia/Jakarta")
CONFIG_PATH = os.path.join(db.BASE, "kasir_config.json")


def _now():
    return int(time.time())


def _fmt(n):
    return f"Rp {int(n):,}".replace(",", ".")


def _today_start():
    now = datetime.datetime.now(WIB)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(start.timestamp())


def _to_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _ensure_config():
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        try:
            cfg = json.load(open(CONFIG_PATH, "r", encoding="utf-8"))
        except Exception:
            cfg = {}
    changed = False
    if "secret_key" not in cfg:
        cfg["secret_key"] = secrets.token_hex(32)
        changed = True
    if changed:
        json.dump(cfg, open(CONFIG_PATH, "w", encoding="utf-8"))
    app.secret_key = cfg["secret_key"]


def ensure_users():
    if db.fetchone("SELECT id FROM users WHERE role='admin'"):
        return
    now = _now()
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@kyuzakasir.id")
    admin_pw = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(10)
    kasir_pw = os.environ.get("KASIR_PASSWORD", "kasir123")
    db.execute(
        "INSERT INTO users (email,password_hash,name,role,created_at) VALUES (?,?,?,?,?)",
        (admin_email, generate_password_hash(admin_pw), "Admin", "admin", now),
    )
    db.execute(
        "INSERT INTO users (email,password_hash,name,role,created_at) VALUES (?,?,?,?,?)",
        ("kasir@kyuzakasir.id", generate_password_hash(kasir_pw), "Kasir", "kasir", now),
    )
    print("\n===== LOGIN KYUZA KASIR (simpan baik-baik) =====")
    print("  ADMIN :", admin_email, "/", admin_pw)
    print("  KASIR : kasir@kyuzakasir.id /", kasir_pw)
    print("===============================================\n")


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Masuk dulu ya, Kak.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Masuk dulu ya, Kak.", "error")
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Hanya admin yang bisa akses.", "error")
            return redirect(url_for("kasir"))
        return f(*args, **kwargs)
    return wrapper


def get_order(oid):
    return db.fetchone("SELECT * FROM orders WHERE id=?", (oid,))


def get_items(oid):
    return db.fetchall("SELECT * FROM order_items WHERE order_id=? ORDER BY id", (oid,))


def order_total(items):
    return sum(it["qty"] * it["price_idr"] for it in items)


def table_name(tid):
    if not tid:
        return "-"
    t = db.fetchone("SELECT name FROM tables WHERE id=?", (tid,))
    return t["name"] if t else "-"


def _idr(n):
    return f"{int(n):,}".replace(",", ".")


def _method_label(m):
    return {"cash": "💵 Tunai", "qris": "📱 QRIS", "transfer": "🏦 Transfer", "crypto": "🪙 Crypto"}.get(m, m or "-")


@app.template_filter("ctime")
def _ctime(ts):
    if not ts:
        return "-"
    return datetime.datetime.fromtimestamp(ts, WIB).strftime("%d/%m/%Y %H:%M")


app.jinja_env.globals["table_name"] = table_name
app.jinja_env.globals["method_label"] = _method_label
app.jinja_env.filters["idr"] = _idr


# ============================ AUTH ============================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        u = db.fetchone("SELECT * FROM users WHERE email=?", (email,))
        if u and check_password_hash(u["password_hash"], password):
            session["user_id"] = u["id"]
            session["name"] = u["name"]
            session["role"] = u["role"]
            session["is_admin"] = (u["role"] == "admin")
            flash(f"Selamat datang, {u['name']}!", "success")
            if u["role"] == "admin":
                return redirect(url_for("kasir"))
            return redirect(url_for("kasir"))
        flash("Email atau password salah.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def home():
    return redirect(url_for("kasir"))


# ============================ KASIR ============================

@app.route("/kasir")
@login_required
def kasir():
    order_id = request.args.get("order", type=int)
    cat_id = request.args.get("cat", type=int)

    tables = db.fetchall("SELECT * FROM tables ORDER BY id")
    open_orders = db.fetchall("SELECT id, table_id FROM orders WHERE status IN ('active','paid')")
    order_by_table = {o["table_id"]: o["id"] for o in open_orders if o["table_id"]}

    categories = db.fetchall("SELECT * FROM categories ORDER BY id")
    if cat_id:
        products = db.fetchall("SELECT * FROM products WHERE active=1 AND category_id=? ORDER BY name", (cat_id,))
    else:
        products = db.fetchall("SELECT * FROM products WHERE active=1 ORDER BY category_id, name")

    order = items = total = None
    if order_id:
        order = get_order(order_id)
        if order and order["status"] in ("active", "paid"):
            items = get_items(order_id)
            total = order_total(items)

    return render_template(
        "kasir.html",
        tables=tables,
        order_by_table=order_by_table,
        categories=categories,
        products=products,
        cat_id=cat_id,
        order=order,
        items=items,
        total=total,
    )


@app.route("/kasir/table/<int:tid>/open", methods=["POST"])
@login_required
def table_open(tid):
    t = db.fetchone("SELECT * FROM tables WHERE id=?", (tid,))
    if not t:
        flash("Meja tidak ditemukan.", "error")
        return redirect(url_for("kasir"))
    existing = db.fetchone("SELECT id FROM orders WHERE table_id=? AND status IN ('active','paid')", (tid,))
    if existing:
        return redirect(url_for("kasir", order=existing["id"]))
    oid = db.execute(
        "INSERT INTO orders (table_id, user_id, status, created_at) VALUES (?,?,?,?)",
        (tid, session["user_id"], "active", _now()),
    )
    db.execute("UPDATE tables SET status='busy' WHERE id=?", (tid,))
    flash(f"{t['name']} dibuka — mulai tambah pesanan.", "success")
    return redirect(url_for("kasir", order=oid))


@app.route("/order/<int:oid>/add", methods=["POST"])
@login_required
def order_add(oid):
    order = get_order(oid)
    if not order or order["status"] != "active":
        flash("Pesanan sudah tidak bisa diubah.", "error")
        return redirect(url_for("kasir"))
    product_id = _to_int(request.form.get("product_id"))
    qty = max(1, _to_int(request.form.get("qty"), 1))
    p = db.fetchone("SELECT * FROM products WHERE id=? AND active=1", (product_id,))
    if p:
        existing = db.fetchone(
            "SELECT id FROM order_items WHERE order_id=? AND product_id=? AND status='pending'",
            (oid, product_id),
        )
        if existing:
            db.execute("UPDATE order_items SET qty=qty+? WHERE id=?", (qty, existing["id"]))
        else:
            db.execute(
                "INSERT INTO order_items (order_id, product_id, name, qty, price_idr, created_at) VALUES (?,?,?,?,?,?)",
                (oid, product_id, p["name"], qty, p["price_idr"], _now()),
            )
    return redirect(url_for("kasir", order=oid))


@app.route("/order/<int:oid>/item/<int:iid>/qty", methods=["POST"])
@login_required
def item_qty(oid, iid):
    order = get_order(oid)
    if not order or order["status"] != "active":
        return redirect(url_for("kasir"))
    qty = max(1, _to_int(request.form.get("qty"), 1))
    db.execute("UPDATE order_items SET qty=? WHERE id=? AND order_id=?", (qty, iid, oid))
    return redirect(url_for("kasir", order=oid))


@app.route("/order/<int:oid>/item/<int:iid>/remove", methods=["POST"])
@login_required
def item_remove(oid, iid):
    order = get_order(oid)
    if not order or order["status"] != "active":
        return redirect(url_for("kasir"))
    db.execute("DELETE FROM order_items WHERE id=? AND order_id=?", (iid, oid))
    return redirect(url_for("kasir", order=oid))


@app.route("/order/<int:oid>/cancel", methods=["POST"])
@login_required
def order_cancel(oid):
    order = get_order(oid)
    if order and order["status"] == "active":
        db.execute("DELETE FROM order_items WHERE order_id=?", (oid,))
        db.execute("DELETE FROM orders WHERE id=?", (oid,))
        if order["table_id"]:
            db.execute("UPDATE tables SET status='free' WHERE id=?", (order["table_id"],))
        flash("Pesanan dibatalkan, meja dibebaskan.", "info")
    return redirect(url_for("kasir"))


@app.route("/order/<int:oid>/pay", methods=["GET", "POST"])
@login_required
def order_pay(oid):
    order = get_order(oid)
    if not order:
        flash("Pesanan tidak ditemukan.", "error")
        return redirect(url_for("kasir"))
    items = get_items(oid)
    total = order_total(items)
    if request.method == "POST":
        if order["status"] != "active":
            return redirect(url_for("receipt", oid=oid))
        method = request.form.get("method", "cash")
        cash = _to_int(request.form.get("cash_received"))
        change = 0
        crypto_symbol = None
        if method == "cash":
            if cash < total:
                flash("Uang tunai kurang dari total.", "error")
                return redirect(url_for("order_pay", oid=oid))
            change = cash - total
        elif method == "crypto":
            crypto_symbol = request.form.get("crypto_symbol", "USDT")
        db.execute(
            "UPDATE orders SET status='paid', total_idr=?, payment_method=?, cash_received=?, change_idr=?, crypto_symbol=?, paid_at=? WHERE id=?",
            (total, method, cash if method == "cash" else None, change, crypto_symbol, _now(), oid),
        )
        return redirect(url_for("receipt", oid=oid))
    return render_template("pay.html", order=order, items=items, total=total, table=table_name(order["table_id"]))


@app.route("/order/<int:oid>/receipt")
@login_required
def receipt(oid):
    order = get_order(oid)
    if not order:
        flash("Pesanan tidak ditemukan.", "error")
        return redirect(url_for("kasir"))
    items = get_items(oid)
    return render_template("receipt.html", order=order, items=items, total=order["total_idr"])


@app.route("/order/<int:oid>/done", methods=["POST"])
@login_required
def order_done(oid):
    order = get_order(oid)
    if order and order["status"] == "paid":
        db.execute("UPDATE orders SET status='done', done_at=? WHERE id=?", (_now(), oid))
        if order["table_id"]:
            db.execute("UPDATE tables SET status='free' WHERE id=?", (order["table_id"],))
        flash("Pesanan selesai, meja dibebaskan.", "success")
    return redirect(url_for("kasir"))


# ============================ DAPUR ============================

@app.route("/dapur")
@login_required
def dapur():
    orders = db.fetchall("SELECT * FROM orders WHERE status='paid' ORDER BY paid_at")
    for o in orders:
        o["table"] = table_name(o["table_id"])
        o["lines"] = get_items(o["id"])
        o["pending"] = sum(1 for it in o["lines"] if it["status"] == "pending")
    return render_template("dapur.html", orders=orders)


@app.route("/dapur/item/<int:iid>/done", methods=["POST"])
@login_required
def dapur_item_done(iid):
    item = db.fetchone("SELECT * FROM order_items WHERE id=?", (iid,))
    if item:
        db.execute("UPDATE order_items SET status='done' WHERE id=?", (iid,))
    return redirect(request.referrer or url_for("dapur"))


# ============================ ADMIN ============================

@app.route("/admin")
@admin_required
def admin():
    today = _today_start()
    today_orders = db.fetchall("SELECT * FROM orders WHERE paid_at >= ?", (today,))
    revenue = sum(o["total_idr"] for o in today_orders)
    by_method = {}
    for o in today_orders:
        m = o["payment_method"] or "lain"
        by_method[m] = by_method.get(m, 0) + o["total_idr"]
    total_orders = db.fetchone("SELECT COUNT(*) c FROM orders")["c"]
    total_revenue = db.fetchone("SELECT COALESCE(SUM(total_idr),0) c FROM orders WHERE status IN ('paid','done')")["c"]
    busy_tables = db.fetchone("SELECT COUNT(*) c FROM tables WHERE status='busy'")["c"]
    return render_template(
        "admin/dashboard.html",
        revenue=revenue,
        by_method=by_method,
        total_orders=total_orders,
        total_revenue=total_revenue,
        busy_tables=busy_tables,
        today_orders=today_orders,
    )


@app.route("/admin/menu")
@admin_required
def admin_menu():
    categories = db.fetchall("SELECT * FROM categories ORDER BY id")
    products = db.fetchall("SELECT p.*, c.name AS cat_name, c.emoji AS cat_emoji FROM products p JOIN categories c ON c.id=p.category_id ORDER BY p.category_id, p.name")
    return render_template("admin/menu.html", categories=categories, products=products)


@app.route("/admin/menu/add", methods=["POST"])
@admin_required
def admin_menu_add():
    name = request.form.get("name", "").strip()
    price = _to_int(request.form.get("price_idr"))
    category_id = _to_int(request.form.get("category_id"))
    emoji = request.form.get("emoji", "").strip() or "🍽️"
    if name and price > 0 and category_id:
        db.execute(
            "INSERT INTO products (name, category_id, price_idr, emoji, active, created_at) VALUES (?,?,?,?,1,?)",
            (name, category_id, price, emoji, _now()),
        )
        flash(f"'{name}' ditambahkan ke menu.", "success")
    else:
        flash("Nama, harga, dan kategori wajib diisi.", "error")
    return redirect(url_for("admin_menu"))


@app.route("/admin/menu/<int:pid>/toggle", methods=["POST"])
@admin_required
def admin_menu_toggle(pid):
    p = db.fetchone("SELECT active FROM products WHERE id=?", (pid,))
    if p:
        db.execute("UPDATE products SET active=? WHERE id=?", (0 if p["active"] else 1, pid))
    return redirect(url_for("admin_menu"))


@app.route("/admin/tables")
@admin_required
def admin_tables():
    tables = db.fetchall("SELECT * FROM tables ORDER BY id")
    return render_template("admin/tables.html", tables=tables)


@app.route("/admin/tables/add", methods=["POST"])
@admin_required
def admin_tables_add():
    name = request.form.get("name", "").strip()
    if name:
        db.execute("INSERT INTO tables (name, status) VALUES (?,?)", (name, "free"))
        flash(f"Meja '{name}' ditambahkan.", "success")
    return redirect(url_for("admin_tables"))


@app.route("/admin/orders")
@admin_required
def admin_orders():
    orders = db.fetchall("SELECT * FROM orders ORDER BY id DESC LIMIT 100")
    for o in orders:
        o["table"] = table_name(o["table_id"])
        o["lines"] = get_items(o["id"])
    return render_template("admin/orders.html", orders=orders)


# ============================ INIT ============================

_ensure_config()
db.init_db()
ensure_users()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8501, debug=False, threaded=True)