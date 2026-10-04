"""Run the research loop (LLM idea, backtest, refine, validate) for several tickers, one after another, and print the outcome.

This is the system's own route to a tradable strategy: the loop proposes and refines strategies from the analysis, the
promotion bar decides, and only an approved ACTIVE artifact may trade. Nothing here lowers the bar.

    VINU_API_KEY=... python scripts/research_batch.py --tickers AAPL,MSFT,GOOGL,AMZN,META
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date, timedelta

import requests


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="AAPL,MSFT,GOOGL,AMZN,META")
    ap.add_argument("--research-api", default="http://127.0.0.1:8087")
    ap.add_argument("--interval", default=None, help="bar size for these runs (default: the service's own, 1d)")
    ap.add_argument("--years", type=int, default=4)
    a = ap.parse_args()
    headers = {"Authorization": f"Bearer {os.environ['VINU_API_KEY']}"} if os.environ.get("VINU_API_KEY") else {}
    end = date.today().isoformat()
    start = (date.today() - timedelta(days=a.years * 365 + 30)).isoformat()
    rows = []
    for ticker in a.tickers.split(","):
        body = {"symbol": ticker, "from_date": start, "to_date": end, "dry_run": False}
        if a.interval:
            body["interval"] = a.interval
        t0 = time.time()
        try:
            r = requests.post(f"{a.research_api}/research/run", json=body, headers=headers, timeout=3600)
            d = r.json() if r.status_code == 200 else {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
        except Exception as exc:  # noqa: BLE001
            d = {"error": f"{type(exc).__name__}: {exc}"}
        secs = time.time() - t0
        rows.append((ticker, d, secs))
        if "error" in d:
            print(f"{ticker:6} ERROR {d['error']}", flush=True)
            continue
        print(f"{ticker:6} run {d.get('id')}  {d.get('outcome_status')}  iterations {d.get('total_iterations')}  "
              f"sharpe {d.get('best_sharpe')}  deflated {d.get('deflated_sharpe')}  holdout {d.get('holdout_passed')}  "
              f"stress {d.get('stress_test_passed')}  ({secs:.0f}s)", flush=True)
        if d.get("diagnosis"):
            print(f"       {d['diagnosis']}", flush=True)
    print("\nDONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
