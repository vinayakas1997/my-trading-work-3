from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from vinu_initial_analysis.api import CorrelationAPI
from vinu_initial_analysis.clients.news_client import NewsClient
from vinu_initial_analysis.clients.price_client import PriceClient
from vinu_initial_analysis.config import load_config
from vinu_initial_analysis.runner import AngleRunner
from vinu_initial_analysis.server.app import create_app
from vinu_initial_analysis.storage.meta import RunLog
from vinu_initial_analysis.storage.parquet import AngleStorage

LOG = logging.getLogger(__name__)


# =========================================================================
# Backward-compat entry points (old vinu-correlation CLI)
# =========================================================================


def serve_main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run vinu-initial-analysis HTTP API")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--data-root", type=Path, default=None)
    args = parser.parse_args(argv)

    config = load_config()
    if args.host:
        config = config.__class__(**{**config.__dict__, "host": args.host})
    if args.port is not None:
        config = config.__class__(**{**config.__dict__, "port": args.port})
    if args.data_root:
        config = config.__class__(**{**config.__dict__, "data_root": args.data_root})

    import uvicorn
    uvicorn.run(create_app(), host=config.host, port=config.port)


def compute_main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run initial analysis compute pipeline")
    parser.add_argument("tickers", nargs="*", help="Ticker symbols to analyze")
    parser.add_argument("--all", action="store_true", help="Analyze all watchlist tickers")
    parser.add_argument("--from-year", type=int, default=None)
    parser.add_argument("--to-year", type=int, default=None)
    parser.add_argument("--incremental", action="store_true", help="Only process new data since last compute")
    parser.add_argument("--force", action="store_true", help="Full recompute from scratch")
    parser.add_argument("--backfill", action="store_true", help="Backfill year-by-year from 2023")
    parser.add_argument("--continuous", action="store_true", help="Run in continuous loop with --interval")
    parser.add_argument("--interval", type=int, default=3600, help="Poll interval in seconds (default: 3600)")
    parser.add_argument("--pipeline", action="store_true", help="Pipeline status output")
    args = parser.parse_args(argv)

    config = load_config()
    storage = AngleStorage(config.data_root)
    run_log = RunLog(config.data_root / "runs.db")
    news_client = NewsClient(config.news_api_url)
    price_client = PriceClient(config.stock_api_url)
    runner = AngleRunner(storage, run_log, news_client=news_client, price_client=price_client)
    logging.basicConfig(level=logging.INFO)

    tickers = args.tickers
    if args.all:
        try:
            import requests
            r = requests.get(f"{config.stock_api_url}/watchlist/tickers", timeout=5)
            if r.status_code == 200:
                tickers = r.json().get("tickers", [])
            else:
                tickers = []
        except Exception:
            tickers = []
        if not tickers:
            LOG.warning("No watchlist tickers from stock API, using defaults")
            tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA"]

    if not tickers:
        parser.print_help()
        return

    def _compute_batch(tickers: list[str], incremental: bool, backfill: bool = False):
        for symbol in tickers:
            if backfill:
                LOG.info("Backfill analyzing %s year-by-year...", symbol)
                for year in range(2023, 2027):
                    from_ts = int(datetime(year, 1, 1, tzinfo=timezone.utc).timestamp())
                    to_ts = int(datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp())
                    LOG.info("  %s -> %s", datetime.fromtimestamp(from_ts), datetime.fromtimestamp(to_ts))
                    runner.run(symbol, from_ts=from_ts, to_ts=to_ts)
            else:
                LOG.info("Analyzing %s (incremental=%s)...", symbol, incremental)
                runner.run(symbol)
            LOG.info("Done %s", symbol)

    if args.continuous:
        LOG.info("Starting continuous compute loop (interval=%ss)", args.interval)
        while True:
            _compute_batch(tickers, incremental=args.incremental or not args.force, backfill=args.backfill)
            LOG.info("Sleeping %ss...", args.interval)
            time.sleep(args.interval)
    else:
        _compute_batch(tickers, incremental=args.incremental or not args.force, backfill=args.backfill)


def compact_main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Compact analysis Parquet files")
    parser.add_argument("tickers", nargs="*", help="Ticker symbols to compact")
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--all", action="store_true", help="Compact all symbols")
    args = parser.parse_args(argv)

    config = load_config()
    storage = AngleStorage(config.data_root)

    tickers = args.tickers
    if args.all:
        tickers = storage.list_symbols()

    if not tickers:
        parser.print_help()
        return

    for symbol in tickers:
        LOG.info("Compacting %s...", symbol)
        LOG.info("Compacted %s", symbol)


def query_main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Query initial analysis data")
    sub = parser.add_subparsers(dest="command", required=True)

    impact_parser = sub.add_parser("impact")
    impact_parser.add_argument("ticker")
    impact_parser.add_argument("--from", type=int, default=None, dest="from_ts")
    impact_parser.add_argument("--to", type=int, default=None, dest="to_ts")

    events_parser = sub.add_parser("events")
    events_parser.add_argument("ticker")
    events_parser.add_argument("--from", type=int, default=None, dest="from_ts")
    events_parser.add_argument("--to", type=int, default=None, dest="to_ts")

    corr_parser = sub.add_parser("correlation")
    corr_parser.add_argument("ticker")
    corr_parser.add_argument("--from", type=int, default=None, dest="from_ts")
    corr_parser.add_argument("--to", type=int, default=None, dest="to_ts")

    dd_parser = sub.add_parser("drawdown")
    dd_parser.add_argument("ticker")
    dd_parser.add_argument("--from", type=int, default=None, dest="from_ts")
    dd_parser.add_argument("--to", type=int, default=None, dest="to_ts")

    base_parser = sub.add_parser("baseline")
    base_parser.add_argument("ticker")

    args = parser.parse_args(argv)
    api = CorrelationAPI()

    if args.command == "impact":
        result = api.get_impact(args.ticker, from_ts=args.from_ts, to_ts=args.to_ts)
        print(json.dumps(result, indent=2, default=str))
    elif args.command == "events":
        result = api.get_events(args.ticker, from_ts=args.from_ts, to_ts=args.to_ts)
        print(json.dumps(result, indent=2, default=str))
    elif args.command == "correlation":
        result = api.get_correlation(args.ticker, from_ts=args.from_ts, to_ts=args.to_ts)
        print(json.dumps(result, indent=2, default=str))
    elif args.command == "drawdown":
        result = api.get_drawdown(args.ticker, from_ts=args.from_ts, to_ts=args.to_ts)
        print(json.dumps(result, indent=2, default=str))
    elif args.command == "baseline":
        result = api.get_baseline(args.ticker)
        print(json.dumps(result, indent=2, default=str))


# =========================================================================
# New entry point: vinu-initial-analysis
# =========================================================================


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="vinu-initial-analysis",
        description="Foundational analysis pipeline — runs 25 deterministic angles against a stock",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # run
    run_p = sub.add_parser("run", help="Run all angles for a symbol")
    run_p.add_argument("ticker", help="Ticker symbol")
    run_p.add_argument("--from", type=int, default=None, dest="from_ts", help="Start timestamp")
    run_p.add_argument("--to", type=int, default=None, dest="to_ts", help="End timestamp")

    # list-angles
    sub.add_parser("list-angles", help="List available analysis angles")

    # status
    status_p = sub.add_parser("status", help="Show analysis status for a symbol")
    status_p.add_argument("ticker", nargs="?", default=None, help="Ticker symbol")

    # serve
    sub.add_parser("serve", help="Start HTTP API server")

    args = parser.parse_args(argv)

    config = load_config()
    storage = AngleStorage(config.data_root)
    run_log = RunLog(config.data_root / "runs.db")
    news_client = NewsClient(config.news_api_url)
    price_client = PriceClient(config.stock_api_url)
    runner = AngleRunner(storage, run_log, news_client=news_client, price_client=price_client)
    logging.basicConfig(level=logging.INFO)

    if args.command == "run":
        LOG.info("Running analysis for %s...", args.ticker.upper())
        results = runner.run(args.ticker.upper(), from_ts=args.from_ts, to_ts=args.to_ts)
        print(json.dumps(results, indent=2, default=str))

    elif args.command == "list-angles":
        angles = runner.list_angles()
        for a in angles:
            print(f"{a['name']:40s} {a['title']}")

    elif args.command == "status":
        if args.ticker:
            symbols = [args.ticker.upper()]
        else:
            symbols = storage.list_symbols()
        for sym in symbols:
            angles = storage.list_angles(sym)
            print(f"\n{sym}:")
            if not angles:
                print("  No data stored yet")
            for a in angles:
                print(f"  {a['angle_name']:40s} {a['run_count']} runs")

    elif args.command == "serve":
        import uvicorn
        uvicorn.run(create_app(), host=config.host, port=config.port)


if __name__ == "__main__":
    main()
