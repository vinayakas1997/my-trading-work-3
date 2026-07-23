from __future__ import annotations

import argparse
import asyncio
import logging
import time

from vinu_lib.debug import setup_logging
from vinu_live.config import load_config
from vinu_live.scheduler import LiveScheduler


def serve_main(args: argparse.Namespace) -> None:
    import uvicorn
    from vinu_live.server.app import create_app

    config = load_config()
    host = args.host or config.host
    port = args.port or config.port
    uvicorn.run(create_app(), host=host, port=port)


def run_cycle_main(args: argparse.Namespace) -> None:
    async def _run() -> None:
        config = load_config()
        scheduler = LiveScheduler(config)
        try:
            result = await scheduler.cycle()
            print(f"Cycle complete: status={result.get('status')}")
            if result.get("n_instructions"):
                print(f"  Instructions: {result['n_instructions']}")
            if result.get("submitted"):
                print(f"  Orders submitted: {len(result['submitted'])}")
        finally:
            await scheduler.close()
    asyncio.run(_run())


def resolve_worker_interval(args: argparse.Namespace | None, config) -> int:
    """Shared by both worker_main's call paths — see worker_main's docstring
    for why args can legitimately be None here."""
    if args is None:
        parser = argparse.ArgumentParser(description="vinu-live-worker")
        parser.add_argument("--interval", type=int, dest="interval_sec", default=None)
        args = parser.parse_args()
    return args.interval_sec if args and args.interval_sec else config.worker_interval_sec


def worker_main(args: argparse.Namespace | None = None) -> None:
    """Continuous worker following the repo's `while True: cycle(); sleep()` pattern.

    Doubles as the `vinu-live-worker` console-script entry point (see
    pyproject.toml), which pip's generated wrapper calls with zero arguments —
    args is always None on that path, so sys.argv has to be parsed here
    directly, or a `--interval` passed on that command line is silently
    dropped in favor of config/env defaults. Previously it was.
    """
    config = load_config()
    interval = resolve_worker_interval(args, config)
    print(f"[worker] Starting vinu-live worker (interval={interval}s)")
    print(f"[worker] Press Ctrl+C to stop.\n")

    async def _worker_loop() -> None:
        scheduler = LiveScheduler(config)
        try:
            while True:
                result = await scheduler.cycle()
                status = result.get("status", "unknown")
                print(f"[worker] Cycle {result.get('cycle_id', '?')}: {status}")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n[worker] Stopped by user.")
        finally:
            await scheduler.close()

    asyncio.run(_worker_loop())


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="vinu-live — Live execution engine")
    sub = parser.add_subparsers(dest="command", required=True)

    serve_p = sub.add_parser("serve", help="Start HTTP API server")
    serve_p.add_argument("--host", default=None)
    serve_p.add_argument("--port", type=int, default=None)
    serve_p.set_defaults(func=serve_main)

    cycle_p = sub.add_parser("cycle", help="Run a single trading cycle")
    cycle_p.set_defaults(func=run_cycle_main)

    worker_p = sub.add_parser("worker", help="Run continuous worker loop")
    worker_p.add_argument("--interval", type=int, dest="interval_sec", default=None)
    worker_p.set_defaults(func=worker_main)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    setup_logging("live")
    if hasattr(args, "func"):
        args.func(args)
    else:
        _parse_args(["--help"])


if __name__ == "__main__":
    main()
