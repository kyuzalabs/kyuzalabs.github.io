# AI Daily Assistant (Telegram)

A **natural-language personal assistant** Telegram bot. Chat to it like you'd text a friend and it logs expenses, sets reminders, and splits bills — no commands to memorize.

## What it does

| You say | It does |
|---|---|
| `catat kopi 25rb` | logs an expense (Rp25.000, category "makan-minum") |
| `makan siang 50k` | logs Rp50.000, auto-categorised |
| `ingatkan bayar listrik tgl 20` | sets a reminder for the 20th |
| `bagi bill 180rb ke 4 orang` | returns Rp45.000/person |

Plus commands: `/start`, `/help`, `/catat` (recent expenses), `/total` (month total), `/remind` (active reminders).

## Why it's interesting

- **Natural language** — parses Indonesian money slang (`25rb`, `1,5jt`, `50.000`, `setengah juta`) and relative dates (`besok`, `lusa`, `tgl 20`, `hari senin`)
- **Zero dependencies** — pure Python stdlib (no `requests`, no `python-telegram-bot`)
- **SQLite storage** — local, no server needed
- **Reminder cron** — polls long-running and pushes due reminders automatically

## How to run

### 1. Create a bot (once)

Open Telegram → search `@BotFather` → `/newbot` → name it → BotFather gives you a token like `123456:ABC-DEF...`.

### 2. Run

```bash
export BOT_TOKEN=123456:ABC-DEF...
python3 bot.py
```

Or save the token in a `token.txt` file next to `bot.py` (simpler):

```
123456:ABC-DEF...
```

### 3. Chat

Message your bot: `catat kopi 25rb`, then `/total`.

## Files

- `bot.py` — Telegram long-polling + wiring
- `helper.py` — parsing + storage (unit-testable, no network)
- `assistant.db` — SQLite (created on first run)

## Stack

Python 3 (stdlib only) · SQLite · Telegram Bot API

## Roadmap

- [ ] LLM fallback for sentences the regex misses (optional, keep the deterministic path as default)
- [ ] Web dashboard for expenses
- [ ] WhatsApp port (needs Meta Business + webhook)