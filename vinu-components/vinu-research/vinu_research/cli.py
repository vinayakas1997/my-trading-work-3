from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any

from vinu_research.config import ResearchConfig, load_config
from vinu_research.loop import StrategyResearchLoop
from vinu_research.models import IterationRecord
from vinu_research.tools import ResearchTools

LOG = logging.getLogger(__name__)

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TICKER_PATTERN = re.compile(r"\b[A-Z]{1,5}\b")
_KNOWN_NON_TICKERS = frozenset({
    "A", "I", "AN", "AS", "AT", "BE", "BY", "DO", "GO", "HE", "IF",
    "IN", "IS", "IT", "ME", "MY", "NO", "OF", "ON", "OR", "SO",
    "TO", "UP", "US", "WE",
    "ALL", "AND", "ANY", "ARE", "BAD", "BEST", "BIG", "BUT", "CAN",
    "DID", "FOR", "GET", "GOOD", "HAD", "HAS", "HAVE", "HER", "HIS",
    "HOW", "ITS", "JOB", "LOT", "LOW", "MAN", "NEW", "NOT", "NOW",
    "OLD", "OUR", "OUT", "OWN", "PER", "PUT", "SAY", "SEE", "SHE",
    "TOP", "TWO", "USE", "WAS", "WAY", "WHO", "WILL", "YET", "TEST",
    "SMA", "RSI", "ADX", "MA", "MACD", "DD", "ATR", "EMA",
    "ETF", "IPO", "ROI", "PE", "EPS", "PEG", "PB", "ROE", "YTD",
    "HIGH", "LOW",
})


def serve_main(args: argparse.Namespace) -> None:
    import uvicorn
    from vinu_research.server.app import create_app

    config = load_config()
    host = args.host or config.host
    port = args.port or config.port
    uvicorn.run(create_app(), host=host, port=port)


def _print_separator(char: str = "\u2500") -> None:
    print(char * 60)


def _on_iteration(record: IterationRecord) -> None:
    m = record.result.metrics
    print()
    _print_separator()
    print(f"[Iteration {record.iteration}] Quant Coder: Strategy generated")
    print(f"[Iteration {record.iteration}] Simulator: Sharpe={m.sharpe_ratio:.2f}, "
          f"MaxDD={m.max_drawdown:.1%}, WinRate={m.win_rate:.0%}")
    print(f"[Iteration {record.iteration}] Risk Critic: {record.critique.reasoning}")

    if record.critique.suggestions:
        print(f"[Iteration {record.iteration}] Suggestions:")
        for s in record.critique.suggestions:
            print(f"  \u2192 {s}")

    if record.critique.verdict == "PASS":
        print(f"[Iteration {record.iteration}] \u2713 VERDICT: PASS")
    elif record.critique.verdict == "STOP":
        print(f"[Iteration {record.iteration}] \u2717 VERDICT: STOP")
    else:
        print(f"[Iteration {record.iteration}] \u21bb VERDICT: REFINE")
    _print_separator()


def _validate_date(val: str | None, name: str) -> str | None:
    if val is None:
        return None
    if not _DATE_PATTERN.match(val):
        raise ValueError(
            f"Invalid {name}: '{val}'. Expected format: YYYY-MM-DD"
        )
    return val


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="vinu-research \u2014 Agentic Strategy Researcher"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    serve_p = sub.add_parser("serve", help="Start HTTP API server")
    serve_p.add_argument("--host", default=None)
    serve_p.add_argument("--port", type=int, default=None)
    serve_p.set_defaults(func=serve_main)

    run_p = sub.add_parser("run", help="Run the strategy research loop")
    run_p.add_argument("idea", nargs="?", default=None, help="Strategy idea (e.g. 'test SMA20/SMA50 crossover on AAPL'). Auto-proposed from angles if not set.")
    run_p.add_argument("--symbol", default=None, help="Ticker symbol (extracted from idea if not set)")
    run_p.add_argument(
        "--universe", default=None,
        help="Comma-separated tickers to backtest as a portfolio (e.g. AAPL,MSFT,GOOGL). "
             "The same strategy runs on each symbol and results are aggregated into one "
             "portfolio, with a correlation matrix and beta-hedge overlay in the report.",
    )
    run_p.add_argument("--from", dest="from_date", default=None, help="Start date (YYYY-MM-DD)")
    run_p.add_argument("--to", dest="to_date", default=None, help="End date (YYYY-MM-DD)")
    run_p.add_argument("--max-iterations", type=int, default=None, help="Max research iterations")
    run_p.add_argument("--indicators", default=None, help="Comma-separated indicator kinds")
    run_p.add_argument("--capital", type=float, default=None, help="Initial capital")
    run_p.add_argument(
        "--strategy-code", default=None,
        help="Pre-written strategy code. Provide a file path to read strategy code from. "
             "Skips LLM generation and uses this code as the starting point; user_idea "
             "is used as refinement context.",
    )
    run_p.add_argument("--approve", action="store_true", help="Approve strategy automatically (non-interactive)")
    run_p.add_argument("--llm", action="store_true", help="Enable LLM usage (risk analysis + strategy generation/refinement)")
    run_p.add_argument(
        "--no-llm", action="store_true",
        help="Disable all LLM usage (risk analysis + strategy refinement); falls back to the "
             "deterministic template/filter path (not actively developed further for now)",
    )
    run_p.add_argument("--walk-forward", action="store_true", help="Enable walk-forward validation")
    run_p.add_argument("--wf-method", default=None, help="Walk-forward method: expanding or sliding")
    run_p.add_argument("--wf-windows", type=int, default=None, help="Number of walk-forward windows")
    run_p.add_argument("--target-sharpe", type=float, default=None, help="Target Sharpe ratio threshold for PASS verdict")
    run_p.add_argument("--target-max-drawdown", type=float, default=None, help="Target Max Drawdown threshold for PASS verdict")
    run_p.add_argument("--quiet", action="store_true", help="Suppress progress output")
    run_p.set_defaults(func=run_main)

    list_p = sub.add_parser("recipes", help="List available strategy recipes")
    list_p.set_defaults(func=recipes_main)

    auto_p = sub.add_parser("autopilot", help="Run research autopilot pipeline")
    auto_p.add_argument("hypothesis_id", help="Hypothesis ID to run autopilot for")
    auto_p.add_argument("--from", dest="from_date", default=None, help="Start date (YYYY-MM-DD)")
    auto_p.add_argument("--to", dest="to_date", default=None, help="End date (YYYY-MM-DD)")
    auto_p.add_argument("--scaffold-only", action="store_true", help="Only scaffold signal engine, skip config generation")
    auto_p.set_defaults(func=autopilot_main)

    link_p = sub.add_parser("link-autopilot", help="Link backtest results to hypothesis")
    link_p.add_argument("hypothesis_id", help="Hypothesis ID")
    link_p.add_argument("run_dir", help="Path to backtest run directory (containing run_card.json)")
    link_p.set_defaults(func=link_autopilot_main)

    decay_p = sub.add_parser("decay-scan", help="Run decay scan on ACTIVE/MONITORING artifacts")
    decay_p.add_argument("--db", default=None, help="Path to strategy store database (default: <data_root>/strategy_store.db)")
    decay_p.add_argument("--dry-run", action="store_true", help="Show transitions without persisting")
    decay_p.set_defaults(func=decay_scan_main)

    sched_decay_p = sub.add_parser("schedule-decay", help="Run decay-scan on a repeating interval")
    sched_decay_p.add_argument("--db", default=None, help="Path to strategy store database (default: <data_root>/strategy_store.db)")
    sched_decay_p.add_argument("--dry-run", action="store_true", help="Show transitions without persisting")
    sched_decay_p.add_argument("--interval-hours", type=int, default=24, help="Hours between scans (default: 24)")
    sched_decay_p.set_defaults(func=schedule_decay_main)

    promote_p = sub.add_parser(
        "promote-scan",
        help="List BENCHING artifacts and promote those clearing the deflated-Sharpe/holdout bar",
    )
    promote_p.add_argument("--db", default=None, help="Path to strategy store database (default: <data_root>/strategy_store.db)")
    promote_p.add_argument("--dry-run", action="store_true", help="Show which artifacts would be promoted without persisting")
    promote_p.set_defaults(func=promote_scan_main)

    ensure_p = sub.add_parser(
        "ensure",
        help="Run research for a ticker only if it has no ACTIVE/MONITORING strategy yet",
    )
    ensure_p.add_argument("idea", nargs="?", default=None, help="Strategy idea to use if research is triggered. Auto-proposed from angles if not set.")
    ensure_p.add_argument("--symbol", required=True, help="Ticker symbol")
    ensure_p.add_argument("--from", dest="from_date", default=None, help="Start date (YYYY-MM-DD)")
    ensure_p.add_argument("--to", dest="to_date", default=None, help="End date (YYYY-MM-DD)")
    ensure_p.set_defaults(func=ensure_main)

    return parser.parse_args(argv)


def _extract_symbol(idea: str) -> str | None:
    words = _TICKER_PATTERN.findall(idea.upper())
    candidates = [t for t in words if t not in _KNOWN_NON_TICKERS]
    if not candidates:
        return None
    candidates.sort(key=lambda x: -len(x))
    return candidates[0]


def _sanitize_filename(name: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
    safe = re.sub(r"_+", "_", safe)
    return safe.strip("_") or "strategy"


def run_main(args: argparse.Namespace) -> None:
    config = load_config()
    overrides: dict[str, Any] = {}
    if args.max_iterations is not None:
        overrides["max_iterations"] = args.max_iterations
    if args.capital is not None:
        overrides["initial_capital"] = args.capital
    if args.llm:
        overrides["llm_enabled"] = True
    if args.no_llm:
        overrides["llm_enabled"] = False
    if args.walk_forward:
        overrides["walk_forward_enabled"] = True
    if args.wf_method is not None:
        overrides["walk_forward_method"] = args.wf_method
    if args.wf_windows is not None:
        overrides["walk_forward_windows"] = args.wf_windows
    if getattr(args, "target_sharpe", None) is not None:
        overrides["target_sharpe_ratio"] = args.target_sharpe
    if getattr(args, "target_max_drawdown", None) is not None:
        overrides["target_max_drawdown"] = args.target_max_drawdown
    if overrides:
        config = ResearchConfig(**{**config.__dict__, **overrides})

    user_idea: str | None = args.idea
    if user_idea is not None and not args.symbol:
        symbol = _extract_symbol(user_idea) or "AAPL"
    elif args.symbol:
        symbol = args.symbol
    else:
        print("[vinu-research] Error: --symbol is required when no idea is provided")
        sys.exit(1)
    symbol = symbol.upper()

    from_date = _validate_date(args.from_date, "--from") or "2024-01-01"
    to_date = _validate_date(args.to_date, "--to") or "2024-12-31"

    indicators: list[str] | None = None
    if args.indicators:
        indicators = [k.strip().lower() for k in args.indicators.split(",") if k.strip()]

    universe: list[str] | None = None
    if getattr(args, "universe", None):
        universe = [t.strip().upper() for t in args.universe.split(",") if t.strip()]

    if user_idea is None:
        print(f"[vinu-research] No idea provided — proposing from angle context for {symbol}...")
        tools_tmp = ResearchTools(config)
        try:
            angles = asyncio.run(tools_tmp.get_angle_context(symbol, config.interval))
        finally:
            asyncio.run(tools_tmp.close())
        if angles and config.llm_enabled:
            from vinu_research.llm import ResearchLlmClient
            from vinu_research.llm_generator import LlmStrategyGenerator
            llm = ResearchLlmClient(config)
            try:
                gen = LlmStrategyGenerator(llm)
                user_idea = asyncio.run(gen.propose_idea_from_angles(angles))
            finally:
                asyncio.run(llm.close())
        elif angles:
            tl = angles.get("trend_lifecycle", {})
            stage = tl.get("stage", "unknown")
            risk = tl.get("risk", "unknown")
            user_idea = f"Trend-following strategy for {stage} stage with {risk} risk regime"
        else:
            user_idea = f"Strategy for {symbol}"
        print(f"[vinu-research] Auto-proposed idea: {user_idea}")

    strategy_code: str | None = None
    if getattr(args, "strategy_code", None):
        code_path = Path(args.strategy_code)
        if code_path.exists():
            strategy_code = code_path.read_text()
            print(f"[vinu-research] Loaded strategy code from {code_path}")
        else:
            print(f"[vinu-research] Warning: --strategy-code file not found: {args.strategy_code}")
            sys.exit(1)

    tools = ResearchTools(config)

    on_iteration = None if args.quiet else _on_iteration
    loop = StrategyResearchLoop(
        tools=tools,
        config=config,
        on_iteration=on_iteration,
    )

    print(f"[vinu-research] Strategy: {user_idea}")
    print(f"[vinu-research] Ticker: {symbol}")
    print(f"[vinu-research] Period: {from_date} \u2192 {to_date}")
    print(f"[vinu-research] Max iterations: {config.max_iterations}")
    if indicators:
        print(f"[vinu-research] Indicators: {', '.join(indicators)}")
    if universe and len(set(universe)) > 1:
        print(f"[vinu-research] Universe: {', '.join(universe)}")
    if config.walk_forward_enabled:
        print(f"[vinu-research] Walk-forward: enabled ({config.walk_forward_method}, {config.walk_forward_windows} windows)")
    _print_separator()

    async def _run_and_close():
        try:
            return await loop.run(
                user_idea=user_idea,
                strategy_code=strategy_code,
                symbol=symbol,
                from_date=from_date,
                to_date=to_date,
                indicators=indicators,
                initial_capital=config.initial_capital,
                universe=universe,
            )
        finally:
            # Must close under the same event loop that created these httpx
            # clients — a second, separate asyncio.run() call for cleanup
            # raises "RuntimeError: Event loop is closed" (the transport's
            # callbacks are bound to the now-dead loop from loop.run()).
            await tools.close()

    try:
        result = asyncio.run(_run_and_close())
    except KeyboardInterrupt:
        print("\n[vinu-research] Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n[vinu-research] Error: {e}")
        LOG.exception("Research loop failed")
        sys.exit(1)

    print()
    print(result.report_md)

    saved_path = None
    if result.best_result:
        safe_sym = _sanitize_filename(symbol.lower())
        safe_name = _sanitize_filename(result.best_result.strategy_name.lower())
        interval_str = getattr(config, "interval", "1d")
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path("output") / f"{safe_sym}_{safe_name}_{interval_str}_{ts_str}.py"
        best_rec = next(
            (r for r in result.iterations if r.iteration == result.best_iteration),
            result.iterations[-1] if result.iterations else None,
        )
        if best_rec:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(best_rec.strategy_code)
            saved_path = output_path
            print(f"\nOptimized Strategy Code: saved to {output_path}")

    _print_separator()
    approved = bool(args.approve) if hasattr(args, "approve") else False
    if not approved and hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
        try:
            resp = input("\nApprove this strategy for use? [y/N] ").strip().lower()
            approved = resp in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            pass
    if approved:
        print("[vinu-research] \u2713 Strategy approved")
        if saved_path:
            approved_path = saved_path.parent / f"{saved_path.stem}_approved.py"
            saved_path.rename(approved_path)
            print(f"[vinu-research] Approved strategy saved to {approved_path}")
    else:
        print("[vinu-research] Strategy saved but not approved (run with --approve or re-run later)")


def autopilot_main(args: argparse.Namespace) -> None:
    from vinu_research.hypothesis_registry import HypothesisRegistry
    from vinu_research.tools import (
        generate_backtest_config,
        link_autopilot_backtest,
        run_autopilot,
        scaffold_signal_engine,
    )

    reg = HypothesisRegistry()
    hypothesis = reg.get(args.hypothesis_id)
    if hypothesis is None:
        print(f"[autopilot] Hypothesis {args.hypothesis_id} not found")
        sys.exit(1)

    print(f"[autopilot] Running autopilot for: {hypothesis.title}")
    print(f"[autopilot] Thesis: {hypothesis.thesis}")
    print()

    result = run_autopilot(args.hypothesis_id, reg)
    print(f"[autopilot] Goal created: {result['goal_id']}")
    print(f"[autopilot] Objective: {result['objective']}")
    print()

    if not args.scaffold_only:
        from_date = _validate_date(args.from_date, "--from") or "2024-01-01"
        to_date = _validate_date(args.to_date, "--to") or "2024-12-31"
        config_path = generate_backtest_config(
            args.hypothesis_id, from_date, to_date, reg,
        )
        print(f"[autopilot] Config written: {config_path}")
    else:
        print("[autopilot] Skipping config generation (--scaffold-only)")

    sig_path = scaffold_signal_engine(args.hypothesis_id, reg)
    print(f"[autopilot] Signal engine scaffold: {sig_path}")
    print()
    print("[autopilot] Next steps:")
    print(f"  1. Edit {sig_path} to implement signal logic")
    print(f"  2. Run backtest via vinu-simulator")
    print(f"  3. Run: vinu-research autopilot link {args.hypothesis_id} <run_dir>")


def link_autopilot_main(args: argparse.Namespace) -> None:
    from vinu_research.hypothesis_registry import HypothesisRegistry
    from vinu_research.tools import link_autopilot_backtest

    reg = HypothesisRegistry()
    result = link_autopilot_backtest(args.hypothesis_id, args.run_dir, reg)
    if result["run_card_found"]:
        print(f"[link-autopilot] Linked backtest to hypothesis {args.hypothesis_id}")
        print(f"[link-autopilot] Hypothesis status: {result['hypothesis_status']}")
        print(f"[link-autopilot] Metrics: sharpe={result['metrics'].get('sharpe', 'N/A')}")
    else:
        print(f"[link-autopilot] No run_card.json found in {args.run_dir}")
        print(f"[link-autopilot] Run card will be linked when found")


def _decay_db_path(args: argparse.Namespace) -> "Path":
    from pathlib import Path as _Path
    if args.db:
        return _Path(args.db)
    return load_config().data_root / "strategy_store.db"


def _trigger_re_research(symbol: str) -> None:
    """Re-run research for a decayed strategy's symbol (sync → async bridge).

    Called synchronously from _run_decay_scan when an artifact transitions to
    DECAYED. Uses the newly-autonomous ensure_strategy (A1) with user_idea=None
    so the idea is auto-proposed from the symbol's angle context.
    """
    from vinu_research.service import ResearchService
    config = load_config()
    async def _run() -> None:
        async with ResearchService(config) as svc:
            await svc.ensure_strategy(
                user_idea=None,
                symbol=symbol,
                from_date="",
                to_date="",
            )
    try:
        asyncio.run(_run())
        LOG.info("Re-research triggered for decayed strategy on %s", symbol)
    except Exception as e:
        LOG.warning("Re-research for %s failed: %s", symbol, e)


def _run_decay_scan(store, thresholds, *, dry_run: bool) -> int:
    """Scan ACTIVE/MONITORING artifacts and transition status on decay.

    Branches by artifact.type: "strategy" artifacts (from an approved research
    run) only ever have Sharpe in their bench history, so they're evaluated on
    rolling-Sharpe-vs-baseline alone; everything else uses the original IC/IR
    factor-decay path. Returns the number of artifacts scanned.
    """
    from vinu_research.decay import (
        compute_decay_snapshot,
        compute_strategy_decay_snapshot,
        transition_status,
    )
    from vinu_research.models import ArtifactStatus

    artifacts = store.list_artifacts(status=ArtifactStatus.ACTIVE) + store.list_artifacts(
        status=ArtifactStatus.MONITORING,
    )
    if not artifacts:
        print("[decay-scan] No ACTIVE or MONITORING artifacts found")
        return 0

    print(f"[decay-scan] Scanning {len(artifacts)} artifacts (thresholds: IC>={thresholds.ic_ratio_healthy}, IR>={thresholds.ir_healthy})")
    print()

    for art in artifacts:
        history = store.get_bench_history(art.artifact_id)
        if len(history) < 2:
            print(f"  SKIP {art.artifact_id} ({art.name}): only {len(history)} bench entries (need >= 2)")
            continue

        if art.type == "strategy":
            snapshot = compute_strategy_decay_snapshot(art.artifact_id, history, thresholds)
        else:
            snapshot = compute_decay_snapshot(art.artifact_id, history, thresholds)

        # get_snapshots() returns newest-first; transition_status needs
        # oldest-to-newest with the just-computed snapshot last, or
        # _n_consecutive's "last N" check reads the wrong end of the history.
        previous_snapshots = store.get_snapshots(art.artifact_id)
        eval_history = [s.evaluation for s in reversed(previous_snapshots)] + [snapshot.evaluation]

        new_status = transition_status(art.status, eval_history)
        changed = new_status != art.status

        status_icon = {
            "HEALTHY": "\u2713",
            "WARNING": "\u26a0",
            "DECAYED": "\u2717",
            "CRITICAL": "\u203c",
        }.get(snapshot.evaluation, "?")

        print(f"  {art.artifact_id} ({art.name})")
        print(f"    Status: {art.status.value} \u2192 {new_status.value if changed else '(unchanged)'}")
        if art.type == "strategy":
            print(f"    Eval: {status_icon} {snapshot.evaluation}  Sharpe_ratio={snapshot.ic_ratio:.2f}  Rolling_Sharpe={snapshot.rolling_sharpe:.2f}")
        else:
            print(f"    Eval: {status_icon} {snapshot.evaluation}  IC_ratio={snapshot.ic_ratio:.2f}  IR={snapshot.rolling_ir:.2f}  IC_pos={snapshot.ic_positive_ratio:.2f}  Sharpe={snapshot.rolling_sharpe:.2f}")
        print()

        if not dry_run:
            store.save_snapshot(snapshot)
            if changed:
                art.status = new_status
                store.upsert_artifact(art)
                if new_status == ArtifactStatus.DECAYED and art.universe:
                    symbol = art.universe[0]
                    LOG.info("Strategy %s decayed — triggering re-research for %s", art.artifact_id, symbol)
                    _trigger_re_research(symbol)

    return len(artifacts)


def decay_scan_main(args: argparse.Namespace) -> None:
    from vinu_research.config import DecayThresholds
    from vinu_research.storage.strategy_store import SqliteStrategyStore

    store = SqliteStrategyStore(_decay_db_path(args))
    try:
        _run_decay_scan(store, DecayThresholds(), dry_run=args.dry_run)
    finally:
        store.close()


def schedule_decay_main(args: argparse.Namespace) -> None:
    from vinu_research.config import DecayThresholds
    from vinu_research.storage.strategy_store import SqliteStrategyStore

    store = SqliteStrategyStore(_decay_db_path(args))
    thresholds = DecayThresholds()
    interval_sec = max(1, args.interval_hours) * 3600
    print(f"[schedule-decay] Running every {args.interval_hours}h. Press Ctrl+C to stop.\n")
    try:
        while True:
            _run_decay_scan(store, thresholds, dry_run=args.dry_run)
            time.sleep(interval_sec)
    except KeyboardInterrupt:
        print("\n[schedule-decay] Stopped.")
    finally:
        store.close()


def promote_scan_main(args: argparse.Namespace) -> None:
    """List BENCHING artifacts and promote those clearing the promotion bar.

    Deliberately not a `while True` scheduled worker like decay-scan/schedule-
    decay — auto-promoting a strategy to ACTIVE (where it starts influencing
    portfolio-api's weight computation) is a bigger consequence than auto-
    triggering more research, so this stays a command a human or agent
    invokes on purpose rather than a silent background loop.
    """
    from vinu_research.models import ArtifactStatus
    from vinu_research.promotion import meets_promotion_bar
    from vinu_research.storage.strategy_store import SqliteStrategyStore

    config = load_config()
    store = SqliteStrategyStore(_decay_db_path(args))
    try:
        benching = store.list_artifacts_by_statuses(statuses=[ArtifactStatus.BENCHING])
        if not benching:
            print("[promote-scan] No BENCHING artifacts found")
            return

        print(f"[promote-scan] Checking {len(benching)} BENCHING artifact(s) "
              f"(deflated_sharpe >= {config.promotion_deflated_sharpe_threshold:.2f}, "
              f"holdout_required={config.promotion_holdout_required})\n")
        for artifact in benching:
            verdict = meets_promotion_bar(artifact, config)
            print(f"  {artifact.artifact_id} ({artifact.name})")
            print(f"    deflated_sharpe={artifact.deflated_sharpe:.3f}  holdout_passed={artifact.holdout_passed}  "
                  f"stress_test_passed={artifact.stress_test_passed}")
            if verdict.eligible:
                print(f"    -> PROMOTE" + (" (dry-run, not persisted)" if args.dry_run else ""))
                if not args.dry_run:
                    artifact.status = ArtifactStatus.ACTIVE
                    store.upsert_artifact(artifact)
            else:
                print(f"    -> hold: {'; '.join(verdict.reasons)}")
            print()
    finally:
        store.close()


def ensure_main(args: argparse.Namespace) -> None:
    from vinu_research.service import ResearchService

    symbol = args.symbol.upper()
    from_date = _validate_date(args.from_date, "--from") or "2024-01-01"
    to_date = _validate_date(args.to_date, "--to") or "2024-12-31"
    idea: str | None = args.idea

    async def _run() -> dict:
        async with ResearchService() as svc:
            return await svc.ensure_strategy(idea, symbol, from_date, to_date)

    result = asyncio.run(_run())
    if result.get("skipped"):
        print(f"[ensure] {symbol} already has an active strategy — skipped ({result.get('reason')})")
    else:
        print(f"[ensure] Ran research for {symbol}: status={result.get('status')}, "
              f"best_sharpe={result.get('best_sharpe')}, best_max_dd={result.get('best_max_dd')}")


def recipes_main(args: argparse.Namespace) -> None:
    from vinu_research.generator import list_recipes
    print("Available strategy recipes:")
    for r in list_recipes():
        print(f"  - {r}")


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.WARN,
        format="%(levelname)s [%(name)s] %(message)s",
    )
    if hasattr(args, "func"):
        args.func(args)
    else:
        _parse_args(["--help"])
