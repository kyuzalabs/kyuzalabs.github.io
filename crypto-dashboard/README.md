# Crypto Dashboard

A single-file, zero-dependency **live crypto price dashboard**. Open it in any browser and it pulls real-time prices + 24h change from the Binance public API.

## Why

Fast way to keep an eye on your watchlist without opening an exchange. One HTML file, no backend, no API key, no build step.

## Features

- **Live prices + 24h % change** (green/red)
- **24h high / low** per coin
- **Auto-refresh** every 60s
- **Dark theme**, responsive cards
- **No key, no server** — just open the file

## Usage

1. Download / clone this repo
2. Open `index.html` in any browser
3. Edit the `WATCH` array in the `<script>` to change your coins

```js
const WATCH = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT", "ADAUSDT"];
```

## Data source

Binance public ticker API — `https://api.binance.com/api/v3/ticker/24hr` (no authentication).

## Stack

HTML + CSS + vanilla JS. No frameworks, no dependencies.

---

Alternatively, deploy it free on GitHub Pages: Repo → Settings → Pages → set source to the default branch.