import os
import sys

# set admin test password SEBELUM import app (agar seed admin memakainya)
os.environ.setdefault("ADMIN_PASSWORD", "admin123")

# pastikan jalankan dari folder mini-store biar import app & db ketemu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as store_app

app = store_app.app
c = app.test_client()

results = []


def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), "-", name)


# home
r = c.get("/")
check("GET / -> 200", r.status_code == 200)
html = r.get_data(as_text=True)
check("halaman berisi product-card / nama produk", ("product-card" in html or "Kopi" in html or "TWS" in html))

# product count dari katalog
import db
print("catalog count:", len(db.load_catalog()))

# register
r = c.post("/register", data={"name": "Test Buyer", "email": "buyer@test.com", "password": "rahasia123"}, follow_redirects=True)
check("POST /register ok", r.status_code == 200)

# login buyer
r = c.post("/login", data={"email": "buyer@test.com", "password": "rahasia123"}, follow_redirects=True)
check("POST /login buyer ok", "Selamat datang" in r.get_data(as_text=True) or r.status_code == 200)

# add to cart
r = c.post("/cart/add", data={"product_id": 1, "qty": 2}, follow_redirects=True)
check("POST /cart/add ok", r.status_code == 200)

# cart
r = c.get("/cart")
check("GET /cart ada Keranjang", "Keranjang" in r.get_data(as_text=True))

# checkout
r = c.get("/checkout")
check("GET /checkout -> 200", r.status_code == 200)

# checkout create order
r = c.post("/checkout", data={"crypto_symbol": "USDC"}, follow_redirects=True)
html = r.get_data(as_text=True)
check("POST /checkout -> halaman pay", r.status_code == 200 and ("USDC" in html or "Pembayaran" in html))

# admin login
c.post("/logout")
r = c.post("/login", data={"email": "admin@kyuzashop.id", "password": "admin123"}, follow_redirects=True)

r = c.get("/admin")
check("GET /admin dashboard", r.status_code == 200 and "Dashboard" in r.get_data(as_text=True))
r = c.get("/admin/products")
check("GET /admin/products -> 200", r.status_code == 200)
r = c.get("/admin/orders")
check("GET /admin/orders -> 200", r.status_code == 200)

print()
print("TOTAL:", sum(1 for _, ok in results if ok), "/", len(results), "PASS")
if all(ok for _, ok in results):
    print("SMOKE TEST OK")
else:
    print("ADA YANG GAGAL — periksa di atas")
    sys.exit(1)