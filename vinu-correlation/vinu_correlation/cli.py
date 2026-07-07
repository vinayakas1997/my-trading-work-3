from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from vinu_correlation.api import CorrelationAPI
from vinu_correlation.config import load_config
from vinu_correlation.server.app import create_app

LOG = logging.getLogger(__name__)


def serve_main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run vinu-correlation HTTP API")
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
    parser = argparse.ArgumentParser(description="Compute correlation data")
    parser.add_argument("tickers", nargs="*", help="Ticker symbols to compute")
    parser.add_argument("--all", action="store_true", help="Compute all watchlist tickers")
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
    api = CorrelationAPI(config)
    logging.basicConfig(level=logging.INFO)

    tickers = args.tickers
    if args.all:
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA"]

    if not tickers:
        parser.print_help()
        return

    def _compute_batch(tickers: list[str], incremental: bool, backfill: bool = False):
        for symbol in tickers:
            if backfill:
                LOG.info("Backfill computing %s year-by-year...", symbol)
                for year in range(2023, 2027):
                    from_ts = int(datetime(year, 1, 1, tzinfo=timezone.utc).timestamp())
                    to_ts = int(datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp())
                    LOG.info("  %s -> %s", datetime.fromtimestamp(from_ts), datetime.fromtimestamp(to_ts))
                    api.compute_and_store(symbol, incremental=False, from_ts=from_ts, to_ts=to_ts)
            else:
                LOG.info("Computing %s (incremental=%s)...", symbol, incremental)
                api.compute_and_store(symbol, incremental=incremental)
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
    parser = argparse.ArgumentParser(description="Compact correlation Parquet files")
    parser.add_argument("tickers", nargs="*", help="Ticker symbols to compact")
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--all", action="store_true", help="Compact all symbols")
    args = parser.parse_args(argv)

    config = load_config()
    from vinu_correlation.storage.backend import CorrelationStorage
    storage = CorrelationStorage(config.data_root)

    tickers = args.tickers
    if args.all:
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA"]

    if not tickers:
        parser.print_help()
        return

    year = args.year or 2026
    for symbol in tickers:
        LOG.info("Compacting %s (year=%s)...", symbol, year)
        storage.compact(symbol, year)
        LOG.info("Compacted %s", symbol)


def query_main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Query correlation data")
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
    import json
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
