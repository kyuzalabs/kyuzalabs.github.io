"""
helper.py — core logic for the AI Daily Assistant (parsing + actions).

Pure functions, no external dependencies, so it can be unit-tested standalone.
Language: Indonesian-friendly (amounts like "25rb", "1,5jt", dates like "tgl 20").
"""

import os
import re
import json
import sqlite3
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

_LOCAL_TZ = ZoneInfo(os.environ.get("ASSISTANT_TZ", "Asia/Jakarta"))  # WIB (UTC+7)


def _now():
    """Local time (naive) in _LOCAL_TZ."""
    return datetime.now(_LOCAL_TZ).replace(tzinfo=None)


def _today():
    return _now().date()

# ---------------------------------------------------------------------------
# Amount parsing
# ---------------------------------------------------------------------------

_MULT = {
    "rb": 1_000, "ribu": 1_000, "k": 1_000, "kilo": 1_000,
    "jt": 1_000_000, "juta": 1_000_000, "m": 1_000_000,
    "miliar": 1_000_000_000, "milyar": 1_000_000_000, "b": 1_000_000_000,
}
_WORDS = {"setengah": 0.5, "seperempat": 0.25}
_HALF_MULT = {"ribu": 500, "juta": 500_000}  # "setengah juta" = 500k


def _to_number(raw: str) -> float:
    """Parse a numeric token with Indonesian separators: '1,5'=1.5, '50.000'=50000, '2.5'=2.5."""
    if "," in raw:
        return float(raw.replace(".", "").replace(",", "."))
    if "." in raw:
        parts = raw.split(".")
        if all(len(p) == 3 for p in parts[1:]):   # thousand separators
            return float("".join(parts))
        return float(raw)                          # decimal
    return float(raw)


def parse_amount(text: str):
    """Return the amount in base units (default IDR rupiah), or None."""
    t = (text or "").lower()
    t = re.sub(r"rp\.?\s*", " ", t).replace("idr", " ")
    t = re.sub(r"[^\w\s,.]", " ", t)

    # word fractions: "setengah juta", "seperempat juta"
    for w, frac in _WORDS.items():
        m = re.search(re.escape(w) + r"\s*(juta|jt|ribu)", t)
        if m:
            base = 1_000_000 if m.group(1) in ("juta", "jt") else 1_000
            return int(round(frac * base))

    m = re.search(r"([\d.,]+)\s*(rb|ribu|k\b|kilo|jt|juta|m\b|miliar|milyar|b\b)?", t)
    if not m:
        return None
    num = _to_number(m.group(1))
    mult = m.group(2)
    if mult:
        num *= _MULT[mult]
    return int(round(num))


# ---------------------------------------------------------------------------
# Category inference (simple keyword map)
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS = [
    ("makan-minum", ["kopi", "makan", "nasi", "bakso", "mie", "mie ayam", "minum", "teh", "es", "ngopi", "sarapan", "makan siang", "jajan", "snack", "goreng", "ayam"]),
    ("transport", ["gojek", "grab", "ojol", "bensin", "bengsin", "parkir", "taxi", "kereta", "bis ", "bus", "tol", "ojek"]),
    ("tagihan", ["listrik", "pdam", "air", "internet", "wifi", "kartu", "pulsa", "paket", "indihome", "pln", "token", "provider", "langganan", "netflix", "spotify", "tagihan"]),
    ("belanja", ["belanja", "topup", "top up", "e-wallet", "gopay", "ovo", "dana", "shopeepay", "market", "indomaret", "alfamart", "minimarket", "shopee", "tokped", "tokopedia", "beli", "barang"]),
    ("kesehatan", ["obat", "dokter", "rumah sakit", "klinik", "apotek", "bpjs", "vitamin", "cek up"]),
]

_DEFAULT_CATEGORY = "lainnya"


def infer_category(text: str) -> str:
    t = (text or "").lower()
    for cat, kws in _CATEGORY_KEYWORDS:
        for kw in kws:
            if kw in t:
                return cat
    return _DEFAULT_CATEGORY


# ---------------------------------------------------------------------------
# Intent detection + actions
# ---------------------------------------------------------------------------

def is_reminder(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in ("ingatkan", "remind", "jangan lupa", "ingetin"))


def is_split_bill(text: str) -> bool:
    t = (text or "").lower()
    return ("bagi" in t and ("bill" in t or "patungan" in t or "tagehan" in t)) or ("split" in t) or ("patungan" in t)


def parse_split(text: str):
    """Return (total, n_people, per_person) or None."""
    total = parse_amount(text)
    if total is None:
        return None
    m = re.search(r"(?:ke|buat|untuk|dibagi|antara)\s*(\d+)\s*(?:orang|org|pax|pace|way)", text.lower())
    if not m:
        # fallback: look for "N orang" anywhere
        m = re.search(r"(\d+)\s*(?:orang|org|pax|pace|way)", text.lower())
    if not m:
        return None
    n = int(m.group(1))
    if n <= 0:
        return None
    per = total // n
    return {"total": total, "people": n, "per_person": per}


# Indonesian weekday names
_DAYS = {
    "senin": 0, "selasa": 1, "rabu": 2, "kamis": 3, "jumat": 4, "jumat'agung": None,
    "sabtu": 5, "minggu": 6, "ahad": 6,
}
_MONTHS = {
    "jan": 1, "januari": 1, "feb": 2, "februari": 2, "mar": 3, "maret": 3,
    "apr": 4, "april": 4, "mei": 5, "may": 5, "jun": 6, "juni": 6,
    "jul": 7, "juli": 7, "agu": 8, "agustus": 8, "sep": 9, "september": 9,
    "okt": 10, "oktober": 10, "nov": 11, "november": 11, "des": 12, "desember": 12,
}


def parse_reminder_date(text: str):
    """Return (date, remainder_text) or (None, text). 'remainder' = the task label."""
    t = text.lower()
    today = _today()

    # relative days
    if "besok" in t:
        return today + timedelta(days=1), _strip(t, "besok")
    if "lusa" in t:
        return today + timedelta(days=2), _strip(t, "lusa")
    if "hari ini" in t:
        return today, _strip(t, "hari ini")

    # "tgl 20" / "tanggal 20" (optionally with month)
    m = re.search(r"(?:tgl|tanggal)\s*(\d{1,2})(?:\s*(jan|januari|feb|februari|mar|maret|apr|april|mei|jun|juni|jul|juli|agu|agustus|sep|september|okt|oktober|nov|november|des|desember))?", t)
    if m:
        day = int(m.group(1))
        month = _MONTHS.get(m.group(2)) if m.group(2) else None
        year = today.year
        if month is None:
            d = date(year, today.month, day)
            if d < today:
                # assume next month
                if today.month == 12:
                    d = date(year + 1, 1, day)
                else:
                    d = date(year, today.month + 1, day)
            return d, _strip(t, m.group(0))
        else:
            d = date(year, month, day)
            if d < today:
                d = date(year + 1, month, day)
            return d, _strip(t, m.group(0))

    # weekday
    for wname, wday in _DAYS.items():
        if wname in t:
            days_ahead = (wday - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7  # next week if today is that weekday and no date given
            return today + timedelta(days=days_ahead), _strip(t, wname)

    return None, text


def _strip(text: str, word: str) -> str:
    t = text
    if word:
        t = re.sub(r"\b" + re.escape(word) + r"\b", " ", t, flags=re.IGNORECASE)
    return _strip_fillers(t)


_FILLERS = ("tolong", "mohon", "ingatkan", "ingetin", "remind", "reminder",
            "aku", "saya", "gw", "gue", "guwa", "ku",
            "sih", "dong", "ya", "untuk", "buat", "buatkan",
            "jangan", "lupa", "hari", "me", "dong")


def _strip_fillers(text: str) -> str:
    t = text
    for w in _FILLERS:
        t = re.sub(r"\b" + re.escape(w) + r"\b", " ", t, flags=re.IGNORECASE)
    return " ".join(t.split())


def parse_time(text: str):
    """Return (hour, minute) or None.

    Handles: 'jam 7', 'jam 7.30 malam', 'pukul 14', '14:30', '7 malam', '3 sore'.
    """
    t = (text or "").lower()

    # "jam 7 [.30] [malam]", "pukul 14", "pk 3"
    m = re.search(r"\b(?:jam|pukul|p[kK])\s*(\d{1,2})(?:\s*[.:]\s*(\d{2}))?\s*(pagi|siang|sore|malam|subuh)?\b", t)
    if m:
        hour, minute, daypart = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    else:
        # "14:30" / "14.30"
        m = re.search(r"\b(\d{1,2})[.:](\d{2})\b", t)
        if m:
            hour, minute, daypart = int(m.group(1)), int(m.group(2)), None
        else:
            # "7 malam", "3 sore"
            m = re.search(r"\b(\d{1,2})\s*(pagi|siang|sore|malam|subuh)\b", t)
            if not m:
                return None
            hour, minute, daypart = int(m.group(1)), 0, m.group(2)

    if daypart in ("sore", "malam") and hour <= 11:
        hour += 12
    if daypart == "malam" and hour == 12:
        hour = 0  # "jam 12 malam" = midnight
    if hour > 23 or minute > 59:
        return None
    return hour, minute


def _strip_time(text: str) -> str:
    t = (text or "")
    t = re.sub(r"\b(?:jam|pukul|p[kK])\s*\d{1,2}(?:\s*[.:]\s*\d{2})?\s*(?:pagi|siang|sore|malam|subuh)?", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\b\d{1,2}\s*(?:pagi|siang|sore|malam|subuh)\b", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\b\d{1,2}[.:]\d{2}\b", " ", t)
    return " ".join(t.split())


def parse_reminder(text: str):
    """Return (datetime, task) or (None, text). Combines date + time-of-day."""
    d, task = parse_reminder_date(text)
    hhmm = parse_time(text)

    if d is None:
        if hhmm is None:
            return None, task  # no date and no time → can't schedule
        # time only → today (or tomorrow if that time already passed)
        now = _now()
        dt = datetime.combine(now.date(), time(hhmm[0], hhmm[1]))
        if dt <= now:
            dt += timedelta(days=1)
    else:
        dt = datetime.combine(d, time(hhmm[0], hhmm[1])) if hhmm else datetime.combine(d, time(9, 0))

    task = _strip_fillers(_strip_time(task))
    return dt, task


def parse_expense(text: str):
    """Return {'amount': int, 'desc': str, 'category': str} or None."""
    amount = parse_amount(text)
    if amount is None:
        return None
    desc = text.lower()
    desc = re.sub(r"\d[\d.,]*\s*(rb|ribu|k|jt|juta|m|miliar|milyar|b)?", " ", desc)
    desc = re.sub(r"(catat|keluar|pengeluaran|spend|belanja|bayar|transfer|topup|top up)\s*", " ", desc)
    desc = re.sub(r"[^\w\s]", " ", desc)
    desc = " ".join(desc.split())
    return {"amount": amount, "desc": desc or "catatan", "category": infer_category(text)}


# ---------------------------------------------------------------------------
# Storage (SQLite)
# ---------------------------------------------------------------------------

def init_db(path="assistant.db"):
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, amount INTEGER, desc TEXT, category TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        due TEXT, task TEXT, done INTEGER DEFAULT 0, chat_id TEXT)""")
    conn.commit()
    return conn


def add_expense(conn, amount, desc, category):
    conn.execute("INSERT INTO expenses (ts, amount, desc, category) VALUES (?,?,?,?)",
                 (_now().isoformat(timespec="seconds"), amount, desc, category))
    conn.commit()


def add_reminder(conn, due_dt, task, chat_id=""):
    conn.execute("INSERT INTO reminders (due, task, chat_id) VALUES (?,?,?)",
                 (due_dt.isoformat() if hasattr(due_dt, "isoformat") else due_dt, task, str(chat_id)))
    conn.commit()


def month_total(conn, y=None, m=None):
    now = _today()
    y = y or now.year
    m = m or now.month
    row = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE strftime('%Y-%m', ts) = ?",
        (f"{y:04d}-{m:02d}",)).fetchone()
    return row[0]


def list_expenses(conn, limit=10):
    return conn.execute("SELECT ts, amount, desc, category FROM expenses ORDER BY id DESC LIMIT ?", (limit,)).fetchall()


def due_reminders(conn, now=None):
    now = (now or _now()).isoformat(timespec="seconds")
    return conn.execute("SELECT id, task, chat_id, due FROM reminders WHERE due <= ? AND done = 0 ORDER BY due", (now,)).fetchall()


def list_reminders(conn):
    """All not-done reminders (upcoming + overdue), soonest first."""
    return conn.execute("SELECT id, task, chat_id, due FROM reminders WHERE done = 0 ORDER BY due").fetchall()


def mark_reminder_done(conn, rid):
    conn.execute("UPDATE reminders SET done = 1 WHERE id = ?", (rid,))
    conn.commit()


def fmt_rupiah(n):
    return f"Rp{n:,}".replace(",", ".")