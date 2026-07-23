from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from vinu_lib.debug import setup_logging
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
