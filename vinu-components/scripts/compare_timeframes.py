"""Backtest the same setup on several bar sizes through the real simulator, to see which timeframe suits it.

The setup is trend_pullback_long's must-conditions: close above its 50-bar average, below its 5-bar average (the pullback),
ADX(14) above 20. After each setup bar the position is held for HOLD bars (long only, weight 1). The live strategy also
has a stop and an RSI confirmation; they are NOT modelled here, so read this as "does the setup carry any edge on this
bar size", not as a replica of the live rules.

    python scripts/compare_timeframes.py --symbols AAPL,MSFT,GOOGL,AMZN,META --from 2022-01-03 --to 2026-10-02
Needs the stack up and VINU_API_KEY in the environment.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor

import requests

CODE = '''
import numpy as np
import pandas as pd
from vinu_simulator.engine.strategies import BaseStrategy


class PullbackSetup(BaseStrategy):
    HOLD = {hold}

    def generate_weights(self, data):
        close, high, low = data["close"], data["high"], data["low"]
        sma5, sma50 = close.rolling(5).mean(), close.rolling(50).mean()
        up, down = high.diff(), -low.diff()
        plus = np.where((up > down) & (up > 0), up, 0.0)
        minus = np.where((down > up) & (down > 0), down, 0.0)
        tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
        pdi = 100 * pd.Series(plus, index=close.index).ewm(alpha=1 / 14, adjust=False).mean() / atr
        mdi = 100 * pd.Series(minus, index=close.index).ewm(alpha=1 / 14, adjust=False).mean() / atr
        adx = (100 * (pdi - mdi).abs() / (pdi + mdi)).ewm(alpha=1 / 14, adjust=False).mean()
        setup = ((close > sma50) & (close < sma5) & (adx > 20)).astype(float)
        return setup.shift(1).rolling(self.HOLD).max().fillna(0.0)
'''


def run_one(base: str, headers: dict, symbol: str, interval: str, start: str, end: str, hold: int,
            costs: dict | None = None) -> dict:
    body = {"symbols": [symbol], "strategy_code": CODE.format(hold=hold), "class_name": "PullbackSetup",
            "start_date": start, "end_date": end, "interval": interval, **(costs or {})}
    try:
        r = requests.post(f"{base}/simulator/simulate/custom", json=body, headers=headers, timeout=900)
        if r.status_code != 200:
            return {"symbol": symbol, "interval": interval, "error": f"HTTP {r.status_code}: {r.text[:160]}"}
        d = r.json()
        m = d.get("metrics", {})
        return {"symbol": symbol, "interval": interval, "trades": d.get("trade_count"), "sharpe": m.get("sharpe_ratio"),
                "total_return": m.get("total_return"), "max_drawdown": m.get("max_drawdown"), "win_rate": m.get("win_rate"),
                "profit_factor": m.get("profit_factor")}
    except Exception as exc:  # noqa: BLE001
        return {"symbol": symbol, "interval": interval, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="AAPL,MSFT,GOOGL,AMZN,META")
    ap.add_argument("--intervals", default="15m,1h,4h,1d")
    ap.add_argument("--from", dest="start", default="2022-01-03")
    ap.add_argument("--to", dest="end", default="2026-10-02")
    ap.add_argument("--hold", type=int, default=20)
    ap.add_argument("--base", default="http://127.0.0.1:8084")
    ap.add_argument("--out", default="logs/timeframe_comparison.json")
    ap.add_argument("--cost-pct", type=float, default=None, help="override commission per trade (0.001 = 0.1%%); the simulator default is 0.1%%")
    ap.add_argument("--slippage-pct", type=float, default=None, help="override slippage per trade (the default is 0.05%%)")
    a = ap.parse_args()
    headers = {"Authorization": f"Bearer {os.environ['VINU_API_KEY']}"} if os.environ.get("VINU_API_KEY") else {}
    costs = {}
    if a.cost_pct is not None or a.slippage_pct is not None:
        costs = {"transaction_cost_pct": a.cost_pct or 0.0, "slippage_pct": a.slippage_pct or 0.0, "slippage_model": "flat"}
    jobs = [(s, i) for i in a.intervals.split(",") for s in a.symbols.split(",")]
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(lambda j: run_one(a.base, headers, j[0], j[1], a.start, a.end, a.hold, costs), jobs))
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)
    print(f"{'bar':5}{'symbol':8}{'trades':>7}{'sharpe':>8}{'return':>9}{'maxDD':>8}{'win%':>6}{'PF':>6}")
    for r in rows:
        if "error" in r:
            print(f"{r['interval']:5}{r['symbol']:8} ERROR {r['error']}")
            continue
        f = lambda v, p=2: "-" if v is None else f"{v:.{p}f}"
        print(f"{r['interval']:5}{r['symbol']:8}{r['trades'] or 0:>7}{f(r['sharpe']):>8}{f(r['total_return'],3):>9}{f(r['max_drawdown'],3):>8}"
              f"{f((r['win_rate'] or 0)*100,0):>6}{f(r['profit_factor']):>6}")
    print("\nper bar size (mean over symbols):")
    for iv in a.intervals.split(","):
        ok = [r for r in rows if r["interval"] == iv and "error" not in r and r["sharpe"] is not None]
        if ok:
            print(f"  {iv:4} sharpe {statistics.mean(r['sharpe'] for r in ok):6.2f}   return {statistics.mean(r['total_return'] for r in ok):7.3f}   "
                  f"maxDD {statistics.mean(r['max_drawdown'] for r in ok):7.3f}   trades {statistics.mean((r['trades'] or 0) for r in ok):8.0f}   ({len(ok)} symbols)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
