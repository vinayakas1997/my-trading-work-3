"""Chain step 0: make sure the price store holds every ticker the screener is asked to rank.

The ranker ranks a universe (core_starter: 50 stocks) but can only score symbols that have bars in the price store. With
the store holding 8 tickers the "top 10" could never be more than 8. This adds every ranker universe ticker to the
stock-price watchlist and backfills what is missing, then prints what the store holds.

    python scripts/sync_universe.py              # add missing tickers, backfill, wait
    python scripts/sync_universe.py --status     # only print universe vs store
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _headers() -> dict[str, str]:
    key = (ROOT / "secrets" / "vinu_api_key").read_text().strip()
    return {"Authorization": f"Bearer {key}"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--screener", default="http://127.0.0.1:8095")
    ap.add_argument("--stock", default="http://127.0.0.1:8081")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--timeout-min", type=int, default=90)
    a = ap.parse_args()
    h = _headers()

    rankers = requests.get(f"{a.screener}/screener/rankers", headers=h, timeout=60).json()["rankers"]
    universe = sorted({s for r in rankers if r.get("active") for s in r["universe"]})
    held = {t for t in requests.get(f"{a.stock}/stock/watchlist/tickers", headers=h, timeout=60).json()["tickers"]}
    missing = [s for s in universe if s not in held]
    print(f"screener universe {len(universe)} tickers; price store watchlist {len(held)}; missing {len(missing)}")
    if missing:
        print("  missing:", ", ".join(missing))
    if a.status or not missing:
        return 0

    r = requests.post(f"{a.stock}/stock/watchlist/tickers", json={"tickers": missing}, headers=h, timeout=60)
    if r.status_code >= 300:
        print(f"watchlist add failed: HTTP {r.status_code} {r.text[:200]}")
        return 1
    now = set(r.json()["tickers"])
    added = [s for s in missing if s in now]
    print(f"added {len(added)} to the watchlist; not accepted: {', '.join(s for s in missing if s not in now) or 'none'}")

    r = requests.post(f"{a.stock}/stock/backfill/trigger", json={"symbols": added}, headers=h, timeout=60)
    print(f"backfill: HTTP {r.status_code} {r.text[:160]}")
    body = r.json() if r.status_code < 300 else {}
    job = body.get("job_id") or (body.get("summary") or {}).get("job_id")
    deadline = time.time() + a.timeout_min * 60
    while job and time.time() < deadline:
        time.sleep(20)
        st = requests.get(f"{a.stock}/stock/backfill/status/{job}", headers=h, timeout=60).json()
        print(f"  backfill {st.get('status')}  {st.get('summary')}", flush=True)
        if st.get("status") != "running":
            break
    cat = requests.get(f"{a.stock}/stock/catalog", headers=h, timeout=60).json()["data"]
    have = {c["symbol"] for c in cat if c.get("backfill_status") == "complete"}
    print(f"price store now holds {len(have)} complete tickers; universe tickers still without bars: "
          f"{', '.join(s for s in universe if s not in have) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
