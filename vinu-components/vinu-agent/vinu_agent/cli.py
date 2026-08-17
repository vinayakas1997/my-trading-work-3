import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

from vinu_infra.debug import setup_logging

from .agent.planner_triage_hook import PlannerTriage
from .agent.scheduler_workers import (
    bootstrap_new_tickers,
    build_channel_targets,
    hypothesis_reader_for,
    make_planner_on_yes,
    make_summary_agent_fn,
    run_capital_allocator_cycle,
    run_significance_cycle,
)
from .agent.significance_triage import SignificanceFlagStore
from .agent.skill_audit import SkillAuditStore, check_skill_edits
from .agent.ticker_gate import ChangeGate, HttpRunLogReader, RunLogTrigger, run_gate_cycle
from .broker.factory import get_live_broker
from .broker.kill_switch import halt_trading, is_trading_halted, resume_trading
from .broker.mandate import DEFAULT_MANDATE_PATH, TradingMandate
from .config import load_config
from .service import AgentService


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="vinu-agent", description="Vinu Agent CLI")
    sub = parser.add_subparsers(dest="command")

    # ── chat ──
    chat_p = sub.add_parser("chat", help="Start an interactive chat session")
    chat_p.add_argument("--session", "-s", default="", help="Session ID to resume")

    # ── send ──
    send_p = sub.add_parser("send", help="Send a message to a session")
    send_p.add_argument("session_id", help="Session ID")
    send_p.add_argument("message", help="Message content")

    # ── serve ──
    serve_p = sub.add_parser("serve", help="Start the FastAPI server")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8086)

    # ── skill-audit-worker ──
    # Phase 9 scheduler-wiring (New-talk-agents/new-thinking/
    # new-restructure/phases/phase-9-scheduler-wiring/): check_skill_edits()
    # was correct and tested since Phase 6 but had no scheduled caller,
    # same "not wired to a live loop" gap Phase 0/4/7 also flagged. This
    # gives it one, mirroring vinu-live's `while True: cycle(); sleep()`
    # worker pattern (see vinu_live/cli.py).
    saw_p = sub.add_parser("skill-audit-worker", help="Run continuous skill-edit audit worker loop")
    saw_p.add_argument("--interval", type=int, dest="interval_sec", default=None)

    # ── planner-worker ──
    # Phase 9 scheduler-wiring: mermaid-explanation.md's Planner (Section
    # 2) = a deterministic triage hook (agent/planner_triage_hook.py, new)
    # + the real, already-built `idea_generator` (teams/research/). This
    # gives the whole watchlist path (RunLog -> Summary Agent refresh ->
    # ChangeGate -> Planner triage -> research team hand-off) a scheduled
    # caller for the first time -- RunLogTrigger/ChangeGate (Phase 0) were
    # correct and tested since Phase 0 but had no live loop invoking them.
    pw_p = sub.add_parser("planner-worker", help="Run continuous Planner triage + Summary Agent refresh worker loop")
    pw_p.add_argument("--interval", type=int, dest="interval_sec", default=None)

    # ── significance-worker ──
    # Phase 9 scheduler-wiring: Significance Triage (Phase 7) was correct
    # and tested but had no scheduled caller and no real delivery target.
    # Telegram/Discord are independently gated on their own token+id being
    # configured (agent/scheduler_workers.py's build_channel_targets) --
    # either, both, or neither can be set; a flag is still recorded even
    # with zero channels configured, just not delivered anywhere yet.
    sw2_p = sub.add_parser("significance-worker", help="Run continuous Significance Triage detection + delivery worker loop")
    sw2_p.add_argument("--interval", type=int, dest="interval_sec", default=None)

    # ── capital-allocator-worker ──
    # Shortcoming #1 (implementation-plan task 01): capital_allocator was
    # fully wired and correct when invoked but had no scheduled caller --
    # approved PEND candidates could sit unfunded indefinitely. Same shape
    # as the other workers above: background loop on a fixed cadence,
    # collecting the whole PEND batch and handing it to the real
    # capital_allocator team (agent/scheduler_workers.py's
    # run_capital_allocator_cycle).
    caw_p = sub.add_parser("capital-allocator-worker", help="Run continuous capital-allocator (PEND batch funding) worker loop")
    caw_p.add_argument("--interval", type=int, dest="interval_sec", default=None)

    # ── broker ──
    broker_p = sub.add_parser("broker", help="Broker operations")
    broker_sub = broker_p.add_subparsers(dest="broker_cmd")
    broker_sub.add_parser("status", help="Show account, positions, and open orders")
    broker_sub.add_parser("halt", help="Activate kill switch — block all trading")
    broker_sub.add_parser("resume", help="Deactivate kill switch — resume trading")

    # ── channel ──
    channel_p = sub.add_parser("channel", help="Channel operations")
    channel_sub = channel_p.add_subparsers(dest="channel_cmd")
    channel_sub.add_parser("list", help="List configured channels")
    ch_send = channel_sub.add_parser("send", help="Send a message to a channel")
    ch_send.add_argument("channel_name", help="Channel name (telegram, discord)")
    ch_send.add_argument("chat_id", help="Target chat ID")
    ch_send.add_argument("message", help="Message text")

    # ── swarm ──
    swarm_p = sub.add_parser("swarm", help="Swarm operations")
    swarm_sub = swarm_p.add_subparsers(dest="swarm_cmd")
    swarm_sub.add_parser("list", help="List available swarm presets")
    sw_run = swarm_sub.add_parser("run", help="Run a swarm preset")
    sw_run.add_argument("preset", help="Preset name")
    sw_run.add_argument("--vars", nargs="*", default=[], help="User variables key=val")

    # ── memory ──
    memory_p = sub.add_parser("memory", help="Memory operations")
    memory_sub = memory_p.add_subparsers(dest="memory_cmd")
    mem_search = memory_sub.add_parser("search", help="Search agent memory")
    mem_search.add_argument("query", help="Search query")

    # ── mandate ──
    mandate_p = sub.add_parser("mandate", help="Trading mandate operations")
    mandate_sub = mandate_p.add_subparsers(dest="mandate_cmd")
    mandate_sub.add_parser("show", help="Show current trading mandate")
    mandate_set = mandate_sub.add_parser("set", help="Set a mandate value")
    mandate_set.add_argument("key", help="Mandate field name")
    mandate_set.add_argument("value", help="New value (JSON-encoded)")

    return parser.parse_args(argv)


async def _chat_loop(session_id: str = "") -> None:
    async with AgentService() as svc:
        if session_id:
            session = svc._store.get_session(session_id)
            if not session:
                print(f"Session {session_id} not found")
                return
        else:
            session = await svc.create_session(title="CLI Chat")
            print(f"Session: {session.session_id}")

        print("Type /quit to exit, /cancel to cancel current run")
        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("\n> ").strip()
                )
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                continue
            if line == "/quit":
                break
            if line == "/cancel":
                svc.cancel(session.session_id)
                print("[cancelled]")
                continue

            result = await svc.send_message(session.session_id, line)
            print(f"\n[{result.get('attempt_id', '')}]")
            await asyncio.sleep(0.5)
            messages = svc._store.get_messages(session.session_id, limit=2)
            for m in reversed(messages):
                if m.role == "assistant":
                    print(f"\n{m.content}")


async def _cmd_broker(args) -> None:
    broker = get_live_broker()
    if not broker.is_configured():
        print('{"status": "error", "error": "Broker API not configured"}')
        return

    if args.broker_cmd == "halt":
        halt_trading()
        print('{"status": "ok", "message": "Trading halted"}')
        return

    if args.broker_cmd == "resume":
        resume_trading()
        print('{"status": "ok", "message": "Trading resumed"}')
        return

    result = {
        "kill_switch_active": is_trading_halted(),
    }
    try:
        account = broker.get_account()
        result["account"] = {
            "status": account.status,
            "cash": account.cash,
            "portfolio_value": account.portfolio_value,
            "buying_power": account.buying_power,
            "equity": account.equity,
        }
        positions = broker.get_positions()
        result["positions"] = [
            {"symbol": p.symbol, "qty": p.qty, "market_value": p.market_value, "unrealized_pl": p.unrealized_pl}
            for p in positions
        ]
        orders = broker.get_orders()
        result["open_orders"] = [
            {"id": o.order_id, "symbol": o.symbol, "side": o.side, "type": o.type, "status": o.status, "qty": o.qty}
            for o in orders
        ]
    except Exception as exc:
        result["error"] = str(exc)
    print(json.dumps(result, indent=2))


def _cmd_channel(args) -> None:
    from vinu_infra.secrets_loader import load_secret

    if args.channel_cmd == "list":
        print(json.dumps({
            "channels": [
                {"name": "telegram", "configured": bool(load_secret("telegram_token", "TELEGRAM_TOKEN"))},
                {"name": "discord", "configured": bool(load_secret("discord_token", "DISCORD_TOKEN"))},
            ]
        }, indent=2))
    elif args.channel_cmd == "send":
        print(json.dumps({
            "status": "not_implemented",
            "message": "Channel send requires a running bot. Use the API instead.",
        }))


async def _cmd_swarm(args) -> None:
    async with AgentService() as svc:
        runtime = svc.swarm_runtime()
        if args.swarm_cmd == "list":
            presets = runtime.list_presets()
            print(json.dumps(presets, indent=2))
        elif args.swarm_cmd == "run":
            user_vars = {}
            for v in args.vars:
                if "=" in v:
                    k, val = v.split("=", 1)
                    user_vars[k] = val
            run = runtime.create_run(args.preset, user_vars)
            run = runtime.start_run(run.run_id)
            print(json.dumps({
                "run_id": run.run_id,
                "preset": args.preset,
                "status": run.status.value,
            }, indent=2))


def _cmd_mandate(args) -> None:
    if args.mandate_cmd == "show":
        mandate = TradingMandate.load()
        print(json.dumps(mandate.to_dict(), indent=2))
    elif args.mandate_cmd == "set":
        mandate = TradingMandate.load()
        key = args.key
        val = args.value
        if hasattr(mandate, key):
            current = getattr(mandate, key)
            if isinstance(current, bool):
                setattr(mandate, key, val.lower() in ("true", "1", "yes"))
            elif isinstance(current, (int, float)):
                setattr(mandate, key, type(current)(val))
            elif isinstance(current, set):
                if val.startswith("[") or val.startswith('"'):
                    setattr(mandate, key, set(json.loads(val)))
                else:
                    setattr(mandate, key, {val})
            else:
                setattr(mandate, key, val)
            DEFAULT_MANDATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            import yaml
            DEFAULT_MANDATE_PATH.write_text(
                yaml.dump(mandate.to_dict(), default_flow_style=False),
                encoding="utf-8",
            )
            print(json.dumps({"status": "ok", "key": key, "value": getattr(mandate, key)}))
        else:
            print(json.dumps({"status": "error", "error": f"Unknown mandate field: {key}"}))


def resolve_worker_interval(args: argparse.Namespace | None, config, config_field: str = "skill_audit_worker_interval_sec") -> int:
    """Unlike vinu-live's own resolve_worker_interval (vinu_live/cli.py),
    there's no dedicated per-worker console script for any vinu-agent
    worker -- each is only ever reached via its own subcommand through
    main()'s dispatch, so args is always real here, never None."""
    return args.interval_sec if args and args.interval_sec else getattr(config, config_field)


def skill_audit_worker_main(args: argparse.Namespace) -> None:
    config = load_config()
    interval = resolve_worker_interval(args, config)
    skills_root = Path(config.skills_dir)
    data_root = Path(config.memory_dir).parent
    print(f"[skill-audit-worker] Starting (interval={interval}s, skills_root={skills_root})")
    print(f"[skill-audit-worker] Press Ctrl+C to stop.\n")

    log = logging.getLogger("vinu.agent.skill_audit_worker")
    audit_store = SkillAuditStore(data_root / "skill_audit.db")
    try:
        while True:
            try:
                entries = check_skill_edits(skills_root, audit_store)
            except Exception:
                log.exception(
                    "skill-audit cycle failed",
                    extra={"vinu_ctx": {"worker": "skill-audit-worker"}},
                )
                raise
            log.info(
                "skill-audit cycle complete",
                extra={"vinu_ctx": {"worker": "skill-audit-worker", "new_entries": len(entries)}},
            )
            for entry in entries:
                log.info(
                    "skill edit detected",
                    extra={
                        "vinu_ctx": {
                            "worker": "skill-audit-worker",
                            "skill_path": str(entry.skill_path),
                            "diff_summary": entry.diff_summary,
                        }
                    },
                )
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[skill-audit-worker] Stopped by user.")
    finally:
        audit_store.close()


def planner_worker_main(args: argparse.Namespace) -> None:
    """Watchlist = TickerSummaryStore.list_summaries() -- tickers that
    already have a Summary Agent read on file, per the decided watchlist
    source (Phase 9's implementation record). Before each cycle's own
    tickers are read, bootstrap_new_tickers() cold-starts a screener run
    for any configured seed ticker (VINU_AGENT_WATCHLIST_SEED_TICKERS)
    not yet in the store -- the watchlist bootstrap gap this worker used
    to have no answer for. Per ticker, per cycle: RunLogTrigger refreshes
    the Summary Agent if vinu-initial-analysis has a new run_id, then
    ChangeGate (Phase 0, unmodified) decides whether anything actually
    changed since the last Planner pass; only a "yes" reaches
    PlannerTriage + the real research-team hand-off."""
    config = load_config()
    interval = resolve_worker_interval(args, config, "planner_worker_interval_sec")
    print(f"[planner-worker] Starting (interval={interval}s)")
    print(f"[planner-worker] Press Ctrl+C to stop.\n")

    log = logging.getLogger("vinu.agent.planner_worker")
    with AgentService() as service:
        run_log_trigger = RunLogTrigger(
            HttpRunLogReader(config.services.get("vinu_initial_analysis")),
            service.ticker_summary_store, service.ticker_ledger,
        )
        change_gate = ChangeGate(service.ticker_summary_store, service._strategy_store, service.ticker_ledger)
        triage = PlannerTriage(service._strategy_store, hypothesis_reader_for(service), service.ticker_ledger)
        summary_agent_fn = make_summary_agent_fn(service)
        on_yes = make_planner_on_yes(service, triage)

        try:
            while True:
                try:
                    if config.watchlist_seed_tickers:
                        bootstrapped = bootstrap_new_tickers(service, config.watchlist_seed_tickers)
                        if bootstrapped:
                            log.info(
                                "bootstrapped new tickers",
                                extra={"vinu_ctx": {"worker": "planner-worker", "tickers": bootstrapped}},
                            )
                    tickers = [s.ticker for s in service.ticker_summary_store.list_summaries()]
                    for ticker in tickers:
                        try:
                            run_log_trigger.refresh_if_stale(ticker, summary_agent_fn)
                        except Exception:
                            log.exception(
                                "summary refresh failed for %s, continuing", ticker,
                                extra={"vinu_ctx": {"worker": "planner-worker", "ticker": ticker}},
                            )
                    run_gate_cycle(tickers, change_gate, on_yes)
                except Exception:
                    log.exception(
                        "planner cycle failed",
                        extra={"vinu_ctx": {"worker": "planner-worker"}},
                    )
                    raise
                log.info(
                    "planner cycle complete",
                    extra={"vinu_ctx": {"worker": "planner-worker", "watchlist_size": len(tickers)}},
                )
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n[planner-worker] Stopped by user.")


def significance_worker_main(args: argparse.Namespace) -> None:
    """Watchlist = TickerSummaryStore.list_summaries(), same decided
    source as planner-worker. Per cycle: all three pattern detectors
    (repeated rejection, large funding, thesis-contradicting close) per
    ticker, record + deliver any hit through whichever channels are
    actually configured (see build_channel_targets -- zero, one, or both
    of Telegram/Discord). The large-funding threshold is the mandate's own
    max_order_value -- the one dollar ceiling already decided/committed
    to, never a second number invented for this detector."""
    config = load_config()
    interval = resolve_worker_interval(args, config, "significance_worker_interval_sec")
    print(f"[significance-worker] Starting (interval={interval}s)")
    print(f"[significance-worker] Press Ctrl+C to stop.\n")

    targets = build_channel_targets(config)
    print(f"[significance-worker] {len(targets)} delivery channel(s) configured")

    log = logging.getLogger("vinu.agent.significance_worker")
    funding_threshold = TradingMandate.load().max_order_value

    data_root = Path(config.memory_dir).parent
    flag_store = SignificanceFlagStore(data_root / "significance_flags.db")
    try:
        with AgentService() as service:
            try:
                while True:
                    tickers = [s.ticker for s in service.ticker_summary_store.list_summaries()]
                    try:
                        flags = asyncio.run(
                            run_significance_cycle(
                                tickers, service.ticker_ledger, flag_store, targets,
                                funding_threshold=funding_threshold,
                            ),
                        )
                    except Exception:
                        log.exception(
                            "significance cycle failed",
                            extra={"vinu_ctx": {"worker": "significance-worker"}},
                        )
                        raise
                    log.info(
                        "significance cycle complete",
                        extra={
                            "vinu_ctx": {
                                "worker": "significance-worker",
                                "tickers_checked": len(tickers),
                                "flags_raised": len(flags),
                            }
                        },
                    )
                    time.sleep(interval)
            except KeyboardInterrupt:
                print("\n[significance-worker] Stopped by user.")
    finally:
        flag_store.close()


def capital_allocator_worker_main(args: argparse.Namespace) -> None:
    """Scheduled caller for capital_allocator (shortcoming #1): on a fixed
    cadence, collect the whole PEND batch and hand it, with the configured
    risk budget, to the real capital_allocator team -- the same
    `while True: cycle(); sleep()` shape and the same
    `run_team_for_ticker(...)` team invocation planner-worker already uses
    for its research hand-off. A cycle with zero PEND artifacts skips the
    LLM team run entirely (nothing to fund), and a failed cycle is logged
    then re-raised (crash-loud with a structured record, never silently
    swallowed)."""
    config = load_config()
    interval = resolve_worker_interval(args, config, "capital_allocator_worker_interval_sec")
    print(f"[capital-allocator-worker] Starting (interval={interval}s, budget=${config.capital_allocator_budget:.2f})")
    print(f"[capital-allocator-worker] Press Ctrl+C to stop.\n")

    log = logging.getLogger("vinu.agent.capital_allocator_worker")
    with AgentService() as service:
        cycle = 0
        try:
            while True:
                cycle += 1
                try:
                    result = run_capital_allocator_cycle(
                        service, budget=config.capital_allocator_budget, cycle=cycle,
                    )
                    log.info(
                        "capital-allocator cycle complete",
                        extra={"vinu_ctx": {"worker": "capital-allocator-worker", "cycle": cycle, **result}},
                    )
                except Exception:
                    log.exception(
                        "capital-allocator cycle failed",
                        extra={"vinu_ctx": {"worker": "capital-allocator-worker", "cycle": cycle}},
                    )
                    raise
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n[capital-allocator-worker] Stopped by user.")


def main() -> None:
    setup_logging("agent")
    args = _parse_args()
    if args.command == "serve":
        from .server.app import run
        run(host=args.host, port=args.port)
    elif args.command == "chat":
        asyncio.run(_chat_loop(session_id=args.session))
    elif args.command == "send":
        async def _send():
            async with AgentService() as svc:
                result = await svc.send_message(args.session_id, args.message)
                print(json.dumps(result, indent=2))
        asyncio.run(_send())
    elif args.command == "broker":
        async def _broker():
            await _cmd_broker(args)
        asyncio.run(_broker())
    elif args.command == "channel":
        _cmd_channel(args)
    elif args.command == "skill-audit-worker":
        skill_audit_worker_main(args)
    elif args.command == "planner-worker":
        planner_worker_main(args)
    elif args.command == "significance-worker":
        significance_worker_main(args)
    elif args.command == "capital-allocator-worker":
        capital_allocator_worker_main(args)
    elif args.command == "swarm":
        asyncio.run(_cmd_swarm(args))
    elif args.command == "mandate":
        _cmd_mandate(args)
    else:
        _parse_args(["--help"])


if __name__ == "__main__":
    main()
