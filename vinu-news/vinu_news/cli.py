"""CLI entry points for vinu-news."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time

from vinu_news.config import load_config
from vinu_news.server.app import create_app
from vinu_news.service import NewsService


def _parse_common_db_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        type=str,
        default="",
        help="SQLite database path (overrides VINU_NEWS_DB_PATH)",
    )


def ingest_main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run vinu-news RSS ingestion worker")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Run a single poll cycle")
    mode.add_argument(
        "--continuous",
        action="store_true",
        help="Poll repeatedly using VINU_NEWS_POLL_INTERVAL_SEC from env/.env",
    )
    mode.add_argument(
        "--interval",
        type=int,
        metavar="SECONDS",
        help="Poll repeatedly every N seconds",
    )
    parser.add_argument(
        "--feeds",
        type=str,
        default="",
        help="Comma-separated feed ids (default: all enabled)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Fetch only; skip DB writes")
    parser.add_argument("--verbose", action="store_true")
    _parse_common_db_args(parser)
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.db:
        import os

        os.environ["VINU_NEWS_DB_PATH"] = args.db

    feed_ids = [f.strip() for f in args.feeds.split(",") if f.strip()] or None
    interval = args.interval
    if args.continuous:
        interval = load_config().default_poll_interval_sec

    def run_cycle() -> None:
        with NewsService() as service:
            summary = service.run_ingestion_cycle(
                feed_ids=feed_ids,
                dry_run=args.dry_run,
            )
            print(summary.format_report())

    if args.once or interval is None:
        run_cycle()
        return

    while True:
        run_cycle()
        with NewsService() as service:
            sleep_sec = service.get_settings().poll_interval_sec
        logging.info("Sleeping %s seconds until next poll", sleep_sec)
        time.sleep(sleep_sec)


def serve_main(argv: list[str] | None = None) -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Run vinu-news HTTP API server")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    _parse_common_db_args(parser)
    args = parser.parse_args(argv)

    if args.db:
        import os

        os.environ["VINU_NEWS_DB_PATH"] = args.db

    cfg = load_config()
    host = args.host or cfg.host
    port = args.port or cfg.port
    app = create_app()
    uvicorn.run(app, host=host, port=port)


def query_main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Query vinu-news database from CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    latest = sub.add_parser("latest", help="Latest lead articles")
    latest.add_argument("--limit", type=int, default=20)

    ticker = sub.add_parser("ticker", help="News for one ticker")
    ticker.add_argument("symbol")
    ticker.add_argument("--days", type=int, default=7)
    ticker.add_argument("--limit", type=int, default=50)

    search = sub.add_parser("search", help="Full-text search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=20)

    settings_cmd = sub.add_parser("settings", help="Show or update settings")
    settings_cmd.add_argument("action", choices=["show", "set"])
    settings_cmd.add_argument("key", nargs="?", choices=["mode", "poll_interval_sec"])
    settings_cmd.add_argument("value", nargs="?")

    watch = sub.add_parser("watchlist", help="Show or update watchlist")
    watch.add_argument("action", choices=["show", "add", "remove"])
    watch.add_argument("tickers", nargs="*", help="Ticker symbols")

    _parse_common_db_args(parser)
    args = parser.parse_args(argv)

    if args.db:
        import os

        os.environ["VINU_NEWS_DB_PATH"] = args.db

    with NewsService() as service:
        if args.command == "latest":
            rows = service.get_latest(args.limit)
            print(json.dumps(rows, indent=2))
        elif args.command == "ticker":
            rows = service.get_ticker_news(args.symbol, days=args.days, limit=args.limit)
            print(json.dumps(rows, indent=2))
        elif args.command == "search":
            rows = service.search(args.query, args.limit)
            print(json.dumps(rows, indent=2))
        elif args.command == "settings":
            if args.action == "show":
                print(json.dumps(service.get_settings().to_dict(), indent=2))
            else:
                if args.key == "mode":
                    view = service.patch_settings(mode=args.value)
                elif args.key == "poll_interval_sec":
                    view = service.patch_settings(poll_interval_sec=int(args.value))
                else:
                    parser.error("settings set requires key and value")
                    return
                print(json.dumps(view.to_dict(), indent=2))
        elif args.command == "watchlist":
            if args.action == "show":
                print(json.dumps({"tickers": service.get_watchlist()}, indent=2))
            elif args.action == "add":
                service.add_watchlist_tickers(args.tickers)
                print(json.dumps({"tickers": service.get_watchlist()}, indent=2))
            elif args.action == "remove":
                for symbol in args.tickers:
                    service.remove_watchlist_ticker(symbol)
                print(json.dumps({"tickers": service.get_watchlist()}, indent=2))


if __name__ == "__main__":
    ingest_main(sys.argv[1:])
