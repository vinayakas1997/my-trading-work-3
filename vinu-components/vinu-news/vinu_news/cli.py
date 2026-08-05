"""CLI entry points for vinu-news."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time

from vinu_infra.debug import setup_logging
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

    setup_logging("news", verbose=args.verbose)

    if args.db:
        import os

        os.environ["VINU_NEWS_DB_PATH"] = args.db

    feed_ids = [f.strip() for f in args.feeds.split(",") if f.strip()] or None
    interval = args.interval
    if args.continuous:
        interval = load_config().default_poll_interval_sec

    def run_rss_cycle() -> None:
        with NewsService() as service:
            service.set_poll_status(last_poll_started_at=int(time.time()))
            summary = service.run_ingestion_cycle(
                feed_ids=feed_ids,
                dry_run=args.dry_run,
            )
            service.set_poll_status(
                last_poll_finished_at=int(time.time()),
                last_raw_count=summary.raw_count,
                last_leads_before_filter=summary.leads_before_filter,
                last_leads_after_filter=summary.leads_after_filter,
                last_inserted=summary.inserted,
            )
            print(summary.format_report())

    def run_ticker_cycle(tickers: list[str] | None = None) -> None:
        with NewsService() as service:
            summary = service.run_ticker_news_ingest(tickers=tickers, dry_run=args.dry_run)
            if tickers is None:
                service.clear_all_pending_ticker_fetch()
            print(summary.format_report())

    if args.once or interval is None:
        run_rss_cycle()
        run_ticker_cycle()
        return

    def sync_and_backfill() -> None:
        with NewsService() as service:
            sync_result = service.sync_watchlist_from_shared()
            if sync_result.get("added"):
                logging.info(
                    "Synced new ticker(s) from shared watchlist: %s",
                    ", ".join(sync_result["added"]),
                )
            backfill_results = service.run_backfill_all()
            if backfill_results:
                logging.info("Ran %d pending backfill(s)", len(backfill_results))

    tick_sec = 2
    while True:
        run_rss_cycle()
        run_ticker_cycle()
        sync_and_backfill()

        elapsed = 0
        while True:
            with NewsService() as service:
                current_interval = service.get_settings().poll_interval_sec
                pending = service.pop_pending_ticker_fetch()
                status = service.get_poll_status()
                if status.last_poll_finished_at is not None:
                    service.set_poll_status(
                        next_poll_at=status.last_poll_finished_at + current_interval
                    )
            if pending:
                logging.info(
                    "New ticker(s) added (%s); fetching news immediately",
                    ", ".join(pending),
                )
                run_ticker_cycle(pending)
                continue
            if elapsed >= current_interval:
                break
            wait = min(tick_sec, current_interval - elapsed)
            time.sleep(wait)
            elapsed += wait
        logging.info("Woke after %ss (poll interval now %ss)", elapsed, current_interval)


def finbert_main(argv: list[str] | None = None) -> None:
    """Independent FinBERT-scoring loop — deliberately a separate process
    from `ingest_main`'s loop, not a step inside it. FinBERT scoring has
    no dependency on LLM analysis, but `ingest_main`'s `NewsService()`
    calls can legitimately block for hours on a real LLM-analysis backlog
    (see AutoAnalysisWorker.shutdown()'s docstring) — running here means
    that never delays FinBERT, and vice versa. Same pattern as
    vinu-research's `schedule-freshness`/`schedule-decay` CLI loops.
    """
    parser = argparse.ArgumentParser(description="Run vinu-news FinBERT backfill worker")
    parser.add_argument(
        "--interval-sec", type=int, default=60,
        help="Seconds to wait between backfill sweeps once caught up (default: 60)",
    )
    parser.add_argument("--once", action="store_true", help="Run a single sweep and exit")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    setup_logging("news-finbert", verbose=args.verbose)

    def run_sweep() -> None:
        with NewsService() as service:
            while True:
                result = service.backfill_finbert_sentiment(limit=500)
                if result["scored"] == 0:
                    break
                logging.info(
                    "[finbert] scored %d articles, %d remaining",
                    result["scored"], result["remaining"],
                )
                if result["remaining"] == 0:
                    break

    if args.once:
        run_sweep()
        return

    while True:
        run_sweep()
        time.sleep(args.interval_sec)


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


def backfill_main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Alpaca historical news backfill")
    parser.add_argument("tickers", nargs="*", help="Ticker symbols to backfill")
    parser.add_argument("--all", action="store_true", help="Backfill all enabled tickers")
    parser.add_argument("--once", action="store_true", help="Run a single backfill pass")
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run in continuous loop polling for new enabled tickers",
    )
    parser.add_argument("--interval", type=int, default=300, help="Poll interval seconds")
    _parse_common_db_args(parser)
    args = parser.parse_args(argv)

    if args.db:
        import os
        os.environ["VINU_NEWS_DB_PATH"] = args.db

    setup_logging("news")

    def run() -> None:
        with NewsService() as service:
            if args.all:
                results = service.run_backfill_all()
            elif args.tickers:
                results = [service.run_backfill_single(t) for t in args.tickers]
            else:
                results = service.run_backfill_all()
            for r in results:
                print(json.dumps(r))

    if args.once or not args.continuous:
        run()
        return

    while True:
        run()
        time.sleep(args.interval)


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

    backfill_llm = sub.add_parser("backfill-analysis", help="Analyze articles missing LLM analysis")
    backfill_llm.add_argument("--limit", type=int, default=500)

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
        elif args.command == "backfill-analysis":
            result = service.backfill_analysis(limit=args.limit)
            print(json.dumps(result, indent=2))


if __name__ == "__main__":
    ingest_main(sys.argv[1:])
