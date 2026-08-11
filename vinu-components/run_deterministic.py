"""Run deterministic pipeline stages (features -> analysis -> strategy -> simulator)
with wall-clock timing per stage. Skips the LLM-heavy news/research stages.

Usage: python run_deterministic.py --ticker AAPL --from-date 2025-07-01 --to-date 2025-12-31
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import run_pipeline as rp

ROOT = Path(__file__).resolve().parent


def timed(name: str, fn):
    t0 = time.perf_counter()
    started = datetime.now(timezone.utc).isoformat()
    try:
        summary = fn()
        status = "ok"
    except Exception as exc:
        summary = None
        status = "error"
        print(f"[{name}] ERROR: {exc}")
    dt = round(time.perf_counter() - t0, 3)
    print(f"[{name}] {status} in {dt}s")
    return {"name": name, "status": status, "duration_sec": dt,
            "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
            "response_summary": summary}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ticker", required=True)
    p.add_argument("--from-date", required=True)
    p.add_argument("--to-date", required=True)
    p.add_argument("--timeframe", default="1d")
    p.add_argument("--features", default="sma_20,rsi_14")
    p.add_argument("--strategy-name", default=None)
    args = p.parse_args()

    ticker = args.ticker.upper()
    from_ts = rp._date_to_epoch(args.from_date)
    to_ts = rp._date_to_epoch(args.to_date)
    feats = [f.strip() for f in args.features.split(",") if f.strip()]

    report = {"run_id": f"deterministic_{ticker}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
              "ticker": ticker, "from_date": args.from_date, "to_date": args.to_date,
              "timeframe": args.timeframe, "steps": []}

    report["steps"].append(timed("features", lambda: rp.step_features(ticker, from_ts, to_ts, feats, timeframe=args.timeframe)))
    report["steps"].append(timed("initial_analysis", lambda: rp.step_initial_analysis(ticker, from_ts, to_ts)))
    report["steps"].append(timed("strategy", lambda: rp.step_strategy(ticker, args.strategy_name, {"strategy_name": args.strategy_name})))
    report["steps"].append(timed("simulator", lambda: rp.step_simulator(ticker, args.from_date, args.to_date, timeframe=args.timeframe)))

    out = ROOT / "logs" / "pipeline_runs" / f"{report['run_id']}.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nReport: {out}")
    for s in report["steps"]:
        dur = s["duration_sec"]
        print(f"{s['name']:20s} {s['status']:6s} {dur:.2f}s")


if __name__ == "__main__":
    main()
