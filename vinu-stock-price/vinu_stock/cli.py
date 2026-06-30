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

    if args.once or interval is None:
        run_cycle()
        return

    while True:
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
            rows = service.get_candles(
                args.symbol,
                interval=args.interval,
                days=args.days,
                limit=args.limit,
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
