#!/usr/bin/env python3
"""
Job Scraper — kumpulkan lowongan remote/tech dari sumber gratis, filter keyword,
tampilkan (atau kirim) digest harian.

Sumber (gratis, tanpa API key):
  • Remote OK   — https://remoteok.com/api
  • Arbeitnow   — https://www.arbeitnow.com/api/job-board-api

Usage:
    python3 job_scraper.py                          # default keywords
    python3 job_scraper.py --keyword crypto web3    # filter keyword custom
    python3 job_scraper.py --top 10 --json          # 10 teratas, JSON
    python3 job_scraper.py --send                   # kirim ke Telegram (butuh env BOT_TOKEN & CHAT_ID)
"""

import argparse
import json
import os
import urllib.parse
import urllib.request

SOURCES = {
    "remoteok": "https://remoteok.com/api",
    "arbeitnow": "https://www.arbeitnow.com/api/job-board-api",
}

# kata kunci default — cocok buat cari kerja remote/tech/crypto + content/support
DEFAULT_KEYWORDS = [
    "crypto", "web3", "blockchain", "defi", "solidity", "ethereum", "solana",
    "python", "javascript", "node", "react", "ai", "data",
    "content", "community", "support", "marketing", "design", "analyst",
]

UA = {"User-Agent": "job-scraper/1.0 (+personal portfolio)"}


def fetch_json(url):
    req = urllib.request.Request(url, headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace"))


def fmt_salary(mn, mx):
    if not mn and not mx:
        return ""
    if mn and mx:
        return f"${mn/1000:.0f}k–${mx/1000:.0f}k/thn"
    if mx:
        return f"sampai ${mx/1000:.0f}k/thn"
    return f"${mn/1000:.0f}k+/thn"


def scrape_remoteok():
    data = fetch_json(SOURCES["remoteok"])
    out = []
    for j in data[1:]:  # baris pertama = metadata/legal
        out.append({
            "title": j.get("position") or "",
            "company": j.get("company") or "",
            "location": (j.get("location") or "").strip() or "Remote",
            "salary": fmt_salary(j.get("salary_min"), j.get("salary_max")),
            "tags": " ".join(j.get("tags") or []),
            "url": j.get("url") or j.get("apply_url") or "",
            "source": "RemoteOK",
        })
    return out


def scrape_arbeitnow():
    data = fetch_json(SOURCES["arbeitnow"])
    out = []
    for j in data.get("data", []):
        out.append({
            "title": j.get("title") or "",
            "company": j.get("company_name") or "",
            "location": (j.get("location") or "").strip() or "Remote",
            "salary": "",  # arbeitnow tidak menyediakan gaji
            "tags": " ".join(j.get("job_types") or []),
            "url": j.get("url") or "",
            "source": "Arbeitnow",
        })
    return out


def scrape():
    jobs = []
    for name, fn in (("RemoteOK", scrape_remoteok), ("Arbeitnow", scrape_arbeitnow)):
        try:
            jobs.extend(fn())
        except Exception as e:
            print(f"[!] gagal fetch {name}: {e}", file=__import__("sys").stderr)
    return jobs


def match(job, keywords):
    hay = " ".join([job["title"], job["company"], job["tags"], job["location"]]).lower()
    return any(k.lower() in hay for k in keywords)


def filter_jobs(jobs, keywords, limit):
    hits = [j for j in jobs if match(j, keywords)]
    # yang ada gaji diurutkan duluan, lalu abjad judul
    hits.sort(key=lambda j: (not j["salary"], j["title"].lower()))
    return hits[:limit] if limit else hits


def render(jobs, keywords):
    lines = []
    now = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
    lines.append(f"🔎 Digest lowongan — {now}")
    lines.append(f"   keyword: {', '.join(keywords[:8])}{'…' if len(keywords) > 8 else ''}")
    lines.append("─" * 34)
    if not jobs:
        lines.append("Tidak ada lowongan yang cocok hari ini.")
        return "\n".join(lines)
    for i, j in enumerate(jobs, 1):
        loc = f"🌍 {j['location']}"
        sal = f" 💰 {j['salary']}" if j["salary"] else ""
        lines.append(f"{i}. {j['title']} — {j['company']}")
        lines.append(f"   {loc}{sal}")
        if j["tags"]:
            lines.append(f"   🏷 {j['tags'][:80]}")
        lines.append(f"   🔗 {j['url']}")
        lines.append("")
    lines.append(f"Total: {len(jobs)} lowongan")
    return "\n".join(lines)


def send_telegram(bot_token, chat_id, text):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id, "text": text, "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    urllib.request.urlopen(req, timeout=30)


def main():
    ap = argparse.ArgumentParser(description="Kumpulkan & filter lowongan remote/tech.")
    ap.add_argument("--keyword", nargs="+", default=None, help="keyword filter (default: tech/crypto/remote)")
    ap.add_argument("--top", type=int, default=None, help="batasi jumlah hasil")
    ap.add_argument("--json", action="store_true", help="output JSON")
    ap.add_argument("--send", action="store_true", help="kirim ke Telegram (env BOT_TOKEN + CHAT_ID)")
    args = ap.parse_args()

    keywords = args.keyword or DEFAULT_KEYWORDS
    jobs = filter_jobs(scrape(), keywords, args.top)

    if args.json:
        print(json.dumps(jobs, ensure_ascii=False, indent=2))
        return

    text = render(jobs, keywords)
    print(text)

    if args.send:
        token = os.environ.get("BOT_TOKEN")
        chat = os.environ.get("CHAT_ID")
        if not token or not chat:
            print("\n[!] --send butuh env BOT_TOKEN dan CHAT_ID")
            return
        send_telegram(token, chat, text)
        print("\n✅ terkirim ke Telegram")


if __name__ == "__main__":
    main()