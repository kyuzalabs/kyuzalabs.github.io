#!/usr/bin/env python3
"""
bot.py — AI Daily Assistant (Telegram), stdlib-only, long-polling.

Run:
    export BOT_TOKEN=123456:ABC...   # or create token.txt next to this file
    python3 bot.py

Chat to it in natural Indonesian / English:
    "catat kopi 25rb"
    "ingatkan bayar listrik tgl 20"
    "bagi bill 180rb ke 4 orang"
Commands: /start /help /catat /total /remind
"""

import json
import os
import time
import urllib.parse
import urllib.request

from helper import (
    init_db, add_expense, add_reminder, month_total, list_expenses,
    due_reminders, list_reminders, mark_reminder_done, parse_expense, parse_split,
    parse_reminder, is_reminder, is_split_bill, fmt_rupiah, infer_category,
)

API = "https://api.telegram.org/bot"


def get_token():
    tok = os.environ.get("BOT_TOKEN")
    if tok:
        return tok
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.txt")
    if os.path.exists(here):
        return open(here).read().strip()
    raise SystemExit("Set BOT_TOKEN env var, or drop a token.txt next to bot.py")


def api_call(token, method, **params):
    url = f"{API}{token}/{method}"
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    # timeout must exceed getUpdates' long-poll (30s) so it doesn't spuriously time out
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Pure message handler (testable without Telegram)
# ---------------------------------------------------------------------------

INTRO = (
    "Halo! Aku AI Daily Assistant 🤖\n\n"
    "Kirim pesan natural, contoh:\n"
    "• catat kopi 25rb\n"
    "• makan siang 50k\n"
    "• ingatkan bayar listrik tgl 20\n"
    "• bagi bill 180rb ke 4 orang\n\n"
    "Perintah: /catat (list), /total (ringkasan), /remind (reminder aktif), /help"
)


def handle(conn, text: str, chat_id: str = "") -> str:
    t = text.strip()

    # commands
    if t.startswith("/"):
        cmd = t.split()[0].lower().lstrip("/").split("@")[0]
        if cmd in ("start", "help"):
            return INTRO
        if cmd in ("catat", "list", "expenses"):
            rows = list_expenses(conn, 10)
            if not rows:
                return "Belum ada catatan. Coba: catat kopi 25rb"
            lines = ["📒 Pengeluaran terakhir:"]
            for ts, amount, desc, cat in rows:
                lines.append(f"  • {ts[:10]} {desc} — {fmt_rupiah(amount)} ({cat})")
            return "\n".join(lines)
        if cmd in ("total", "ringkasan", "summary"):
            total = month_total(conn)
            return f"📊 Total pengeluaran bulan ini: {fmt_rupiah(total)}"
        if cmd in ("remind", "reminders"):
            rows = list_reminders(conn)
            if not rows:
                return "Tidak ada reminder aktif."
            return "⏰ Reminder aktif:\n" + "\n".join(
                f"  • {task} — {due[:16].replace('T', ' ')}" for _, task, _, due in rows)
        return "Perintah nggak dikenal. Ketik /help."

    # natural-language intents
    if is_reminder(t):
        dt, task = parse_reminder(t)
        if dt and task:
            add_reminder(conn, dt, task, chat_id)
            return f"✅ Dicatat reminder: “{task}” → {dt.strftime('%d %b %Y %H:%M')}"
        return "Maaf, tanggal/waktunya belum kebaca. Contoh: ingatkan bayar listrik tgl 20 jam 7 malam"

    if is_split_bill(t):
        sp = parse_split(t)
        if sp:
            return (f"💸 Total {fmt_rupiah(sp['total'])} dibagi {sp['people']} orang "
                    f"= {fmt_rupiah(sp['per_person'])}/orang")
        return "Contoh: bagi bill 180rb ke 4 orang"

    e = parse_expense(t)
    if e and e["amount"] > 0:
        add_expense(conn, e["amount"], e["desc"], e["category"])
        return f"💾 Dicatat: {e['desc']} — {fmt_rupiah(e['amount'])} ({e['category']})"

    return "Belum paham maksudnya. Coba: catat kopi 25rb, ingatkan …, atau bagi bill …"


# ---------------------------------------------------------------------------
# Telegram wiring
# ---------------------------------------------------------------------------

def send(token, chat_id, text):
    api_call(token, "sendMessage", chat_id=chat_id, text=text)


def run(token):
    conn = init_db(os.path.join(os.path.dirname(os.path.abspath(__file__)), "assistant.db"))
    offset = 0
    print("Bot aktif. Kirim /start di Telegram.", flush=True)
    last_reminder_check = 0

    while True:
        try:
            # reminder sweep (every 60s)
            now = time.time()
            if now - last_reminder_check >= 60:
                last_reminder_check = now
                for rid, task, chat_id, due in due_reminders(conn):
                    if chat_id:
                        send(token, chat_id, f"⏰ Reminder: {task}")
                        mark_reminder_done(conn, rid)

            # poll updates
            updates = api_call(token, "getUpdates", offset=offset, timeout=30)
            for u in updates.get("result", []):
                offset = u["update_id"] + 1
                msg = u.get("message")
                if not msg or "text" not in msg:
                    continue
                chat_id = msg["chat"]["id"]
                reply = handle(conn, msg["text"], str(chat_id))
                send(token, chat_id, reply)

        except KeyboardInterrupt:
            print("Stop.", flush=True)
            break
        except Exception as e:  # noqa: BLE001 — keep polling through transient errors
            print("error:", e, flush=True)
            time.sleep(3)


if __name__ == "__main__":
    run(get_token())