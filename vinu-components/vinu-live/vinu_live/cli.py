from __future__ import annotations

import argparse
import asyncio
import logging
import time

from vinu_lib.debug import setup_logging
from vinu_live.config import load_config
from vinu_live.scheduler import LiveScheduler
from vinu_live.feedback_loop import FeedbackLoopWorker
from vinu_live.shadow_evaluator import ShadowEvaluator
from vinu_live.trade_plan.orchestrator import TradePlanOrchestrator


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


def run_trade_plan_cycle_main(args: argparse.Namespace) -> None:
    async def _run() -> None:
        config = load_config()
        orchestrator = TradePlanOrchestrator(config)
        try:
            result = await orchestrator.cycle()
            print(f"Trade-plan cycle complete: status={result.get('status')}")
            print(f"  Actions: {len(result.get('actions', []))}")
        finally:
            await orchestrator.close()
    asyncio.run(_run())


def trade_plan_worker_main(args: argparse.Namespace | None = None) -> None:
    """Continuous trade-plan worker — separate loop from `worker_main`'s portfolio
    rebalancer (see Phase 6 implementation doc for why these stay separate)."""
    config = load_config()
    interval = (
        args.interval_sec if args and getattr(args, "interval_sec", None)
        else config.trade_plan_worker_interval_sec
    )
    print(f"[trade-plan-worker] Starting (interval={interval}s)")
    print(f"[trade-plan-worker] Press Ctrl+C to stop.\n")

    async def _worker_loop() -> None:
        orchestrator = TradePlanOrchestrator(config)
        try:
            while True:
                result = await orchestrator.cycle()
                status = result.get("status", "unknown")
                print(f"[trade-plan-worker] Cycle {result.get('cycle_id', '?')}: {status}")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n[trade-plan-worker] Stopped by user.")
        finally:
            await orchestrator.close()

    asyncio.run(_worker_loop())


def run_shadow_evaluate_main(args: argparse.Namespace) -> None:
    async def _run() -> None:
        config = load_config()
        evaluator = ShadowEvaluator(
            research_api_url=config.research_api_url,
            agent_api_url=config.agent_api_url,
        )
        try:
            results = await evaluator.evaluate_all()
            print(f"Shadow evaluation complete: {len(results)} artifacts checked")
            for r in results:
                print(f"  {r['artifact_id']}: {r['status']} (paper={r.get('paper_sharpe')})")
        finally:
            await evaluator.close()
    asyncio.run(_run())


def run_feedback_cycle_main(args: argparse.Namespace) -> None:
    async def _run() -> None:
        config = load_config()
        worker = FeedbackLoopWorker(config)
        try:
            result = await worker.cycle()
            print(f"Feedback cycle complete: status={result.get('status')}")
            print(f"  Positions processed: {len(result.get('processed', []))}")
        finally:
            await worker.close()
    asyncio.run(_run())


def feedback_worker_main(args: argparse.Namespace | None = None) -> None:
    """Continuous Phase 7 feedback worker — separate loop from the trade-plan and
    portfolio-rebalancer workers (each closes a different loop)."""
    config = load_config()
    interval = (
        args.interval_sec if args and getattr(args, "interval_sec", None)
        else config.feedback_worker_interval_sec
    )
    print(f"[feedback-worker] Starting (interval={interval}s)")
    print(f"[feedback-worker] Press Ctrl+C to stop.\n")

    async def _worker_loop() -> None:
        worker = FeedbackLoopWorker(config)
        try:
            while True:
                result = await worker.cycle()
                status = result.get("status", "unknown")
                print(f"[feedback-worker] Cycle {result.get('cycle_id', '?')}: {status}")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n[feedback-worker] Stopped by user.")
        finally:
            await worker.close()

    asyncio.run(_worker_loop())


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

    tp_cycle_p = sub.add_parser("trade-plan-cycle", help="Run a single Phase 4 trade-plan cycle")
    tp_cycle_p.set_defaults(func=run_trade_plan_cycle_main)

    tp_worker_p = sub.add_parser("trade-plan-worker", help="Run continuous trade-plan worker loop")
    tp_worker_p.add_argument("--interval", type=int, dest="interval_sec", default=None)
    tp_worker_p.set_defaults(func=trade_plan_worker_main)

    fb_cycle_p = sub.add_parser("feedback-cycle", help="Run a single Phase 7 feedback-loop cycle")
    fb_cycle_p.set_defaults(func=run_feedback_cycle_main)

    se_p = sub.add_parser("shadow-evaluate", help="Run a single shadow-evaluation cycle (BENCHING artifacts)")
    se_p.set_defaults(func=run_shadow_evaluate_main)

    fb_worker_p = sub.add_parser("feedback-worker", help="Run continuous feedback-loop worker")
    fb_worker_p.add_argument("--interval", type=int, dest="interval_sec", default=None)
    fb_worker_p.set_defaults(func=feedback_worker_main)

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
