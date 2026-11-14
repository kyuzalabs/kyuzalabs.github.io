"""Kyuza Shop - crypto payment module (stdlib only).

Mendukung USDC (Polygon) dan USDT (BSC). Menggunakan urllib + json untuk
polling event Transfer token via JSON-RPC publik. Tidak butuh dependency
eksternal selain Python standard library.
"""

import json
import os
import urllib.request

SUPPORTED_TOKENS = ["USDC", "USDT"]

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
PLACEHOLDER_ADDRESS = "0x0000000000000000000000000000000000000000"
DEFAULT_IDR_RATE = 16000

TOKENS = {
    "USDC": {
        "network": "polygon",
        "contract": "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359",
        "decimals": 6,
        "rpc": "https://polygon-rpc.com",
    },
    "USDT": {
        "network": "bsc",
        "contract": "0x55d398326f99059ff775485246999027b3197955",
        "decimals": 18,
        "rpc": "https://bsc-dataseed.binance.org",
    },
}

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "payments_config.json"
)


def _load_config():
    """Baca payments_config.json. Kembalikan dict kosong jika gagal."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _pad_address(address):
    """Pad alamat jadi 64 hex char (32 byte) tanpa prefix '0x' di hasil."""
    hex_addr = str(address).strip().lower()
    if hex_addr.startswith("0x"):
        hex_addr = hex_addr[2:]
    return "0x" + hex_addr.zfill(64)


def _rpc_call(rpc_url, method, params, timeout=20):
    """POST JSON-RPC via urllib (stdlib)."""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        rpc_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_quote(total_idr, symbol):
    """Hitung jumlah crypto yang harus dibayar untuk total_idr rupiah."""
    token = TOKENS[symbol]
    config = _load_config()

    idr_rate = int(config.get("idr_rate", DEFAULT_IDR_RATE))
    wallet_address = str(config.get("wallet_address", "")).strip()

    result = {
        "symbol": symbol,
        "network": token["network"],
        "contract": token["contract"],
        "decimals": token["decimals"],
        "amount": round(total_idr / idr_rate, 6),
        "deposit_address": wallet_address,
        "idr_rate": idr_rate,
    }

    if not wallet_address or wallet_address == PLACEHOLDER_ADDRESS:
        result["deposit_address"] = PLACEHOLDER_ADDRESS
        result["warning"] = (
            "Deposit address belum diset. Ganti wallet_address di "
            "payments_config.json dengan alamat wallet admin sebelum go-live."
        )

    return result


def check_payment(symbol, expected_amount, since_timestamp=0):
    """Poll event Transfer menuju deposit_address sejak since_timestamp.

    since_timestamp diterima untuk kompatibilitas interface, tetapi
    from_block memakai '0x0' agar aman (menyapu seluruh histori log).
    paid True hanya jika total transfer >= expected_amount * 0.98.
    """
    token = TOKENS[symbol]
    config = _load_config()

    wallet_address = str(config.get("wallet_address", "")).strip()
    if not wallet_address or wallet_address == PLACEHOLDER_ADDRESS:
        wallet_address = PLACEHOLDER_ADDRESS

    padded = _pad_address(wallet_address)
    topics = [TRANSFER_TOPIC, None, padded]
    params = [
        {
            "fromBlock": "0x0",
            "toBlock": "latest",
            "address": token["contract"],
            "topics": topics,
        }
    ]

    try:
        resp = _rpc_call(token["rpc"], "eth_getLogs", params)
        logs = resp.get("result", []) or []
    except Exception as exc:
        return {
            "paid": False,
            "tx_hash": None,
            "received": 0.0,
            "suggested": "RPC error: {}".format(exc),
        }

    received = 0.0
    tx_hash = None
    for log in logs:
        data = log.get("data", "0x")
        try:
            raw = int(data, 16)
            received += raw / (10 ** token["decimals"])
            if tx_hash is None:
                tx_hash = log.get("transactionHash")
        except Exception:
            continue

    paid = received >= expected_amount * 0.98
    return {
        "paid": paid,
        "tx_hash": tx_hash,
        "received": received,
        "suggested": None,
    }


if __name__ == "__main__":
    print(get_quote(320000, "USDC"))
    print(check_payment("USDC", 20.0))