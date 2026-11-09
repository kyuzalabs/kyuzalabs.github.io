#!/usr/bin/env python3
"""
Mint Radar — scan the Agent ID project catalog for free & low-risk active mints.

Data source: https://agentidhub.eth.limo/project-catalog.js
(Generated from content/projects.json; ~1000 projects with on-chain status.)

Usage:
    python3 mint_radar.py                 # all active mints
    python3 mint_radar.py --free          # only free (gas-only) mints
    python3 mint_radar.py --max-risk low  # exclude medium/high risk
    python3 mint_radar.py --json          # machine-readable output
"""

import argparse
import json
import urllib.request

CATALOG_URL = "https://agentidhub.eth.limo/project-catalog.js"
LANG = "en"


def load(catalog_url: str = CATALOG_URL) -> dict:
    req = urllib.request.Request(catalog_url, headers={"User-Agent": "mint-radar/1.0"})
    raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    start = raw.index("{")                  # strip the JS wrapper around the JSON
    end = raw.rindex("}")
    return json.loads(raw[start:end + 1])


def pick(obj, key):
    """Prefer the chosen language (LANG), fall back to zh / raw."""
    v = obj.get(key)
    if isinstance(v, dict):
        return v.get(LANG) or v.get("zh") or json.dumps(v, ensure_ascii=False)
    return v


def is_free(cost_text: str) -> bool:
    c = (cost_text or "").lower()
    return "free" in c or "免费" in c or "gas" in c


def scan(catalog: dict, free_only=False, max_risk=None):
    rows = []
    for p in catalog.get("projects", []):
        v = p.get("verdict") or {}
        phase = v.get("phase")
        if phase != "active":
            continue

        risk = v.get("risk")
        if max_risk:
            order = {"low": 0, "medium": 1, "high": 2}
            if order.get(risk, 2) > order.get(max_risk, 2):
                continue

        cost = pick(v, "cost") or ""
        if free_only and not is_free(cost):
            continue

        mp = p.get("mintProgress") or {}
        minted = mp.get("minted") if mp.get("minted") is not None else "?"
        supply = mp.get("supply") if mp.get("supply") is not None else "?"

        rows.append({
            "name": p.get("name"),
            "category": p.get("category"),
            "risk": risk,
            "cost": cost,
            "deadline": v.get("deadline"),
            "minted": f"{minted}/{supply}" if supply != "?" else "n/a",
            "score": v.get("score"),
            "take": pick(v, "ourTake") or "",
        })

    # low risk first, then higher score
    order = {"low": 0, "medium": 1, "high": 2}
    rows.sort(key=lambda r: (order.get(r["risk"], 2), -(r["score"] or 0)))
    return rows


def main():
    ap = argparse.ArgumentParser(description="Scan the Agent ID catalog for mints.")
    ap.add_argument("--free", action="store_true", help="only free / gas-only mints")
    ap.add_argument("--max-risk", choices=["low", "medium", "high"],
                    help="exclude mints riskier than this")
    ap.add_argument("--json", action="store_true", help="print JSON instead of a table")
    ap.add_argument("--catalog", default=CATALOG_URL, help="catalog URL/override")
    args = ap.parse_args()

    catalog = load(args.catalog)
    rows = scan(catalog, free_only=args.free, max_risk=args.max_risk)

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    print(f"Mint Radar — {len(rows)} active mint(s)"
          + (" (free only)" if args.free else "")
          + (f", max-risk={args.max_risk}" if args.max_risk else ""))
    print("-" * 100)
    for r in rows:
        deadline = (r["deadline"] or "n/a")[:10]
        print(f"[{r['risk'].upper():<6}] {r['name']}")
        print(f"    cost: {r['cost']}")
        print(f"    minted: {r['minted']}  deadline: {deadline}  score: {r['score']}")
        if r["take"]:
            print(f"    take: {r['take'][:160]}")
        print()


if __name__ == "__main__":
    main()