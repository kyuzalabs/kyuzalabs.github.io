# Crypto Portfolio Tracker

Tracker portofolio crypto **real-time** — catat asetmu, lihat nilai + untung/rugi live.

**Cara pakai:** buka `index.html` di browser, tambah coin (misal `BTC`) + jumlah + harga beli (opsional). Harga live ditarik dari Binance API.

**Fitur:**
- Harga live per coin (Binance public API)
- Hitung nilai total portofolio (USD + IDR)
- Untung/rugi otomatis kalau harga beli diisi
- Data tersimpan di perangkat (localStorage), tidak hilang saat refresh
- Hapus aset dengan satu klik

**Stack:** HTML · Vanilla JS · Binance API · localStorage — tanpa dependency, bisa di-host gratis (GitHub Pages).