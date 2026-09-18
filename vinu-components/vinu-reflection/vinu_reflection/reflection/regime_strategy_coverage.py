"""Analysis B -- regime x strategy coverage map: per strategy_family, has
real closed-trade coverage newly appeared or its outcome quality drifted,
broken down by the regime each trade closed under. Design reference:
missing-pieces-of-system/maturity-agentic-system/thinking-1/02-decided-
pattern/25-A-Y-details/02-regime-risk-coverage.md ("B").

**The taxonomy blocker, resolved 2026-09-19**: the design doc's own
verdict said `strategy_family` had no real categorical concept anywhere,
and that `Artifact.type`/`signal_definition` couldn't provide one
(`Artifact.type` is a coarse kind flag; `signal_definition` has no real
writer at all -- confirmed empty on every real artifact today). Resolved
by adding `Artifact.strategy_family` (`vinu-research/vinu_research/
models.py`), classified once at creation time from `ResearchRunRecord.
user_idea` via the new `vinu_research.strategy_family.classify_strategy_
family()` -- a small, fixed, grounded taxonomy (momentum, mean_reversion,
breakout, volatility, stat_arb, event_driven, unclassified), the same
"research external convention, pick something grounded, document the
reasoning" resolution `03-severity-and-trend.md`/`04-reference-baseline-
config.md` used for the PSI-threshold questions. See that module's own
docstring for the full reasoning and keyword list.

**Forward-only, same contract as regime_tag/freeze_hash/timeframe**: only
artifacts created after this field existed carry a real
`strategy_family` -- never backfilled. Artifacts with `strategy_family ==
""` (pre-existing, or a "strategy" artifact from before this pass) are
excluded from every cross-tab cell rather than lumped into a fake
`"unclassified"` bucket that would conflate "we don't know" with "the
research run genuinely stated no style."

**Real join and scope-down, documented**: the design doc's Fetch also
lists `bench_history` (`ic, ir, ic_positive, sharpe`) as a source.
`bench_history` is a per-artifact *backtest*-time series (appended once
per approved research run, not per real trade) -- it cannot answer a
per-(strategy_family, regime_tag) cross-tab of *real* closed-trade
outcomes, which is what this analysis is actually about. Uses
`trade_audit_log.jsonl`'s real exit rows instead (`artifact_id`,
`realized_pnl`, both confirmed populated at every real write site in
`vinu-live/vinu_live/trade_plan/orchestrator.py`), joined to
`Artifact.strategy_family`/`regime_tag` via `artifact_id`. `ic`
(information coefficient) is dropped from the per-regime breakdown --
it needs per-forecast expected-value data trade_audit_log doesn't carry,
same "drop the field with no real substitute" scoping already applied to
C/H. The per-cell figure reported is a raw reward-to-variability ratio
(mean/std of realized_pnl over the window), not an annualized Sharpe
ratio -- real trade holding periods vary, so there's no single
annualization factor to apply, same honesty already given to C's own
loss-rate metric.

Windowing follows every other trailing-comparison analysis in this
service (two adjacent windows, PSI on the raw realized_pnl values) --
the natural way a cell's evidence_count also organically satisfies the
Condition's "crosses a minimum real-sample floor... for the first time"
half: nothing is written for a family until it first accumulates
`CURRENT_WINDOW + MIN_REFERENCE_WINDOW` real trades, so the first Finding
for a family already is that crossing event.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from vinu_infra.reflection import (
    Finding,
    POLARITY_LOWER_IS_WORSE,
    population_stability_index,
)
from vinu_infra.trade_audit_log import read_all

from vinu_agent.broker.research_link import get_strategy_store

ANALYST_NAME = "regime_risk_coverage"
CLUSTER = "Regime & Risk Coverage"
METRIC_NAME = "family_outcome_trend"

# Real-sample floors, small deliberately -- a single strategy_family's
# real closed trades are scarcer than the whole-system trade stream every
# other execution-side analyst (C/loss_attribution) draws on. Matches the
# design doc's own "e.g. <5 real closed trades" minimum-sample language.
CURRENT_WINDOW = 5
REFERENCE_WINDOW_MAX = 15
MIN_REFERENCE_WINDOW = 5


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _reward_to_variability(pnls: list[float]) -> float:
    if len(pnls) < 2:
        return 0.0
    mean = _mean(pnls)
    variance = sum((p - mean) ** 2 for p in pnls) / (len(pnls) - 1)
    std = variance ** 0.5
    return mean / std if std else 0.0


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    """`data_root_paths["vinu_live"]` must point at a mounted copy of
    vinu-live's own data root (docker-compose.yml mounts `./data/live`
    read-only into this service at `/live-data`) -- same mount
    `loss_attribution.py` (C) already established."""
    log_path = Path(data_root_paths["vinu_live"]) / "trade_audit_log.jsonl"
    rows = read_all(log_path=log_path)

    strategy_store = get_strategy_store()
    artifact_cache: dict[str, Any] = {}

    def _artifact_for(artifact_id: str):
        if artifact_id not in artifact_cache:
            artifact_cache[artifact_id] = strategy_store.get_artifact(artifact_id)
        return artifact_cache[artifact_id]

    # family -> chronologically ordered list of (realized_pnl, regime_tag).
    by_family: dict[str, list[tuple[float, str]]] = defaultdict(list)

    for row in rows:
        if row.get("event") != "exit":
            continue
        artifact_id = row.get("artifact_id")
        realized_pnl = row.get("realized_pnl")
        if not artifact_id or realized_pnl is None:
            continue
        artifact = _artifact_for(artifact_id)
        # Excluded, not "unclassified" -- see module docstring: this
        # artifact predates the field or its run stated no real style.
        if artifact is None or not artifact.strategy_family:
            continue
        by_family[artifact.strategy_family].append(
            (float(realized_pnl), artifact.regime_tag or "")
        )

    findings: list[Finding] = []
    for family, trades in by_family.items():
        if len(trades) < CURRENT_WINDOW + MIN_REFERENCE_WINDOW:
            continue

        window = trades[-(CURRENT_WINDOW + REFERENCE_WINDOW_MAX):]
        current = window[-CURRENT_WINDOW:]
        reference = window[:-CURRENT_WINDOW]
        if len(reference) < MIN_REFERENCE_WINDOW:
            continue

        current_pnls = [pnl for pnl, _ in current]
        reference_pnls = [pnl for pnl, _ in reference]
        current_rvr = _reward_to_variability(current_pnls)
        reference_rvr = _reward_to_variability(reference_pnls)
        delta = current_rvr - reference_rvr

        psi = population_stability_index(reference_pnls, current_pnls)

        regime_totals: dict[str, list[float]] = defaultdict(list)
        for pnl, regime_tag in current:
            regime_totals[regime_tag].append(pnl)
        regime_breakdown = {
            regime_tag: {"n": len(pnls), "reward_to_variability": _reward_to_variability(pnls)}
            for regime_tag, pnls in regime_totals.items()
        }

        findings.append(
            Finding(
                analyst_name=ANALYST_NAME,
                cluster=CLUSTER,
                scope_type="strategy_family",
                scope_key=family,
                signal_json={
                    "regime_breakdown": regime_breakdown,
                    "current_reward_to_variability": current_rvr,
                    "reference_reward_to_variability": reference_rvr,
                },
                evidence_count=len(window),
                primary_metric=delta,
                metric_name=METRIC_NAME,
                psi=psi,
                narrative=(
                    f"{family}: reward/variability {current_rvr:.3f} (latest "
                    f"{CURRENT_WINDOW} trades) vs. {reference_rvr:.3f} (prior {len(reference)})"
                ),
            )
        )
    return findings


def seed_reference_config(reflection_store) -> None:
    """Idempotent, same posture as every other analyst's
    seed_reference_config in this service."""
    reflection_store.upsert_reference_config(
        analyst_name=ANALYST_NAME,
        scope_type="strategy_family",
        metric_name=METRIC_NAME,
        metric_polarity=POLARITY_LOWER_IS_WORSE,
        reference_window_definition="trailing_15_closed_trades_before_the_latest_5_for_this_family",
        reason="B: a lower reward-to-variability ratio for a strategy family's real closed trades is worse",
        updated_by=ANALYST_NAME,
    )
