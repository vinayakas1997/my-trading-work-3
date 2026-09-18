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
    concentration_coverage,
    consistency_freeze,
    correlation_coverage,
    debate_value,
    decision_process,
    event_holding_loss,
    ingest_health,
    loss_attribution,
    mandate_limit_friction,
    memory_effectiveness,
    paper_live_correlation,
    process_mining,
    rebalance_bypass,
    regime_drift,
    regime_strategy_coverage,
    screener_agreement,
    significance_response_outcome,
    skill_edit_governance,
    threshold_calibration,
    triage_freshness,
)

LOG = logging.getLogger("vinu.reflection.worker")

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
        # this service's own data root -- consistency_freeze.py (H,
        # consistency piece) persists its prior-cycle manifest here since
        # reflection_beliefs can't be trusted to hold it across a quiet
        # (routine, nothing-written) stretch.
        "vinu_reflection": config.data_root,
    }

    print(f"[reflection-worker] Starting (interval={interval}s, analysts={len(ANALYSTS)})")
    print("[reflection-worker] Press Ctrl+C to stop.\n")
    while True:
        written = run_cycle(reflection_store, data_root_paths)
        if written:
            print(f"[reflection-worker] cycle wrote {written} finding(s)")
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(prog="vinu-reflection")
    sub = parser.add_subparsers(dest="command", required=True)

    worker = sub.add_parser("worker", help="Run the reflection worker loop")
    worker.add_argument("--interval-sec", type=int, default=None)
    worker.set_defaults(func=reflection_worker_main)

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    args.func(args)


if __name__ == "__main__":
    main()
