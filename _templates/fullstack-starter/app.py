"""Full-stack Flask + SQLite starter (production-hardened, minim error)."""
import os, time, secrets
from functools import wraps
from flask import Flask, request, render_template, session, redirect, flash
from werkzeug.security import generate_password_hash, check_password_hash
import db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_urlsafe(32))


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


def login_required(f):
    @wraps(f)
    def w(*a, **kw):
        if not session.get("user_id"):
            return redirect("/login")
        return f(*a, **kw)
    return w


def admin_required(f):
    @wraps(f)
    def w(*a, **kw):
        if not session.get("is_admin"):
            return redirect("/login")
        return f(*a, **kw)
    return w


def ensure_admin():
    email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
    pw = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(12)
    u = _one("SELECT id FROM users WHERE email=?", (email,))
    if not u:
        _exec(
            "INSERT INTO users (email, password_hash, is_admin, created_at) VALUES (?,?,1,?)",
            (email, generate_password_hash(pw), int(time.time())),
        )
        if not os.environ.get("ADMIN_PASSWORD"):
            print(f"[init] admin dibuat: {email} | password (simpan!): {pw}")


@app.route("/")
def index():
    products = _rows("SELECT * FROM products ORDER BY id")
    return render_template("index.html", products=products)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        pw = request.form.get("password", "")
        if "@" not in email or len(pw) < 6:
            flash("Email valid & password minimal 6 karakter.")
            return redirect("/register")
        if _one("SELECT id FROM users WHERE email=?", (email,)):
            flash("Email sudah terdaftar.")
            return redirect("/register")
        _exec(
            "INSERT INTO users (email, password_hash, is_admin, created_at) VALUES (?,?,0,?)",
            (email, generate_password_hash(pw), int(time.time())),
        )
        return redirect("/login")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        pw = request.form.get("password", "")
        u = _one("SELECT * FROM users WHERE email=?", (email,))
        if u and check_password_hash(u["password_hash"], pw):
            session["user_id"] = u["id"]
            session["is_admin"] = bool(u["is_admin"])
            return redirect("/")
        flash("Email/password salah.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


db.init_db()
ensure_admin()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=int(os.environ.get("PORT", 5000)))