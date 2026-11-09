# Mint Radar

Scan the [Agent ID project catalog](https://agentidhub.eth.limo/project-catalog.js) for **free & low-risk active mints** — and skip the ones that will burn gas for nothing.

## Why

Hunting agent-gated mints on BSC means paying gas for every `mint()` call. This tool reads a ~1,000-project catalog that already carries on-chain status + a human/AI verdict per project, then filters it down to what's actually worth claiming.

## Features

- **Free-only filter** — list just the gas-only mints (`--free`)
- **Risk gate** — drop `medium`/`high` risk contracts (`--max-risk low`)
- **Minted/supply** — see how much supply is left so you don't chase full pools
- **Verdict-aware** — surfaces the catalog's own take (e.g. "free pool exhausted — skip paid")
- **JSON output** — pipe it into another bot or cron (`--json`)

## Usage

```bash
# all active mints
python3 mint_radar.py

# only free (gas-only) mints
python3 mint_radar.py --free

# free + low-risk only (safest)
python3 mint_radar.py --free --max-risk low

# machine-readable
python3 mint_radar.py --json
```

## Data source

Catalog: `https://agentidhub.eth.limo/project-catalog.js` (schema v1). Overridable with `--catalog <url>`.

## Stack

Python 3 (stdlib only — no dependencies).

## Disclaimer

A "free" mint still costs network gas, and every mint carries price/rug risk. This tool reads published catalog data and does not guarantee that a mint will be profitable.