"""Smoke test end-to-end POS (fresh DB). Run: .venv/bin/python test_smoke.py"""
import os
import db

if os.path.exists(db.DB_PATH):
    os.remove(db.DB_PATH)

import app  # runs db.init_db() di DB baru

c = app.app.test_client()


def test():
    assert c.get("/").status_code == 200
    # buka meja 1
    r = c.post("/open/1", follow_redirects=True)
    assert r.status_code == 200
    oid = app._one("SELECT id FROM orders WHERE table_id=1 AND status='active'")["id"]
    # tambah 2x Espresso (id 1) + 1x Kopi Susu Gula Aren (id 4)
    assert c.post(f"/order/{oid}/add", data={"menu_id": 1}, follow_redirects=True).status_code == 200
    assert c.post(f"/order/{oid}/add", data={"menu_id": 1}, follow_redirects=True).status_code == 200
    assert c.post(f"/order/{oid}/add", data={"menu_id": 4}, follow_redirects=True).status_code == 200
    total = app.order_total(oid)
    assert total == 15000 * 2 + 20000, total
    # checkout tunai 100000
    r = c.post(f"/order/{oid}/checkout", data={"method": "cash", "cash": "100000"}, follow_redirects=True)
    assert r.status_code == 200
    o = app._one("SELECT * FROM orders WHERE id=?", (oid,))
    assert o["status"] == "paid"
    assert o["change_idr"] == 100000 - total
    # toggle item dapur
    item = app._one("SELECT id FROM order_items WHERE order_id=? ORDER BY id", (oid,))
    assert c.post(f"/item/{item['id']}/toggle", follow_redirects=True).status_code == 200
    # selesai -> meja free
    assert c.post(f"/order/{oid}/done", follow_redirects=True).status_code == 200
    assert app._one("SELECT status FROM tables WHERE id=1")["status"] == "free"
    # halaman lain
    assert c.get("/kitchen").status_code == 200
    assert c.get("/menu").status_code == 200
    print("SMOKE OK")


test()