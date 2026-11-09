#!/usr/bin/env python3
"""
Dashboard health server — pantau CPU, RAM, disk, uptime, dan status service,
disajikan sebagai halaman web + endpoint JSON.

Pure stdlib (http.server) — tidak butuh pip install.

Usage:
    python3 server_dashboard.py            # serve di http://0.0.0.0:8090
    python3 server_dashboard.py --port 8090
"""

import argparse
import json
import os
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

DEFAULT_SERVICES = "kyuza-assistant.service,kyuza-projects.service,kyuza-jobs.timer"
SERVICES = []

PAGE = """<!DOCTYPE html>
<html lang="id"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Server Dashboard</title>
<style>
body{background:#0d1117;color:#e6edf3;font-family:-apple-system,Segoe UI,Roboto,sans-serif;padding:24px;margin:0}
.wrap{max-width:760px;margin:0 auto}
h1{font-size:1.4rem}.sub{color:#8b949e;font-size:.85rem;margin-bottom:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px}
.card{background:#161b22;border:1px solid #21262d;border-radius:12px;padding:16px}
.card .l{color:#8b949e;font-size:.75rem}.card .v{font-size:1.6rem;font-weight:700;margin-top:4px}
.bar{height:8px;background:#21262d;border-radius:4px;margin-top:10px;overflow:hidden}
.bar i{display:block;height:100%;background:#8b5cf6}
.svc{display:flex;justify-content:space-between;align-items:center;background:#161b22;border:1px solid #21262d;border-radius:10px;padding:12px 16px;margin-bottom:8px}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:8px}
.up{background:#3fb950}.down{background:#f85149}
.foot{color:#8b949e;font-size:.75rem;text-align:center;margin-top:24px}
</style></head><body><div class="wrap">
<h1>🖥️ Server Dashboard</h1>
<div class="sub">Live — status server Kyuza</div>
<div class="grid" id="cards">memuat…</div>
<h2 style="font-size:1rem;margin:24px 0 10px">Services (systemd)</h2>
<div id="svcs">memuat…</div>
<div class="foot">refresh otomatis tiap 5 detik · endpoint: /api/stats</div>
</div>
<script>
async function load(){
  const d = await (await fetch('/api/stats')).json();
  const n = (x,p=1)=>x.toFixed(p);
  document.getElementById('cards').innerHTML = `
    <div class="card"><div class="l">CPU</div><div class="v">${n(d.cpu)}%</div><div class="bar"><i style="width:${d.cpu}%"></i></div></div>
    <div class="card"><div class="l">RAM</div><div class="v">${n(d.mem)}%</div><div class="bar"><i style="width:${d.mem}%"></i></div></div>
    <div class="card"><div class="l">Disk</div><div class="v">${n(d.disk)}%</div><div class="bar"><i style="width:${d.disk}%"></i></div></div>
    <div class="card"><div class="l">Uptime</div><div class="v" style="font-size:1.1rem">${d.uptime}</div></div>
    <div class="card"><div class="l">RAM terpakai</div><div class="v" style="font-size:1.1rem">${d.mem_used}</div></div>
  `;
  document.getElementById('svcs').innerHTML = d.services.map(s =>
    `<div class="svc"><span><span class="dot ${s.active?'up':'down'}"></span>${s.name}</span><span style="color:#8b949e;font-size:.8rem">${s.active?'🟢 aktif':'🔴 mati'}</span></div>`
  ).join('');
}
load(); setInterval(load, 5000);
</script>
</body></html>"""


def read_cpu():
    """Baca %CPU dari /proc/stat (dua sampel 100ms)."""
    def sample():
        with open("/proc/stat") as f:
            parts = f.readline().split()
        total = sum(int(x) for x in parts[1:])
        idle = int(parts[4])
        return total, idle
    t1, i1 = sample()
    time.sleep(0.1)
    t2, i2 = sample()
    dt = t2 - t1
    if dt == 0:
        return 0.0
    return round((1 - (i2 - i1) / dt) * 100, 1)


def read_mem():
    with open("/proc/meminfo") as f:
        m = {l.split(":")[0]: int(l.split()[1]) for l in f if ":" in l}
    used = m["MemTotal"] - m["MemAvailable"]
    pct = used / m["MemTotal"] * 100
    return {"pct": round(pct, 1), "used": used}


def read_disk():
    st = os.statvfs("/")
    pct = (1 - st.f_bavail / st.f_blocks) * 100
    return round(pct, 1)


def read_uptime():
    with open("/proc/uptime") as f:
        sec = float(f.readline().split()[0])
    d, h = divmod(int(sec), 86400)
    h, m = divmod(h, 3600)
    m = m // 60
    return f"{d}h {h}j {m}m" if d else f"{h}j {m}m"


def service_status(name):
    import subprocess
    try:
        r = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True, timeout=3)
        return r.stdout.strip() == "active"
    except Exception:
        return False


def collect():
    mem = read_mem()
    return {
        "cpu": read_cpu(),
        "mem": mem["pct"],
        "mem_used": f"{mem['used'] / 1024 / 1024:.1f} GB",
        "disk": read_disk(),
        "uptime": read_uptime(),
        "services": [{"name": s, "active": service_status(s)} for s in SERVICES],
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


class H(BaseHTTPRequestHandler):
    def _json(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/stats":
            self._json(collect())
        else:
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, *a):
        pass  # hentikan log request agar bersih


def main():
    ap = argparse.ArgumentParser(description="Dashboard health server (systemd + /proc).")
    ap.add_argument("--port", type=int, default=8090)
    ap.add_argument("--services", default=DEFAULT_SERVICES,
                    help="nama service systemd yang dipantau, dipisah koma (contoh: \"my-bot.service,nginx.service\")")
    args = ap.parse_args()
    global SERVICES
    SERVICES = [s.strip() for s in args.services.split(",") if s.strip()]
    print(f"Dashboard aktif di http://0.0.0.0:{args.port}")
    print(f"Memantau service: {', '.join(SERVICES)}")
    HTTPServer(("0.0.0.0", args.port), H).serve_forever()


if __name__ == "__main__":
    main()