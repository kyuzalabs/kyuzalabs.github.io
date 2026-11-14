"""Smoke test end-to-end (fresh DB). Run: .venv/bin/python test_smoke.py"""
import os
import db

if os.path.exists(db.DB_PATH):
    os.remove(db.DB_PATH)

import app  # menjalankan db.init_db() + ensure_admin() di DB baru

c = app.app.test_client()


def test():
    assert c.get("/").status_code == 200
    r = c.post("/register", data={"email": "u@test.com", "password": "rahasia1"},
               follow_redirects=True)
    assert r.status_code == 200
    r = c.post("/login", data={"email": "u@test.com", "password": "rahasia1"},
               follow_redirects=True)
    assert r.status_code == 200
    print("SMOKE OK")


test()