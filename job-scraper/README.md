# Job Scraper

Kumpulkan lowongan remote/tech dari **sumber gratis**, filter sesuai keyword, tampilkan (atau kirim) digest harian ke Telegram/email.

## Sumber (gratis, tanpa API key)
- **Remote OK** — `https://remoteok.com/api` (ada gaji & tags)
- **Arbeitnow** — `https://www.arbeitnow.com/api/job-board-api`

## Fitur
- Gabung 2 sumber → satu daftar
- Filter keyword (crypto, web3, python, dll — bisa custom)
- Tampil judul, perusahaan, lokasi, gaji, tags, link
- `--send` kirim digest ke Telegram (butuh env `BOT_TOKEN` + `CHAT_ID`)
- `--json` untuk output machine-readable

## Usage
```bash
# lowongan default (tech/crypto/remote)
python3 job_scraper.py

# filter keyword custom
python3 job_scraper.py --keyword crypto web3 blockchain

# 10 teratas, JSON
python3 job_scraper.py --top 10 --json

# kirim ke Telegram (set env dulu)
BOT_TOKEN=... CHAT_ID=... python3 job_scraper.py --keyword crypto --send
```

## Stack
Python 3 (stdlib only — `urllib`, `json`, `argparse`).

## Disclaimer
Sumber data adalah API publik resmi (RemoteOK via [Remote OK API](https://remoteok.com/api), Arbeitnow). Tool ini hanya agregasi + filter; **jangan hard-scrape** situs lowongan yang melarangnya, dan selalu patuhi ToS tiap sumber.