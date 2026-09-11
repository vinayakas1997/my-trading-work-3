"""`vinu-screener` entrypoint (`[project.scripts]` in pyproject.toml).
Two subcommands, deliberately separate processes -- same split
`vinu-portfolio`'s `serve`/`monitor` CLI already uses: `serve` runs the
HTTP API (rule CRUD, dry-run, pairlist); `scan` runs the polling loop.
Bundling both into one process would mean a hung scan cycle could starve
the API's event loop, or vice versa -- two small single-purpose processes
instead of one that does both badly.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from vinu_infra.debug import setup_logging


def serve_main(args: argparse.Namespace) -> None:
    import uvicorn

    from vinu_screener.server.app import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port)


def scan_main(args: argparse.Namespace) -> None:
    import httpx

    from vinu_screener.audit.watch_history import WatchAuditStore
    from vinu_screener.rules.store import RuleStore
    from vinu_screener.scan.data_source import HttpStockDataSource
    from vinu_screener.scan.monitor import ScanMonitor
    from vinu_screener.scheduler import Scheduler
    from vinu_screener.server.app import (
        DEFAULT_AUDIT_DB_PATH,
        DEFAULT_RULE_DB_PATH,
        DEFAULT_STOCK_API_URL,
    )

    rule_store = RuleStore(args.rule_db or DEFAULT_RULE_DB_PATH)
    audit_store = WatchAuditStore(args.audit_db or DEFAULT_AUDIT_DB_PATH)
    data_source = HttpStockDataSource(httpx.Client(), base_url=args.stock_api_url or DEFAULT_STOCK_API_URL)
    monitor = ScanMonitor(data_source)
    scheduler = Scheduler(rule_store, monitor, audit_store=audit_store)
    scheduler.run_forever(poll_sec=args.poll_sec)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="vinu-screener")
    sub = parser.add_subparsers(dest="command", required=True)

    serve_p = sub.add_parser("serve", help="Start the HTTP API (rule CRUD, dry-run, pairlist)")
    serve_p.add_argument("--host", default=os.environ.get("VINU_SCREENER_HOST", "0.0.0.0"))
    serve_p.add_argument("--port", type=int, default=int(os.environ.get("VINU_SCREENER_PORT", "8095")))
    serve_p.set_defaults(func=serve_main)

    scan_p = sub.add_parser("scan", help="Run the polling loop against every active rule")
    scan_p.add_argument("--poll-sec", type=float, default=5.0, help="How often to check for due rules")
    scan_p.add_argument("--rule-db", type=Path, default=None)
    scan_p.add_argument("--audit-db", type=Path, default=None)
    scan_p.add_argument("--stock-api-url", default=None)
    scan_p.set_defaults(func=scan_main)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    setup_logging("screener")
    args.func(args)


if __name__ == "__main__":
    main()
