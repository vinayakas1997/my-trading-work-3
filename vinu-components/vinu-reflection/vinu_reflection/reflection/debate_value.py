"""Analysis M -- does the investment-committee debate earn its cost.
Compares realized outcome quality for trade-plan artifacts that did vs.
didn't fold in an `investment_committee` swarm debate before authoring.
Design reference:
missing-pieces-of-system/maturity-agentic-system/thinking-1/02-decided-pattern/
25-A-Y-details/04-decision-process-cognition.md ("M").

**Correction to the original design's join, found while implementing**:
the swarm run's own `run_id` is never persisted into `trade_plan_data`/
`origin_angles` (`SignalEntry` -- vinu-research/vinu_research/models.py
-- has no `run_id` field). The real, available signal is simpler and
doesn't need the swarm store at all: `trade_plan_authoring.py`'s
`fetch_debate_signal` (when `config.debate_signal_enabled`) appends one
`SignalEntry` with `source="investment_committee"` into
`forecast.signals` before the plan is frozen into `Artifact.trade_plan_data`
(JSON). Presence/absence of that one signal, per artifact, is exactly
"did vs. didn't fold in a completed debate" -- a real, ID-free join.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from vinu_infra.reflection import (
    Finding,
    POLARITY_LOWER_IS_WORSE,
    population_stability_index,
)

from vinu_agent.broker.research_link import get_strategy_store

ANALYST_NAME = "decision_process"
CLUSTER = "Decision-Process / Cognition"
METRIC_NAME = "with_debate_outcome_delta"
SCOPE_KEY = "investment_committee"

# "a minimum sample (e.g. 10 debated artifacts)" -- 04-decision-process-
# cognition.md's own placeholder, applied to both groups (a comparison
# needs a real "without" baseline too, not just enough "with" evidence).
MIN_GROUP_SIZE = 10

_DEBATE_SOURCE = "investment_committee"


def _has_debate_signal(trade_plan_data: str) -> bool:
    try:
        data = json.loads(trade_plan_data) if trade_plan_data else {}
    except (json.JSONDecodeError, TypeError):
        return False
    signals = (data.get("forecast") or {}).get("signals") or []
    return any(s.get("source") == _DEBATE_SOURCE for s in signals)


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    strategy_store = get_strategy_store()

    with_debate: list[float] = []
    without_debate: list[float] = []
    for artifact in strategy_store.list_artifacts(type_="trade_plan"):
        if not artifact.trade_plan_data:
            continue
        entries = strategy_store.get_calibration_entries(artifact.artifact_id)
        if not entries:
            continue
        quality = sum(1.0 if e.directional_correct else 0.0 for e in entries) / len(entries)
        target = with_debate if _has_debate_signal(artifact.trade_plan_data) else without_debate
        target.append(quality)

    if len(with_debate) < MIN_GROUP_SIZE or len(without_debate) < MIN_GROUP_SIZE:
        return []

    with_mean = sum(with_debate) / len(with_debate)
    without_mean = sum(without_debate) / len(without_debate)
    # Signed: negative -- debated artifacts underperform undebated ones
    # (the debate isn't earning its cost). Matches
    # 04-reference-baseline-config.md's `lower_is_worse` polarity.
    delta = with_mean - without_mean

    psi = population_stability_index(without_debate, with_debate, bin_count=2, min_samples_per_bin=1)

    finding = Finding(
        analyst_name=ANALYST_NAME,
        cluster=CLUSTER,
        scope_type="system",
        scope_key=SCOPE_KEY,
        signal_json={
            "with_debate_outcome": with_mean,
            "without_debate_outcome": without_mean,
            "n_debated": len(with_debate),
            "n_undebated": len(without_debate),
        },
        evidence_count=len(with_debate) + len(without_debate),
        primary_metric=delta,
        metric_name=METRIC_NAME,
        psi=psi,
        narrative=(
            f"investment_committee debate: with-debate outcome quality {with_mean:.2f} "
            f"vs. without {without_mean:.2f} ({len(with_debate)} debated artifacts)"
        ),
    )
    return [finding]


def seed_reference_config(reflection_store) -> None:
    """Idempotent, same posture as decision_process.seed_reference_config
    and `vinu-screener seed-default`."""
    reflection_store.upsert_reference_config(
        analyst_name=ANALYST_NAME,
        scope_type="system",
        metric_name=METRIC_NAME,
        metric_polarity=POLARITY_LOWER_IS_WORSE,
        reference_window_definition="all_trade_plan_artifacts_with_a_calibrated_outcome",
        reason="M: a debate that isn't improving outcomes isn't earning its LLM cost",
        updated_by=ANALYST_NAME,
    )
