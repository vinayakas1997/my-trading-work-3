"""Send every live-decision strategy (one with must_conditions) through research validation and print the verdicts.

The live loop only lets a strategy open positions after this has passed for its exact current rules, and only on the
tickers that passed. Re-run it after adding or editing a strategy.

    VINU_API_KEY=... python scripts/validate_strategies.py            # start validation for all, wait, print
    VINU_API_KEY=... python scripts/validate_strategies.py --only trend_pullback_long_1h
    VINU_API_KEY=... python scripts/validate_strategies.py --status   # just print the current verdicts
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import requests


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy-api", default="http://127.0.0.1:8084")
    ap.add_argument("--research-api", default="http://127.0.0.1:8087")
    ap.add_argument("--only", default="", help="comma separated strategy names")
    ap.add_argument("--status", action="store_true", help="only print the current verdicts")
    ap.add_argument("--poll-sec", type=int, default=20)
    ap.add_argument("--timeout-min", type=int, default=120)
    a = ap.parse_args()
    headers = {"Authorization": f"Bearer {os.environ['VINU_API_KEY']}"} if os.environ.get("VINU_API_KEY") else {}

    def verdicts() -> list[dict]:
        return requests.get(f"{a.research_api}/research/strategy-validations", headers=headers, timeout=60).json()["validations"]

    if not a.status:
        wanted = {n for n in a.only.split(",") if n}
        names = [s["name"] if isinstance(s, dict) else s
                 for s in requests.get(f"{a.strategy_api}/strategy/strategies", headers=headers, timeout=60).json()]
        started = []
        for name in names:
            if wanted and name not in wanted:
                continue
            cfg = requests.get(f"{a.strategy_api}/strategy/strategies/{name}", headers=headers, timeout=60).json()
            if not cfg.get("must_conditions"):
                continue                                              # an allocation-pipeline strategy: no triggers to test
            body = {"name": name, "schedule": cfg.get("schedule"), "universe": cfg.get("universe", []),
                    "must_conditions": cfg["must_conditions"],
                    "live_decision_max_hold_bars": cfg.get("live_decision_max_hold_bars", 0)}
            r = requests.post(f"{a.research_api}/research/strategy-validations", json=body, headers=headers, timeout=60)
            print(f"started {name}: HTTP {r.status_code}")
            started.append(name)
        deadline = time.time() + a.timeout_min * 60
        while started and time.time() < deadline:
            time.sleep(a.poll_sec)
            by = {v["strategy_id"]: v for v in verdicts()}
            pending = [n for n in started if by.get(n, {}).get("status") in (None, "running")]
            print(f"  waiting on {len(pending)} of {len(started)}: {', '.join(pending) or '-'}")
            if not pending:
                break

    print(f"\n{'strategy':28}{'bar':5}{'status':15}{'passed':>8}  tickers that passed")
    for v in verdicts():
        d = v.get("detail", {})
        share = d.get("pass_share")
        print(f"{v['strategy_id']:28}{(v.get('interval') or '-'):5}{v['status']:15}{('-' if share is None else f'{share:.0%}'):>8}  "
              f"{', '.join(d.get('eligible_tickers', [])) or '-'}")
        for t, td in (d.get("per_ticker") or {}).items():
            if not td.get("eligible"):
                at = td.get("attempt") or {}
                nums = (f"Sharpe {at['sharpe']:.2f}, maxDD {at['max_drawdown_pct']:.0f}%, win {at['win_rate_pct']}%  "
                        if "sharpe" in at else "")
                print(f"{'':28}   {t}: {nums}{(td.get('reasons') or ['?'])[0][:90]}")
        for r in d.get("reasons", []):
            print(f"{'':28}   {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
