"""vinu-reflection's CLI -- one worker loop, same real shape every other
worker in this codebase uses (`vinu-agent/vinu_agent/cli.py`'s
`skill_audit_worker_main`: `while True: cycle(); sleep()`), per
02-analyst-interface.md's worker-loop pseudocode.
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Any, Callable

from vinu_infra.reflection import Finding, ReflectionStore, write_findings

from vinu_reflection.config import load_config
from vinu_reflection.reflection import (
    angle_trust,
    brain,
    concentration_coverage,
    consistency_freeze,
    correlation_coverage,
    debate_value,
    decision_process,
    dl_angle_backtest_health,
    event_holding_loss,
    ingest_health,
    lesson_maturity_baseline_check,
    loss_attribution,
    mandate_limit_friction,
    memory_effectiveness,
    paper_live_correlation,
    process_mining,
    rebalance_bypass,
    regime_drift,
    regime_strategy_coverage,
    screener_agreement,
    shock_reading_before_halt,
    significance_response_outcome,
    skill_edit_governance,
    threshold_calibration,
    triage_freshness,
)

LOG = logging.getLogger("vinu.reflection.worker")


def serve_main(args: argparse.Namespace) -> None:
    """Step 9's HTTP surface -- see `server/app.py`'s own docstring for
    why this exists at all. Same `serve` shape every other service's
    `cli.py` already uses (e.g. `vinu-live/vinu_live/cli.py`)."""
    import uvicorn

    from vinu_reflection.server.app import create_app

    config = load_config()
    host = args.host or config.host
    port = args.port or config.port
    uvicorn.run(create_app(config), host=host, port=port)

# Adding a 7th analyst later is a one-line addition to this list and to
# _SEED_FNS below -- not a framework change (02-analyst-interface.md).
# D, L, M are the implementable "Decision-Process / Cognition" cluster
# analyses (04-decision-process-cognition.md; K is blocked -- see that
# file). A is the first "Forecast Intelligence" cluster analysis
# (01-forecast-intelligence.md; Q/P/G/S not attempted, see that file).
# C is the first "Execution & Money-Flow" cluster analysis
# (03-execution-money-flow.md). E (pair piece only) is the first
# "Regime & Risk Coverage" cluster analysis (02-regime-risk-coverage.md).
# H (governance piece only) is the first "Governance & Freshness" cluster
# analysis (05-governance-freshness.md). I/X are both implemented in
# screener_agreement.run() (06-external-signal-cross-check.md).
# concentration_coverage.run() is E's concentration piece (the pair
# piece is correlation_coverage.run()). threshold_calibration.run() is W
# (bracket_partial/rebalance_protect checkpoints only -- the design doc's
# third named checkpoint has no real call site, see that module's
# docstring). consistency_freeze.run() is H's consistency piece (the
# governance piece is skill_edit_governance.run()). ingest_health.run()
# is P+G merged into one per-ticker row -- the 2026-09-19 "blocked"
# verdict for both in 01-forecast-intelligence.md was a documentation
# error (calibration_entries.timestamp IS populated by a real writer),
# corrected and built 2026-09-19, see that module's docstring.
# paper_live_correlation.run() is V -- its own two blockers (a
# `promoted_at` timestamp, a Pearson-correlation helper) turned out to
# both be non-issues/small additions once investigated, see that
# module's docstring. regime_strategy_coverage.run() is B -- its
# `strategy_family` taxonomy blocker resolved by adding
# Artifact.strategy_family (vinu-research), classified from
# ResearchRunRecord.user_idea, see that module's docstring.
# memory_effectiveness.run() is K -- its missing-writer blocker resolved
# by adding InjectedContextLogStore (vinu-agent), written once per
# ContextBuilder.build_messages() call, see that module's docstring.
# rebalance_bypass.run() is U, event_holding_loss.run() is Y,
# mandate_limit_friction.run() is O, triage_freshness.run() is R -- all
# four built 2026-09-20 once the user explicitly signed off on their new
# writers (rebalance_request_history, events_archive,
# GuardResult.blocked_artifact_ids, the live Planner-triage freshness
# hook). Each writer only started collecting data 2026-09-20, so these
# four will write nothing until real production evidence accumulates
# past each one's MIN_EVIDENCE_COUNT floor -- registered now so they're
# ready to work correctly the moment it does, rather than needing a
# second build pass later. See each module's own docstring.
# regime_drift.run() is J -- its original framing (regime_tag relabeling
# events) was a dead end (regime_tag never changes after artifact
# creation), reframed around the real, already-computed
# market_regime_analogue.get_market_regime_stats_for_today() signal, which
# just had no durable home until MarketRegimeHistoryStore (vinu-research,
# new) was added 2026-09-20 on explicit user sign-off. Sparser than the
# other four above (only accumulates when regime_analogue_enabled is on
# and a trade plan is actually authored that day) but the same
# MIN_EVIDENCE_COUNT-style windowing makes it safe to register now. See
# that module's own docstring.
# significance_response_outcome.run() is F -- "not attempted, 2026-09-19"
# because "downstream outcomes for the flagged tickers" wasn't a checked,
# concrete join yet. Checked 2026-09-20: significance_flags already has
# ticker + created_at, a real (if weak) join to trade_audit_log.jsonl's
# exit rows, same shape as U's rebalance-bypass join -- the only real gap
# was SignificanceFlagStore having no way to read every flag (added
# all_flags()). No schema change needed after all. See that module's own
# docstring.
# dl_angle_backtest_health.run() is Q, shock_reading_before_halt.run() is
# N -- both re-investigated 2026-09-20 and found to be worse than a
# "dependency-cost" problem, not better: Q's whole premise (a live model
# checkpoint's real trade outcomes) has no real referent anywhere in
# production (weights_ref only exists in an offline backtest path, never
# threaded to a live forecast); N's data is reachable without the heavy
# import, but only via live HTTP to a running service. Both reframed
# around what's actually real and read via
# `_initial_analysis_parquet.py` (pandas/pyarrow only, never installs
# vinu_initial_analysis itself) -- Q around the angle's own backtest-
# accuracy trend, N around the nearest quarterly shock-reading snapshot
# before a real halt. See each module's own docstring.
# lesson_maturity_baseline_check.run() is T -- structurally blocked until
# 2026-09-20, when `_maturity_assessor.py` (new, not itself a
# Finding-writing analyst -- a shared, importable read-model per
# 00-maturity-agentic-system-explanation.md) gave T something real to
# compare vinu-live's LESSON snapshots against. Compares LESSON's own
# crude last5 win/loss read against MaturityAssessor's own same-shaped
# "recent form" read (both real, both intentionally crude, matching the
# design doc's own "both sides are already summary judgments" framing) --
# not the persisted tier itself, which the design doc explicitly forbids
# storing as a new trend series. See both modules' own docstrings.
AnalystFn = Callable[[dict[str, Path], dict[str, Any]], list[Finding]]
ANALYSTS: list[AnalystFn] = [
    decision_process.run,
    process_mining.run,
    debate_value.run,
    angle_trust.run,
    ingest_health.run,
    loss_attribution.run,
    memory_effectiveness.run,
    rebalance_bypass.run,
    event_holding_loss.run,
    mandate_limit_friction.run,
    triage_freshness.run,
    regime_drift.run,
    significance_response_outcome.run,
    dl_angle_backtest_health.run,
    shock_reading_before_halt.run,
    lesson_maturity_baseline_check.run,
    correlation_coverage.run,
    paper_live_correlation.run,
    regime_strategy_coverage.run,
    skill_edit_governance.run,
    screener_agreement.run,
    concentration_coverage.run,
    threshold_calibration.run,
    consistency_freeze.run,
]
_SEED_FNS: list[Callable[[ReflectionStore], None]] = [
    decision_process.seed_reference_config,
    process_mining.seed_reference_config,
    debate_value.seed_reference_config,
    angle_trust.seed_reference_config,
    ingest_health.seed_reference_config,
    loss_attribution.seed_reference_config,
    memory_effectiveness.seed_reference_config,
    rebalance_bypass.seed_reference_config,
    event_holding_loss.seed_reference_config,
    mandate_limit_friction.seed_reference_config,
    triage_freshness.seed_reference_config,
    regime_drift.seed_reference_config,
    significance_response_outcome.seed_reference_config,
    dl_angle_backtest_health.seed_reference_config,
    shock_reading_before_halt.seed_reference_config,
    lesson_maturity_baseline_check.seed_reference_config,
    correlation_coverage.seed_reference_config,
    paper_live_correlation.seed_reference_config,
    regime_strategy_coverage.seed_reference_config,
    skill_edit_governance.seed_reference_config,
    screener_agreement.seed_reference_config,
    concentration_coverage.seed_reference_config,
    threshold_calibration.seed_reference_config,
    consistency_freeze.seed_reference_config,
]


def run_cycle(
    reflection_store: ReflectionStore,
    data_root_paths: dict[str, Path],
    service_clients: dict[str, Any] | None = None,
) -> int:
    """One pass over every registered analyst. Each analyst's failure is
    isolated -- a broken analyst can't stop the rest of this cycle's run
    (05-to-do.md #7) -- on top of the structural isolation that already
    holds because every analyst is a pure function with no shared state.
    Returns how many findings were actually written this cycle (routine
    findings don't count -- most cycles, most scopes, write nothing)."""
    written = 0
    for analyst_fn in ANALYSTS:
        try:
            findings = analyst_fn(data_root_paths, service_clients or {})
            written += len(write_findings(reflection_store, findings))
        except Exception:
            LOG.exception("[reflection-worker] %s failed, skipping", analyst_fn.__module__)
    return written


def resolve_worker_interval(args: argparse.Namespace | None, config) -> int:
    return args.interval_sec if args and args.interval_sec else config.worker_interval_sec


def reflection_worker_main(args: argparse.Namespace) -> None:
    config = load_config()
    interval = resolve_worker_interval(args, config)
    reflection_store = ReflectionStore(config.data_root / "reflection.db")
    for seed_fn in _SEED_FNS:
        seed_fn(reflection_store)
    data_root_paths = {
        "vinu_agent": config.agent_data_root,
        "vinu_live": config.live_trade_audit_log_path.parent,
        "vinu_screener": config.screener_data_root,
        "vinu_portfolio": config.portfolio_data_root,
        "vinu_stock": config.stock_data_root,
        # A *data* mount only (2026-09-20, Q/N) -- never an install of
        # vinu_initial_analysis itself. See
        # vinu_reflection/reflection/_initial_analysis_parquet.py.
        "vinu_initial_analysis": config.initial_analysis_data_root,
        # this service's own data root -- consistency_freeze.py (H,
        # consistency piece) persists its prior-cycle manifest here since
        # reflection_beliefs can't be trusted to hold it across a quiet
        # (routine, nothing-written) stretch.
        "vinu_reflection": config.data_root,
    }

    # Step 8 ("the brain") -- opt-in, off by default. Constructing the LLM
    # client only when enabled means the `openai` dependency (or whichever
    # provider) never has to be installed for a deployment that never
    # turns this on -- same "ships inert" posture every other opt-in
    # feature in this codebase already uses.
    brain_llm = None
    if config.brain_synthesis_enabled:
        from vinu_agent.agent.llm import create_llm_from_config
        from vinu_agent.config import load_config as load_agent_config

        brain_llm = create_llm_from_config(load_agent_config().llm)
    last_brain_run = 0.0

    print(f"[reflection-worker] Starting (interval={interval}s, analysts={len(ANALYSTS)})")
    print("[reflection-worker] Press Ctrl+C to stop.\n")
    while True:
        written = run_cycle(reflection_store, data_root_paths)
        if written:
            print(f"[reflection-worker] cycle wrote {written} finding(s)")
        if brain_llm is not None:
            now = time.time()
            if now - last_brain_run >= config.brain_synthesis_worker_interval_sec:
                try:
                    resolved = brain.resolve_pending_syntheses(reflection_store)
                    if resolved:
                        print(f"[reflection-brain] resolved {resolved} pending synthesis outcome(s)")
                    synthesis_id = brain.run_synthesis(
                        reflection_store, brain_llm, data_root_paths=data_root_paths,
                    )
                    if synthesis_id:
                        print(f"[reflection-brain] wrote synthesis {synthesis_id}")
                except Exception:
                    LOG.exception("[reflection-brain] cycle failed, skipping")
                last_brain_run = now
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(prog="vinu-reflection")
    sub = parser.add_subparsers(dest="command", required=True)

    worker = sub.add_parser("worker", help="Run the reflection worker loop")
    worker.add_argument("--interval-sec", type=int, default=None)
    worker.set_defaults(func=reflection_worker_main)

    serve = sub.add_parser("serve", help="Start the read-only HTTP API (Step 9)")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    serve.set_defaults(func=serve_main)

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    args.func(args)


if __name__ == "__main__":
    main()
