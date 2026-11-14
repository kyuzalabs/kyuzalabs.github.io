import json
import os
import secrets
import time
import datetime
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, abort)
from werkzeug.security import generate_password_hash, check_password_hash

import db
import payments

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, "config.json")
BRAND_PATH = os.path.join(BASE, "store_branding.json")

app = Flask(__name__)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
if os.environ.get("FORCE_HTTPS"):
    app.config["SESSION_COOKIE_SECURE"] = True


# ---------- config & brand ----------
def _load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def _load_brand():
    try:
        with open(BRAND_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"name": "Kyuza Shop", "tagline": "Belanja mudah, bayar pakai crypto"}


BRAND = _load_brand()
app.jinja_env.globals["BRAND"] = BRAND


def _ensure_config():
    cfg = _load_config()
    changed = False
    if "secret_key" not in cfg:
        cfg["secret_key"] = secrets.token_hex(32)
        changed = True
    if changed:
        _save_config(cfg)
    app.secret_key = cfg["secret_key"]
    return cfg


CONFIG = _ensure_config()


# ---------- db helpers ----------
def _rows(sql, args=()):
    conn = db.get_conn()
    cur = conn.execute(sql, args)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def _one(sql, args=()):
    rows = _rows(sql, args)
    return rows[0] if rows else None


def _exec(sql, args=()):
    conn = db.get_conn()
    cur = conn.execute(sql, args)
    conn.commit()
    lastid = cur.lastrowid
    conn.close()
    return lastid


def _int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _safe_next(nxt):
    if (not nxt or not nxt.startswith("/") or nxt.startswith("//")
            or ":/" in nxt or "\\" in nxt):
        return url_for("index")
    return nxt


def fmt_ts(ts):
    if not ts:
        return "-"
    return datetime.datetime.fromtimestamp(ts).strftime("%d %b %Y %H:%M")


# ---------- admin seed ----------
def ensure_admin():
    email = os.environ.get("ADMIN_EMAIL", "admin@kyuzashop.id")
    if _one("SELECT id FROM users WHERE is_admin = 1"):
        return
    pw = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(10)
    _exec("INSERT INTO users (email, password_hash, name, is_admin, created_at) VALUES (?,?,?,1,?)",
          (email, generate_password_hash(pw), "Admin", int(time.time())))
    print("\n===== ADMIN LOGIN (simpan baik-baik) =====\n email: %s\n password: %s\n==========================================\n" % (email, pw))


# ---------- auth decorators ----------
def login_required(f):
    @wraps(f)
    def w(*a, **kw):
        if not session.get("user_id"):
            flash("Silakan masuk dulu.", "warning")
            return redirect(url_for("login", next=request.path))
        return f(*a, **kw)
    return w


def admin_required(f):
    @wraps(f)
    def w(*a, **kw):
        u = _one("SELECT is_admin FROM users WHERE id = ?", (session.get("user_id"),))
        if not u or not u["is_admin"]:
            flash("Butuh akses admin.", "danger")
            return redirect(url_for("login"))
        return f(*a, **kw)
    return w


# ---------- cart helpers ----------
def _cart():
    return session.setdefault("cart", [])


def _cart_detail():
    out = []
    for it in _cart():
        p = _one("SELECT * FROM products WHERE id = ?", (it["product_id"],))
        if not p or p["stock"] <= 0:
            continue
        qty = max(1, min(int(it["qty"]), p["stock"]))
        price = p["price_idr"]
        out.append({
            "product_id": p["id"],
            "name": p["name"],
            "price_idr": price,
            "image_url": p["image_url"],
            "qty": qty,
            "subtotal": price * qty,
        })
    return out


def _cart_total():
    return sum(i["subtotal"] for i in _cart_detail())


# ---------- order helpers ----------
def _order_view(o):
    d = dict(o)
    d["created_at"] = fmt_ts(d.get("created_at"))
    sym = d.get("crypto_symbol")
    d["network"] = payments.TOKENS.get(sym, {}).get("network", "") if sym else ""
    d["crypto_amount"] = d.get("crypto_amount") or 0
    return d


def maybe_auto_confirm(o):
    if o.get("status") != "pending" or not o.get("crypto_symbol"):
        return
    amount = o.get("crypto_amount")
    if not amount or amount <= 0:
        return
    addr = (o.get("deposit_address") or "").strip()
    if not addr or addr == payments.PLACEHOLDER_ADDRESS:
        return  # alamat wallet belum diset -> skip auto-check
    res = payments.check_payment(o["crypto_symbol"], amount, o.get("created_at") or 0)
    if res.get("paid"):
        tx = res.get("tx_hash")
        if tx:
            _exec("UPDATE orders SET status='paid', paid_at=?, tx_hash=COALESCE(tx_hash, ?) WHERE id=?",
                  (int(time.time()), tx, o["id"]))
        else:
            _exec("UPDATE orders SET status='paid', paid_at=? WHERE id=?",
                  (int(time.time()), o["id"]))


# ---------- shop routes ----------
@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    cat = request.args.get("cat", "").strip()
    sql = "SELECT * FROM products WHERE active = 1"
    args = []
    if q:
        sql += " AND (name LIKE ? OR description LIKE ?)"
        like = f"%{q}%"
        args += [like, like]
    if cat:
        sql += " AND category = ?"
        args.append(cat)
    sql += " ORDER BY id DESC"
    products = _rows(sql, args)
    categories = [r["category"] for r in _rows("SELECT DISTINCT category FROM products WHERE active=1 ORDER BY category")]
    return render_template("index.html", products=products, categories=categories, q=q, cat=cat)


@app.route("/product/<int:pid>")
def product(pid):
    p = _one("SELECT * FROM products WHERE id = ? AND active = 1", (pid,))
    if not p:
        abort(404)
    return render_template("product.html", product=p)


@app.route("/cart/add", methods=["POST"])
def cart_add():
    pid = _int(request.form.get("product_id"), 0)
    qty = _int(request.form.get("qty"), 0) or 1
    p = _one("SELECT * FROM products WHERE id = ? AND active = 1", (pid,))
    if not p:
        flash("Produk tidak ditemukan.", "danger")
        return redirect(url_for("index"))
    stock = p["stock"]
    if stock <= 0:
        flash("Stok habis.", "danger")
        return redirect(url_for("product", pid=pid))
    qty = max(1, min(qty, stock))
    cart = _cart()
    for it in cart:
        if it["product_id"] == pid:
            it["qty"] = min(it["qty"] + qty, stock)
            break
    else:
        cart.append({"product_id": pid, "qty": qty})
    session["cart"] = cart
    flash(f"{p['name']} masuk keranjang.", "success")
    return redirect(url_for("cart"))


@app.route("/cart")
def cart():
    return render_template("cart.html", cart=_cart_detail(), total_idr=_cart_total())


@app.route("/cart/update", methods=["POST"])
def cart_update():
    pid = _int(request.form.get("product_id"), 0)
    qty = _int(request.form.get("qty"), 0)
    cart = _cart()
    if qty <= 0:
        cart = [it for it in cart if it["product_id"] != pid]
    else:
        p = _one("SELECT stock FROM products WHERE id = ?", (pid,))
        cap = p["stock"] if p else 0
        for it in cart:
            if it["product_id"] == pid:
                it["qty"] = min(qty, cap) if cap > 0 else qty
    session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:pid>", methods=["POST"])
def cart_remove(pid):
    session["cart"] = [it for it in _cart() if it["product_id"] != pid]
    flash("Item dihapus dari keranjang.", "info")
    return redirect(url_for("cart"))


@app.route("/checkout")
@login_required
def checkout():
    cart = _cart_detail()
    if not cart:
        flash("Keranjang kosong.", "warning")
        return redirect(url_for("cart"))
    tokens = [{"symbol": sym, "network": payments.TOKENS.get(sym, {}).get("network", "")}
              for sym in payments.SUPPORTED_TOKENS]
    return render_template("checkout.html", cart=cart, total_idr=_cart_total(), tokens=tokens)


@app.route("/checkout", methods=["POST"])
@login_required
def checkout_post():
    cart = _cart_detail()
    if not cart:
        flash("Keranjang kosong.", "warning")
        return redirect(url_for("cart"))
    # validasi stok ulang sebelum buat order (anti oversell)
    for it in cart:
        p = _one("SELECT id, stock, name FROM products WHERE id = ? AND active = 1", (it["product_id"],))
        if not p:
            flash("Ada produk yang tidak tersedia lagi.", "danger")
            return redirect(url_for("cart"))
        if it["qty"] > p["stock"]:
            flash(f"Stok '{p['name']}' tidak cukup (sisa {p['stock']}).", "danger")
            return redirect(url_for("cart"))
    symbol = request.form.get("crypto_symbol", "USDC")
    if symbol not in payments.SUPPORTED_TOKENS:
        symbol = payments.SUPPORTED_TOKENS[0]
    total_idr = _cart_total()
    quote = payments.get_quote(total_idr, symbol)
    oid = _exec(
        "INSERT INTO orders (user_id, status, total_idr, crypto_symbol, crypto_amount, deposit_address, created_at) VALUES (?,?,?,?,?,?,?)",
        (session["user_id"], "pending", total_idr, symbol, quote["amount"], quote["deposit_address"], int(time.time())),
    )
    for it in cart:
        _exec("INSERT INTO order_items (order_id, product_id, qty, price_idr) VALUES (?,?,?,?)",
              (oid, it["product_id"], it["qty"], it["price_idr"]))
        _exec("UPDATE products SET stock = stock - ? WHERE id = ?", (it["qty"], it["product_id"]))
    session["cart"] = []
    return redirect(url_for("pay", oid=oid))


@app.route("/pay/<int:oid>")
def pay(oid):
    o = _one("SELECT * FROM orders WHERE id = ?", (oid,))
    if not o:
        abort(404)
    if not session.get("is_admin") and o["user_id"] != session.get("user_id"):
        abort(403)
    maybe_auto_confirm(o)
    o = _one("SELECT * FROM orders WHERE id = ?", (oid,))
    return render_template("pay.html", order=_order_view(o))


@app.route("/pay/<int:oid>/confirm", methods=["POST"])
def pay_confirm(oid):
    o = _one("SELECT * FROM orders WHERE id = ?", (oid,))
    if not o:
        abort(404)
    if not session.get("is_admin") and o["user_id"] != session.get("user_id"):
        abort(403)
    tx = request.form.get("tx_hash", "").strip()
    if tx:
        _exec("UPDATE orders SET tx_hash = ? WHERE id = ?", (tx, o["id"]))
    maybe_auto_confirm(o)
    o2 = _one("SELECT * FROM orders WHERE id = ?", (oid,))
    if o2 and o2["status"] == "paid":
        flash("Pembayaran terverifikasi otomatis! ✅", "success")
    else:
        flash("TXID tercatat. Status jadi 'paid' kalau sistem sudah terverifikasi pembayarannya.", "info")
    return redirect(url_for("pay", oid=oid))


@app.route("/orders")
@login_required
def orders():
    rows = _rows("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC", (session["user_id"],))
    return render_template("orders.html", orders=[_order_view(o) for o in rows])


@app.route("/order/<int:oid>")
@login_required
def order_detail(oid):
    o = _one("SELECT * FROM orders WHERE id = ?", (oid,))
    if not o:
        abort(404)
    if not session.get("is_admin") and o["user_id"] != session.get("user_id"):
        abort(403)
    maybe_auto_confirm(o)
    o = _one("SELECT * FROM orders WHERE id = ?", (oid,))
    items = _rows(
        "SELECT oi.qty, oi.price_idr, p.name FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE oi.order_id = ?",
        (oid,),
    )
    return render_template("order.html", order=_order_view(o), items=items)


# ---------- auth routes ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        if not email or len(pw) < 6:
            flash("Password minimal 6 karakter.", "danger")
            return redirect(url_for("register"))
        if _one("SELECT id FROM users WHERE email = ?", (email,)):
            flash("Email sudah terdaftar.", "danger")
            return redirect(url_for("register"))
        _exec("INSERT INTO users (email, password_hash, name, is_admin, created_at) VALUES (?,?,?,0,?)",
              (email, generate_password_hash(pw), name or email.split("@")[0], int(time.time())))
        flash("Akun berhasil dibuat. Silakan masuk.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        u = _one("SELECT * FROM users WHERE email = ?", (email,))
        if u and check_password_hash(u["password_hash"], pw):
            session["user_id"] = u["id"]
            session["user_name"] = u["name"] or u["email"].split("@")[0]
            session["is_admin"] = bool(u["is_admin"])
            flash(f"Selamat datang, {u['name'] or email}!", "success")
            return redirect(_safe_next(request.args.get("next", "")))
        flash("Email atau password salah.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Kamu sudah keluar.", "info")
    return redirect(url_for("index"))


# ---------- admin routes ----------
@app.route("/admin")
@admin_required
def admin_dashboard():
    stats = {
        "total_orders": _one("SELECT COUNT(*) AS c FROM orders")["c"],
        "total_revenue_idr": _one("SELECT COALESCE(SUM(total_idr),0) AS s FROM orders WHERE status IN ('paid','shipped','completed')")["s"],
        "pending_orders": _one("SELECT COUNT(*) AS c FROM orders WHERE status='pending'")["c"],
        "total_products": _one("SELECT COUNT(*) AS c FROM products WHERE active=1")["c"],
    }
    recent = [_order_view(o) for o in _rows("SELECT * FROM orders ORDER BY id DESC LIMIT 8")]
    return render_template("admin/dashboard.html", stats=stats, recent_orders=recent)


@app.route("/admin/products", methods=["GET", "POST"])
@admin_required
def admin_products():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        price = _int(request.form.get("price_idr"), 0)
        cat = request.form.get("category", "").strip()
        stock = _int(request.form.get("stock"), 99)
        img = request.form.get("image_url", "").strip()
        desc = request.form.get("description", "").strip()
        if name and price > 0:
            _exec("INSERT INTO products (name, slug, description, price_idr, category, image_url, stock, active, created_at) VALUES (?,?,?,?,?,?,?,1,?)",
                  (name, db.slugify(name), desc, price, cat, img, stock, int(time.time())))
            flash("Produk ditambahkan.", "success")
        else:
            flash("Nama & harga wajib diisi.", "danger")
        return redirect(url_for("admin_products"))
    products = _rows("SELECT * FROM products ORDER BY id DESC")
    return render_template("admin/products.html", products=products)


@app.route("/admin/orders")
@admin_required
def admin_orders():
    rows = _rows(
        "SELECT o.*, u.email, u.name AS user_name FROM orders o LEFT JOIN users u ON u.id = o.user_id ORDER BY o.id DESC"
    )
    return render_template("admin/orders.html", orders=[_order_view(o) for o in rows])


@app.route("/admin/orders/<int:oid>/status", methods=["POST"])
@admin_required
def admin_order_status(oid):
    status = request.form.get("status", "pending")
    if status not in ("pending", "paid", "shipped", "completed", "cancelled"):
        status = "pending"
    if status == "paid":
        _exec("UPDATE orders SET status='paid', paid_at=? WHERE id=?", (int(time.time()), oid))
    else:
        _exec("UPDATE orders SET status=? WHERE id=?", (status, oid))
    flash(f"Status pesanan #{oid} → {status}.", "success")
    return redirect(url_for("admin_orders"))


@app.route("/api/health")
def health():
    return {"ok": True, "name": BRAND.get("name", "Kyuza Shop")}


# init DB + admin on every start (idempotent)
db.init_db()
ensure_admin()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8500))
    app.run(host="0.0.0.0", port=port, debug=False)