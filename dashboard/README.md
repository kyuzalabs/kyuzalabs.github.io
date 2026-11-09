# Server Health Dashboard

Dashboard web yang memantau status server secara live: CPU, RAM, disk, uptime, dan status service (systemd).

## Fitur
- **CPU / RAM / Disk** — dipantau real-time (refresh 5 detik)
- **Uptime** server
- **Status service** — cek bot/service yang aktif (🟢/🔴)
- Endpoint JSON (`/api/stats`) untuk di-connect ke alat lain

## Cara jalan
```bash
python3 server_dashboard.py            # serve di http://0.0.0.0:8090
python3 server_dashboard.py --port 8080

# mantau service kamu sendiri (ganti nama service-nya)
python3 server_dashboard.py --services "my-bot.service,nginx.service"
```

Nama service bisa dicek pakai: `systemctl --type=service`

## Deploy (systemd)
```bash
sudo cp kyuza-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kyuza-dashboard.service
```

## Stack
Python 3 **stdlib only** — `http.server`, baca `/proc`, `os.statvfs`, `systemctl`. Tanpa FastAPI/psutil.

## Catatan
- CPU dihitung dari dua sampel `/proc/stat` (100ms)
- Status service pakai `systemctl is-active` (query read-only)