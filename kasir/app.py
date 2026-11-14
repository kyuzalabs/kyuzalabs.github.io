"""Aplikasi Kasir (POS) fullstack — Flask + SQLite."""
import os, time
from flask import Flask, request, render_template, redirect, url_for, flash
import db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "kasir-demo-secret")


def _rows(sql, args=()):
    conn = db.get_conn()
    r = [dict(x) for x in conn.execute(sql, args).fetchall()]
    conn.close()
    return r


def _one(sql, args=()):
    conn = db.get_conn()
    r = conn.execute(sql, args).fetchone()
    conn.close()
    return dict(r) if r else None


def _exec(sql, args=()):
    conn = db.get_conn()
    with conn:
        conn.execute(sql, args)
    conn.close()


def _int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def order_total(order_id):
    row = _one("SELECT COALESCE(SUM(price*qty),0) AS t FROM order_items WHERE order_id=?", (order_id,))
    return row["t"] if row else 0


def _sync_total(order_id):
    _exec("UPDATE orders SET total=? WHERE id=?", (order_total(order_id), order_id))


@app.route("/")
def index():
    tables = _rows("SELECT * FROM tables ORDER BY id")
    menu = _rows("SELECT * FROM menu ORDER BY category, name")
    active_orders = _rows(
        "SELECT o.*, t.name AS table_name FROM orders o LEFT JOIN tables t ON t.id=o.table_id "
        "WHERE o.status IN ('active','paid') ORDER BY o.id DESC"
    )
    revenue = _one("SELECT COALESCE(SUM(total),0) AS t FROM orders WHERE status IN ('paid','done')")
    table_order = {}
    for o in active_orders:
        if o["status"] == "active" and o["table_id"]:
            table_order[o["table_id"]] = o["id"]
    for t in tables:
        t["order_id"] = table_order.get(t["id"])
    return render_template("index.html", tables=tables, menu=menu,
                           active_orders=active_orders,
                           revenue=revenue["t"] if revenue else 0)


@app.route("/open/<int:table_id>", methods=["POST"])
def open_table(table_id):
    t = _one("SELECT * FROM tables WHERE id=?", (table_id,))
    if not t:
        flash("Meja tidak ditemukan.")
        return redirect(url_for("index"))
    if t["status"] == "busy":
        o = _one("SELECT id FROM orders WHERE table_id=? AND status='active'", (table_id,))
        return redirect(url_for("order", order_id=o["id"])) if o else redirect(url_for("index"))
    _exec("INSERT INTO orders (table_id, status, created_at) VALUES (?, 'active', ?)",
          (table_id, int(time.time())))
    _exec("UPDATE tables SET status='busy' WHERE id=?", (table_id,))
    oid = _one("SELECT id FROM orders WHERE table_id=? AND status='active' ORDER BY id DESC", (table_id,))["id"]
    return redirect(url_for("order", order_id=oid))


@app.route("/order/<int:order_id>")
def order(order_id):
    o = _one("SELECT o.*, t.name AS table_name FROM orders o LEFT JOIN tables t ON t.id=o.table_id WHERE o.id=?", (order_id,))
    if not o:
        flash("Order tidak ditemukan.")
        return redirect(url_for("index"))
    items = _rows("SELECT * FROM order_items WHERE order_id=?", (order_id,))
    menu = _rows("SELECT * FROM menu ORDER BY category, name")
    return render_template("order.html", o=o, items=items, menu=menu, total=o["total"])


@app.route("/order/<int:order_id>/add", methods=["POST"])
def add_item(order_id):
    o = _one("SELECT * FROM orders WHERE id=?", (order_id,))
    if not o or o["status"] != "active":
        flash("Order sudah dibayar/selesai.")
        return redirect(url_for("order", order_id=order_id))
    menu_id = _int(request.form.get("menu_id"))
    m = _one("SELECT * FROM menu WHERE id=?", (menu_id,))
    if m:
        existing = _one("SELECT id FROM order_items WHERE order_id=? AND menu_id=? AND status='pending'",
                        (order_id, menu_id))
        if existing:
            _exec("UPDATE order_items SET qty=qty+1 WHERE id=?", (existing["id"],))
        else:
            _exec("INSERT INTO order_items (order_id, menu_id, name, price, qty, status) VALUES (?,?,?,?,1,'pending')",
                  (order_id, menu_id, m["name"], m["price"]))
        _sync_total(order_id)
    return redirect(url_for("order", order_id=order_id))


@app.route("/order/<int:order_id>/qty", methods=["POST"])
def set_qty(order_id):
    item_id = _int(request.form.get("item_id"))
    qty = max(1, min(_int(request.form.get("qty"), 1), 99))
    _exec("UPDATE order_items SET qty=? WHERE id=? AND order_id=?", (qty, item_id, order_id))
    _sync_total(order_id)
    return redirect(url_for("order", order_id=order_id))


@app.route("/order/<int:order_id>/checkout", methods=["POST"])
def checkout(order_id):
    o = _one("SELECT * FROM orders WHERE id=?", (order_id,))
    if not o or o["status"] != "active":
        return redirect(url_for("order", order_id=order_id))
    method = request.form.get("method", "cash")
    cash = _int(request.form.get("cash"))
    total = order_total(order_id)
    change = max(0, cash - total) if method == "cash" else 0
    _exec("UPDATE orders SET status='paid', payment_method=?, cash_received=?, change_idr=?, total=? WHERE id=?",
          (method, cash if method == "cash" else None, change, total, order_id))
    flash(f"Pembayaran {method.upper()} diterima. Pesanan dikirim ke dapur.")
    return redirect(url_for("kitchen"))


@app.route("/order/<int:order_id>/done", methods=["POST"])
def finish_order(order_id):
    o = _one("SELECT * FROM orders WHERE id=?", (order_id,))
    if o:
        _exec("UPDATE orders SET status='done' WHERE id=?", (order_id,))
        _exec("UPDATE tables SET status='free' WHERE id=?", (o["table_id"],))
    return redirect(url_for("index"))


@app.route("/item/<int:item_id>/toggle", methods=["POST"])
def toggle_item(item_id):
    it = _one("SELECT * FROM order_items WHERE id=?", (item_id,))
    if it:
        ns = "done" if it["status"] == "pending" else "pending"
        _exec("UPDATE order_items SET status=? WHERE id=?", (ns, item_id))
    return redirect(url_for("kitchen"))


@app.route("/kitchen")
def kitchen():
    orders = _rows(
        "SELECT o.*, t.name AS table_name FROM orders o LEFT JOIN tables t ON t.id=o.table_id "
        "WHERE o.status IN ('active','paid') ORDER BY o.id"
    )
    for o in orders:
        o["lines"] = _rows("SELECT * FROM order_items WHERE order_id=? ORDER BY id", (o["id"],))
    return render_template("kitchen.html", orders=orders)


@app.route("/menu", methods=["GET", "POST"])
def menu():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        price = _int(request.form.get("price"))
        cat = request.form.get("category", "Umum").strip() or "Umum"
        if name and price > 0:
            _exec("INSERT INTO menu (name, price, category, slug) VALUES (?,?,?,?)",
                  (name, price, cat, db.slugify(name)))
        return redirect(url_for("menu"))
    items = _rows("SELECT * FROM menu ORDER BY category, name")
    return render_template("menu.html", items=items)


@app.route("/menu/<int:item_id>/delete", methods=["POST"])
def delete_menu(item_id):
    _exec("DELETE FROM menu WHERE id=?", (item_id,))
    return redirect(url_for("menu"))


db.init_db()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=int(os.environ.get("PORT", 5000)))