from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

from vinu_infra.debug import setup_logging
from vinu_strategy.api import StrategyAPI
from vinu_strategy.config import load_config
from vinu_strategy.server.app import create_app

LOG = logging.getLogger(__name__)

_SCHEDULE_MAP: dict[str, timedelta] = {
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
    "monthly": timedelta(days=30),
}


def serve_main(args: argparse.Namespace) -> None:
    import uvicorn
    config = load_config()
    host = args.host or config.host
    port = args.port or config.port
    uvicorn.run(create_app(), host=host, port=port)


def list_main(args: argparse.Namespace) -> None:
    api = StrategyAPI()
    strategies = api.list_strategies()
    if not strategies:
        print("No strategies registered.")
        return
    print(f"{'Name':<30} {'Schedule':<10} {'Enabled':<8} Description")
    print("-" * 80)
    for s in strategies:
        print(f"{s['name']:<30} {s['schedule']:<10} {'✓' if s['enabled'] else '✗':<8} {s['description']}")


def evaluate_main(args: argparse.Namespace) -> None:
    api = StrategyAPI()
    symbols = args.tickers if args.tickers else None
    try:
        result = api.evaluate(args.strategy, symbols)
    except ValueError as e:
        print(f"Error: {e}")
        return

    print(f"\nStrategy: {result['strategy_name']}")
    print(f"Run ID:   {result['run_id']}")
    print(f"Time:     {result['timestamp']}")
    print(f"\n{'Symbol':<12} {'Weight':<10} {'Signal':<10}")
    print("-" * 36)
    for w in result["weights"]:
        print(f"{w['symbol']:<12} {w['weight']:<10.4f} {w['signal_value']:<10.4f}")

    if args.trace and result.get("rule_trace"):
        print(f"\n{'Rule Trace':^60}")
        print("=" * 60)
        for sym, entries in result["rule_trace"].items():
            print(f"\n{sym}:")
            for e in entries:
                status = "✓" if e["fired"] else "✗"
                print(f"  {status} {e['rule']}")
                for c in e["conditions"]:
                    print(f"    {c['source']}.{c['key']} {c['operator']} {c['expected']} → {c['reason']}")
                if e.get("action"):
                    print(f"    → action: {e['action']['type']}({e['action']['value']}), weight_after={e['weight_after']}")

    if args.json:
        print(f"\nFull JSON:\n{json.dumps(result, indent=2, default=str)}")


def schedule_main(args: argparse.Namespace) -> None:
    api = StrategyAPI()
    strategies = api.list_strategies()
    if not strategies:
        print("No strategies to schedule.")
        return

    intervals: list[tuple[str, timedelta]] = []
    for s in strategies:
        raw = s.get("schedule", "daily")
        interval = _SCHEDULE_MAP.get(raw)
        if interval is None:
            LOG.warning("Unknown schedule '%s' for strategy '%s', using daily", raw, s["name"])
            interval = timedelta(days=1)
        intervals.append((s["name"], interval))

    print(f"Scheduling {len(intervals)} strategies. Press Ctrl+C to stop.\n")
    last_run: dict[str, datetime] = {}

    try:
        while True:
            now = datetime.utcnow()
            for name, interval in intervals:
                last = last_run.get(name)
                if last is None or (now - last) >= interval:
                    print(f"[{now.isoformat()}] Evaluating '{name}'...")
                    try:
                        result = api.evaluate(name)
                        print(f"  ✓ {len(result['weights'])} weights, run_id={result['run_id']}")
                    except Exception as e:
                        print(f"  ✗ Error: {e}")
                    last_run[name] = now
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nScheduler stopped.")


def reload_main(args: argparse.Namespace) -> None:
    config = load_config()
    from vinu_strategy.engine.registry import StrategyRegistry
    registry = StrategyRegistry(config.strategies_dir)
    strategies = registry.load_all()
    print(f"Reloaded {len(strategies)} strategies:")
    for name in sorted(strategies):
        print(f"  - {name}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="vinu-strategy — Decision fusion engine")
    sub = parser.add_subparsers(dest="command", required=True)

    serve_p = sub.add_parser("serve", help="Start HTTP API server")
    serve_p.add_argument("--host", default=None)
    serve_p.add_argument("--port", type=int, default=None)
    serve_p.set_defaults(func=serve_main)

    list_p = sub.add_parser("list", help="List registered strategies")
    list_p.set_defaults(func=list_main)

    eval_p = sub.add_parser("evaluate", help="Evaluate a strategy")
    eval_p.add_argument("strategy", help="Strategy name")
    eval_p.add_argument("tickers", nargs="*", help="Ticker symbols to evaluate")
    eval_p.add_argument("--json", action="store_true", help="Output full JSON")
    eval_p.add_argument("--trace", action="store_true", help="Show rule trace (which rules fired/not-fired)")
    eval_p.set_defaults(func=evaluate_main)

    sched_p = sub.add_parser("schedule", help="Run periodic evaluation scheduler")
    sched_p.set_defaults(func=schedule_main)

    reload_p = sub.add_parser("reload", help="Reload strategy YAML files")
    reload_p.set_defaults(func=reload_main)

    args = parser.parse_args(argv)
    setup_logging("strategy")

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
