import os
import sys

os.environ.setdefault("ADMIN_PASSWORD", "admin123")
os.environ.setdefault("KASIR_PASSWORD", "kasir123")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as kasir_app

app = kasir_app.app
c = app.test_client()

results = []


def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), "-", name)


# login page
r = c.get("/login")
check("GET /login -> 200", r.status_code == 200)

# login kasir
r = c.post("/login", data={"email": "kasir@kyuzakasir.id", "password": "kasir123"}, follow_redirects=True)
check("login kasir -> kasir screen", r.status_code == 200)

# kasir screen
r = c.get("/kasir")
html = r.get_data(as_text=True)
check("kasir: ada Meja 1", "Meja 1" in html)
check("kasir: ada menu Nasi Goreng", "Nasi Goreng" in html)

# open table 1
r = c.post("/kasir/table/1/open", follow_redirects=True)
check("buka Meja 1", r.status_code == 200)

# add items
r = c.post("/order/1/add", data={"product_id": 1}, follow_redirects=True)
check("tambah item #1", r.status_code == 200)
r = c.post("/order/1/add", data={"product_id": 9}, follow_redirects=True)
check("tambah item #9 (minuman)", r.status_code == 200)

# view order
r = c.get("/kasir?order=1")
html = r.get_data(as_text=True)
check("panel order ada item", "Nasi Goreng Spesial" in html)
check("panel order ada tombol Bayar", "Bayar" in html)

# pay cash
r = c.post("/order/1/pay", data={"method": "cash", "cash_received": 100000}, follow_redirects=True)
html = r.get_data(as_text=True)
check("bayar -> struk", r.status_code == 200 and ("TOTAL" in html or "KYZU" in html))

# dapur
r = c.get("/dapur")
html = r.get_data(as_text=True)
check("dapur: ada pesanan", "Nasi Goreng Spesial" in html)

# mark item done
items = kasir_app.get_items(1)
r = c.post(f"/dapur/item/{items[0]['id']}/done", follow_redirects=True)
check("tandai item selesai", r.status_code == 200)

# done order
r = c.post("/order/1/done", follow_redirects=True)
check("selesai & bebaskan meja", r.status_code == 200)

# table free again
t = kasir_app.db.fetchone("SELECT status FROM tables WHERE id=1")
check("Meja 1 bebas lagi", t["status"] == "free")

# admin
c.post("/logout")
c.post("/login", data={"email": "admin@kyuzakasir.id", "password": "admin123"}, follow_redirects=True)
r = c.get("/admin")
check("admin dashboard", r.status_code == 200 and "Dashboard" in r.get_data(as_text=True))
for path in ["/admin/menu", "/admin/tables", "/admin/orders"]:
    check(f"GET {path} -> 200", c.get(path).status_code == 200)

print()
print("TOTAL:", sum(1 for _, ok in results if ok), "/", len(results), "PASS")
if not all(ok for _, ok in results):
    print("ADA YANG GAGAL - periksa di atas")
    sys.exit(1)
print("SMOKE TEST OK")