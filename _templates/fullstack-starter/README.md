# Fullstack Starter (Flask + SQLite + Jinja2)

Template dasar full-stack web app siap pakai. Tinggal copy folder ini ke nama project kamu, lalu sesuaikan.

## Jalankan (local)

```bash
cd <project-name>
uv venv .venv
uv pip install --python .venv/bin/python flask
.venv/bin/python app.py          # buka http://127.0.0.1:5000
```

## Test

```bash
.venv/bin/python test_smoke.py   # harus keluar "SMOKE OK"
```

## Admin

- Email default: `admin@example.com`
- Password: set env `ADMIN_PASSWORD` sebelum run, atau dibikin otomatis (ditampilkan sekali di log).

## Catatan produksi

- Ganti `app.secret_key` via env `SECRET_KEY`.
- Jangan commit `store.db` / `.env` (udah ada di `.gitignore`).
- Untuk deploy: baca `references/fullstack-web-app.md` di skill building-portfolio-projects.