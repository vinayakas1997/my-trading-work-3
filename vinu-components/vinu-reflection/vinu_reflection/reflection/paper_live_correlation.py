"""Analysis V -- paper-vs-live performance predictor: does an artifact's
paper-trading return actually predict its subsequent live return, across
every artifact that ever went from paper trading to real capital. Design
reference: missing-pieces-of-system/maturity-agentic-system/thinking-1/
02-decided-pattern/25-A-Y-details/02-regime-risk-coverage.md ("V").

**Investigated 2026-09-19, then built the same day once the two blockers
that note recorded were resolved**:

1. *A `promoted_at`-equivalent timestamp*, thought to be needed to split
   `paper_performance.returns_json` into a paper-period and a
   live-period. Turned out not to be needed at all: `PaperPerformanceStore.
   record_daily_return(s)` (`vinu-agent/vinu_agent/broker/performance_
   store.py`) has exactly one real writer anywhere in the codebase --
   `ShadowEvaluator.record_daily_paper_returns()`
   (`vinu-live/vinu_live/shadow_evaluator.py`) -- and that method only
   ever iterates `_list_benching_artifacts()` (`status=BENCHING`). So
   `paper_performance` is *structurally* paper-period-only: nothing ever
   appends to it once an artifact leaves BENCHING. `calibration_entries`
   (`vinu-research`), on the other side, is only ever populated by
   `record_realized_outcome()` for closed *live* broker positions
   (vinu-live's `feedback_loop.py`, reading `list_closed_positions()` off
   the real position book) -- paper-trading never touches it. The two
   stores are already cleanly split by construction; no new field, no
   join needed. An artifact showing up in both is, by construction, one
   that was promoted.
2. *A Pearson-correlation helper* -- added,
   `vinu_infra.reflection.pearson_correlation()` (first real user).

**Real scope-down from the design doc's Condition, documented**: grouped
`scope_type=strategy_family` in the design doc, same as B -- which still
has no real `strategy_family` categorical concept anywhere in this
codebase (`01-forecast-intelligence.md`'s own B verdict). Scoped down to
one `scope_type=system` row across every promoted artifact instead of a
per-family breakdown, same "don't invent B's taxonomy here" posture C/E's
concentration piece already took. Revisit per-family once B is resolved.

**Real substitution for significance, documented**: the design doc's
Condition is "the correlation coefficient... moves outside its own
trailing band... recomputed each cycle from the full history" -- a
single scalar recomputed fresh every cycle, not two adjacent windows of
raw values the way every other PSI-based analyst here compares. There is
no natural two-distribution PSI comparison for "has one number drifted
between cycles" (that's `compute_trend`'s job, already handled centrally
by `write_finding()` diffing this cycle's `primary_metric` against the
prior belief's). What still needs a `psi` value is the write/no-write
significance gate itself, so PSI is instead computed between the
paper-return distribution and the live-return distribution across all
promoted artifacts -- a real, related question ("how far has the live
outcome distribution diverged from what paper predicted") that this
service's existing PSI machinery can actually answer, while the named
correlation coefficient itself is still the tracked `primary_metric`
(and the exact value `signal_json` reports). The domain-meaningful
"correlation <= 0" line from the Condition is implemented directly as
`domain_floor_breached`, forcing `significant` the same way A's Brier
floor does.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from vinu_infra.reflection import (
    Finding,
    POLARITY_LOWER_IS_WORSE,
    pearson_correlation,
    population_stability_index,
)
from vinu_agent.broker.performance_store import PaperPerformanceStore

from vinu_agent.broker.research_link import get_strategy_store

ANALYST_NAME = "regime_risk_coverage"
CLUSTER = "Regime & Risk Coverage"
METRIC_NAME = "paper_live_correlation"

# Same default ShadowEvaluator itself gates promotion on
# (`min_paper_days`) -- an artifact with fewer paper days than that was
# never itself trusted enough to promote, so its paper average isn't a
# meaningful predictor input either.
MIN_PAPER_DAYS = 5
MIN_LIVE_ENTRIES = 1
# ">=5 promoted artifacts" -- the design doc's own minimum-sample floor.
MIN_SAMPLE_ARTIFACTS = 5


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    """`data_root_paths["vinu_agent"]` must point at a mounted copy of
    vinu-agent's own data root (docker-compose.yml mounts `./data/agent`
    read-only into this service at `/agent-data`) -- same mount
    `decision_process.py` already established for vinu-agent."""
    agent_data_root = Path(data_root_paths["vinu_agent"])
    performance_store = PaperPerformanceStore(agent_data_root / "paper_performance.db")
    strategy_store = get_strategy_store()

    paper_avgs: list[float] = []
    live_avgs: list[float] = []
    for artifact_id, paper_returns in performance_store.get_all().items():
        if len(paper_returns) < MIN_PAPER_DAYS:
            continue
        calib_entries = strategy_store.get_calibration_entries(artifact_id)
        if len(calib_entries) < MIN_LIVE_ENTRIES:
            continue
        paper_avgs.append(_mean(paper_returns))
        live_avgs.append(_mean([e.actual_return_pct for e in calib_entries]))

    n_promoted = len(paper_avgs)
    if n_promoted < MIN_SAMPLE_ARTIFACTS:
        return []

    correlation = pearson_correlation(paper_avgs, live_avgs)
    psi = population_stability_index(paper_avgs, live_avgs)

    return [
        Finding(
            analyst_name=ANALYST_NAME,
            cluster=CLUSTER,
            scope_type="system",
            scope_key="paper_vs_live_performance",
            signal_json={
                "paper_live_correlation": correlation,
                "n_promoted_artifacts": n_promoted,
            },
            evidence_count=n_promoted,
            primary_metric=correlation,
            metric_name=METRIC_NAME,
            psi=psi,
            domain_floor_breached=correlation <= 0,
            narrative=(
                f"paper-vs-live return correlation across {n_promoted} "
                f"promoted artifacts: {correlation:+.3f}"
            ),
        )
    ]


def seed_reference_config(reflection_store) -> None:
    """Idempotent, same posture as every other analyst's
    seed_reference_config in this service."""
    reflection_store.upsert_reference_config(
        analyst_name=ANALYST_NAME,
        scope_type="system",
        metric_name=METRIC_NAME,
        metric_polarity=POLARITY_LOWER_IS_WORSE,
        reference_window_definition="all_promoted_artifacts_with_paper_and_live_history",
        reason=(
            "V: a lower (or negative) paper-vs-live return correlation means "
            "paper performance predicts real performance less well"
        ),
        updated_by=ANALYST_NAME,
    )
