from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

import pandas as pd

from vinu_infra.debug import setup_logging
from vinu_portfolio.config import load_config
from vinu_portfolio.service import PortfolioService


def serve_main(args: argparse.Namespace) -> None:
    import uvicorn
    from vinu_portfolio.server.app import create_app

    config = load_config()
    host = args.host or config.host
    port = args.port or config.port
    uvicorn.run(create_app(), host=host, port=port)


def build_main(args: argparse.Namespace) -> None:
    async def _run() -> None:
        async with PortfolioService() as svc:
            portfolio = await svc.build_portfolio()
            print(json.dumps(portfolio, indent=2, default=str))
    asyncio.run(_run())


def daily_allocation_main(args: argparse.Namespace) -> None:
    async def _run() -> None:
        async with PortfolioService() as svc:
            allocation = await svc.compute_daily_allocation()
            print(json.dumps(allocation, indent=2, default=str))
    asyncio.run(_run())


def daily_game_plan_main(args: argparse.Namespace) -> None:
    async def _run() -> None:
        async with PortfolioService() as svc:
            plan = await svc.compute_daily_game_plan()
            print(json.dumps(plan, indent=2, default=str))
    asyncio.run(_run())


def risk_status_main(args: argparse.Namespace) -> None:
    async def _run() -> None:
        async with PortfolioService() as svc:
            status = await svc.compute_risk_status()
            print(json.dumps(status, indent=2, default=str))
    asyncio.run(_run())


def historical_simulate_main(args: argparse.Namespace) -> None:
    async def _run() -> None:
        from vinu_portfolio.historical_simulation import (
            fetch_benchmark_returns,
            fetch_historical_returns,
            run_historical_simulation,
        )

        async with PortfolioService() as svc:
            strategies = await svc.list_active_strategies()
            if not strategies:
                print(json.dumps({"status": "empty", "error": "no active strategies"}, indent=2))
                return
            # This simulator replays price-history returns per underlying
            # symbol as a proxy for each strategy's own returns -- a
            # simplification vs. the live pipeline's _fetch_strategy_returns
            # (which uses the strategy's actual historical weights/positions).
            # Documented scope decision: see historical_simulation.py's
            # docstring and 07-validation.md.
            symbols = sorted({s.get("symbol", "") for s in strategies if s.get("symbol")})
            symbol_returns = await fetch_historical_returns(svc, symbols, days=args.days)
            benchmark_returns = await fetch_benchmark_returns(svc, days=args.days)
            returns_df = pd.DataFrame({
                s["name"]: symbol_returns[s["symbol"]]
                for s in strategies
                if s.get("symbol") in symbol_returns.columns
            }) if not symbol_returns.empty else symbol_returns
            if returns_df.empty or benchmark_returns.empty:
                print(json.dumps({
                    "status": "empty",
                    "error": (
                        "no historical price data available from vinu-stock-price "
                        "for the requested symbols/benchmark -- this data must be "
                        "backfilled before a simulation can run"
                    ),
                }, indent=2))
                return
            usable_strategies = [s for s in strategies if s["name"] in returns_df.columns]
            result = run_historical_simulation(usable_strategies, returns_df, benchmark_returns, svc)
            print(json.dumps(result.to_dict(), indent=2, default=str))
    asyncio.run(_run())


def monitor_main(args: argparse.Namespace) -> None:
    from vinu_portfolio.drawdown_scheduler import monitor_main_loop

    config = load_config()
    monitor_main_loop(config)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="vinu-portfolio")
    sub = parser.add_subparsers(dest="command", required=True)

    serve_p = sub.add_parser("serve", help="Start HTTP API server")
    serve_p.add_argument("--host", default=None)
    serve_p.add_argument("--port", type=int, default=None)
    serve_p.set_defaults(func=serve_main)

    build_p = sub.add_parser("build", help="Build and print portfolio weights")
    build_p.set_defaults(func=build_main)

    daily_allocation_p = sub.add_parser(
        "daily-allocation",
        help="Build regime-aware, outcome-confidence-weighted daily allocation (one-shot)",
    )
    daily_allocation_p.set_defaults(func=daily_allocation_main)

    game_plan_p = sub.add_parser(
        "daily-game-plan",
        help="Build unified daily game plan document with readiness score (one-shot)",
    )
    game_plan_p.set_defaults(func=daily_game_plan_main)

    risk_p = sub.add_parser(
        "risk-status",
        help="Check daily risk budget and regime-tightened bands (one-shot)",
    )
    risk_p.set_defaults(func=risk_status_main)

    sim_p = sub.add_parser(
        "historical-simulate",
        help="Walk-forward daily-rebalance simulation of risk-parity + regime tilt vs. baselines",
    )
    sim_p.add_argument("--days", type=int, default=730, help="Lookback window in calendar days")
    sim_p.set_defaults(func=historical_simulate_main)

    monitor_p = sub.add_parser("monitor", help="Run drawdown-monitor loop, halting trading on breach")
    monitor_p.set_defaults(func=monitor_main)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    setup_logging("portfolio")
    if hasattr(args, "func"):
        args.func(args)
    else:
        _parse_args(["--help"])


if __name__ == "__main__":
    main()
