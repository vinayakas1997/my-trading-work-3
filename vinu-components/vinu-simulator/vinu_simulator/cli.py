from __future__ import annotations

import argparse
import json
import logging

from vinu_infra.debug import setup_logging
from vinu_simulator.api import SimulatorAPI
from vinu_simulator.config import load_config
from vinu_simulator.server.app import create_app

LOG = logging.getLogger(__name__)


def serve_main(args: argparse.Namespace) -> None:
    import uvicorn
    config = load_config()
    host = args.host or config.host
    port = args.port or config.port
    uvicorn.run(create_app(), host=host, port=port)


def run_main(args: argparse.Namespace) -> None:
    api = SimulatorAPI()
    try:
        result = api.simulate(
            strategy_name=args.strategy,
            start_date=args.start,
            end_date=args.end,
            initial_capital=args.capital,
            transaction_cost_pct=args.cost,
            slippage_pct=args.slippage,
        )
    except ValueError as e:
        print(f"Error: {e}")
        return

    print(f"\nStrategy: {result['strategy_name']}")
    print(f"Run ID:   {result['run_id']}")
    print(f"Trades:   {result['trade_count']}")
    print(f"\n{'Metric':<20} {'Value':<12}")
    print("-" * 34)
    for key, val in result.get("metrics", {}).items():
        print(f"{key:<20} {val:<12.6f}")

    if result.get("benchmark_metrics"):
        print(f"\n{'Benchmark':<12} {'Total Return':<14} {'CAGR':<14} {'Sharpe':<14} {'Max DD':<14}")
        print("-" * 70)
        for bm, m in result["benchmark_metrics"].items():
            print(f"{bm:<12} {m.get('total_return', 0):<14.4f} {m.get('cagr', 0):<14.4f} {m.get('sharpe_ratio', 0):<14.4f} {m.get('max_drawdown', 0):<14.4f}")

    if args.json:
        print(f"\nFull JSON:\n{json.dumps(result, indent=2, default=str)}")


def list_main(args: argparse.Namespace) -> None:
    api = SimulatorAPI()
    runs = api.list_runs(args.strategy)
    if not runs:
        print("No simulation runs found.")
        return
    print(f"{'Run ID':<40} {'Strategy':<25} {'Total Return':<14} {'Sharpe':<10} {'Max DD':<10}")
    print("-" * 105)
    for r in runs:
        m = r.get("metrics", {})
        print(f"{r['run_id']:<40} {r['strategy_name']:<25} {m.get('total_return', 0):<14.4f} {m.get('sharpe_ratio', 0):<10.4f} {m.get('max_drawdown', 0):<10.4f}")


def metrics_main(args: argparse.Namespace) -> None:
    api = SimulatorAPI()
    result = api.get_result(args.run_id, load_data=False)
    if result is None:
        print(f"Run '{args.run_id}' not found.")
        return
    print(f"\nResults for run: {args.run_id}")
    print(f"Strategy: {result['strategy_name']}")
    print(f"\n{'Metric':<25} {'Value':<14}")
    print("-" * 41)
    metrics = result.get("metrics", {})
    for key, val in sorted(metrics.items()):
        print(f"{key:<25} {val:<14.6f}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="vinu-simulator — Backtesting engine")
    sub = parser.add_subparsers(dest="command", required=True)

    serve_p = sub.add_parser("serve", help="Start HTTP API server")
    serve_p.add_argument("--host", default=None)
    serve_p.add_argument("--port", type=int, default=None)
    serve_p.set_defaults(func=serve_main)

    run_p = sub.add_parser("run", help="Run a backtest simulation")
    run_p.add_argument("strategy", help="Strategy name")
    run_p.add_argument("--start", default=None, help="Start date (YYYY-MM-DD)")
    run_p.add_argument("--end", default=None, help="End date (YYYY-MM-DD)")
    run_p.add_argument("--capital", type=float, default=None, help="Initial capital")
    run_p.add_argument("--cost", type=float, default=None, help="Transaction cost %")
    run_p.add_argument("--slippage", type=float, default=None, help="Slippage %")
    run_p.add_argument("--json", action="store_true", help="Output full JSON")
    run_p.set_defaults(func=run_main)

    list_p = sub.add_parser("list", help="List simulation runs")
    list_p.add_argument("--strategy", default=None, help="Filter by strategy name")
    list_p.set_defaults(func=list_main)

    metrics_p = sub.add_parser("metrics", help="Get metrics for a run")
    metrics_p.add_argument("run_id", help="Run ID")
    metrics_p.set_defaults(func=metrics_main)

    args = parser.parse_args(argv)
    setup_logging("simulator")

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
