"""CLI entry points for vinu-stock-price."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time

from vinu_stock.config import load_config
from vinu_stock.server.app import create_app
from vinu_stock.service import StockService


def _parse_data_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--data-root",
        type=str,
        default="",
        help="Override VINU_STOCK_DATA_ROOT",
    )
    parser.add_argument(
        "--meta-db",
        type=str,
        default="",
        help="Override VINU_STOCK_META_DB_PATH",
    )


def _apply_env_overrides(args: argparse.Namespace) -> None:
    import os

    if args.data_root:
        os.environ["VINU_STOCK_DATA_ROOT"] = args.data_root
    if getattr(args, "meta_db", None) and args.meta_db:
        os.environ["VINU_STOCK_META_DB_PATH"] = args.meta_db


def backfill_main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Backfill historical 1m OHLCV to Parquet")
    parser.add_argument("symbols", nargs="*", help="Symbols (default: watchlist)")
    parser.add_argument("--from-year", type=int, default=None, help="Start year (default: auto)")
    parser.add_argument("--to-year", type=int, default=None, help="End year (default: last complete year)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without writing data")
    parser.add_argument("--verbose", action="store_true")
    _parse_data_args(parser)
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    _apply_env_overrides(args)

    with StockService() as service:
        result = service.run_backfill(
            args.symbols or None,
            from_year=args.from_year,
            to_year=args.to_year,
            dry_run=args.dry_run,
        )
        print(result.format_report())


def ingest_main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run live 1m bar ingest worker")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--continuous", action="store_true")
    mode.add_argument("--interval", type=int, metavar="SECONDS")
    parser.add_argument("--verbose", action="store_true")
    _parse_data_args(parser)
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    _apply_env_overrides(args)

    interval = args.interval
    if args.continuous:
        interval = load_config().default_poll_interval_sec

    def run_cycle() -> None:
        with StockService() as service:
            print(service.run_live_cycle().format_report())

    def sync_and_backfill() -> None:
        with StockService() as service:
            sync_result = service.sync_watchlist_from_shared()
            if sync_result.get("added"):
                logging.info(
                    "Synced new ticker(s) from shared watchlist: %s",
                    ", ".join(sync_result["added"]),
                )
            pending = service.get_pending_backfill_symbols()
            if pending:
                logging.info("Running backfill for pending symbol(s): %s", ", ".join(pending))
                result = service.run_backfill(pending)
                print(result.format_report())

    if args.once or interval is None:
        run_cycle()
        return

    while True:
        sync_and_backfill()
        run_cycle()
        with StockService() as service:
            sleep_sec = service.get_settings().poll_interval_sec
        logging.info("Sleeping %s seconds until next ingest", sleep_sec)
        time.sleep(sleep_sec)


def serve_main(argv: list[str] | None = None) -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Run vinu-stock-price HTTP API")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    _parse_data_args(parser)
    args = parser.parse_args(argv)
    _apply_env_overrides(args)

    cfg = load_config()
    host = args.host or cfg.host
    port = args.port or cfg.port
    app = create_app()
    uvicorn.run(app, host=host, port=port)


def query_main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Query stored OHLCV")
    sub = parser.add_subparsers(dest="command", required=True)

    candles_p = sub.add_parser("candles", help="Fetch candles for a symbol")
    candles_p.add_argument("symbol")
    candles_p.add_argument("--interval", default="1m")
    candles_p.add_argument("--days", type=int, default=7)
    candles_p.add_argument("--limit", type=int, default=100)
    candles_p.add_argument("--indicators", default=None, help="e.g. rsi_14,sma_20")
    candles_p.add_argument("--adjusted", action="store_true")
    _parse_data_args(candles_p)

    catalog_p = sub.add_parser("catalog", help="List symbol catalog")
    _parse_data_args(catalog_p)

    wl_add = sub.add_parser("watchlist", help="Add tickers to watchlist")
    wl_add.add_argument("tickers", nargs="+")
    _parse_data_args(wl_add)

    args = parser.parse_args(argv)
    _apply_env_overrides(args)

    with StockService() as service:
        if args.command == "candles":
            from vinu_stock.query.indicators import parse_indicator_names

            indicator_list = None
            if args.indicators:
                indicator_list = parse_indicator_names(args.indicators)
            rows = service.get_candles(
                args.symbol,
                interval=args.interval,
                days=args.days,
                limit=args.limit,
                indicators=indicator_list,
                adjusted=args.adjusted,
            )
            print(json.dumps(rows, indent=2))
        elif args.command == "catalog":
            print(json.dumps(service.get_catalog(), indent=2))
        elif args.command == "watchlist":
            added = service.add_watchlist_tickers(args.tickers)
            print(json.dumps({"added": added, "watchlist": service.get_watchlist()}, indent=2))
        else:
            parser.print_help()
            sys.exit(1)


if __name__ == "__main__":
    ingest_main()
