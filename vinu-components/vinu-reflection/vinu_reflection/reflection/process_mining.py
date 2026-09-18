"""Analysis L -- process-mining the agent's own reasoning traces. Per
`team_name`, checks whether attempts with a long `react_trace` actually
produce better outcomes than short ones, or just burn more calls for the
same result. Design reference:
missing-pieces-of-system/maturity-agentic-system/thinking-1/02-decided-pattern/
25-A-Y-details/04-decision-process-cognition.md ("L").

Real join used (not a direct FK -- `Attempt` has no `team_name` field):
`Attempt.session_id == TeamRun.triggered_by_session_id`, then
`TeamRun.related_artifact_id -> calibration_entries` (vinu-research, read
in-process via vinu-agent's own `research_link.get_strategy_store()`,
same posture as decision_process.py's mount-and-import for llm_calls/
team_runs). A session can trigger more than one team run, and more than
one attempt can share a session -- every (attempt, matching team_run)
pair is counted once, same "best-available approximate join" posture
`TeamRunStore.get_latest_verdict_by_session_id` already documents for D.
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

from vinu_agent.broker.research_link import get_strategy_store
from vinu_agent.session.store import SessionStore
from vinu_agent.storage.team_runs import STATUS_DONE, TeamRunStore

ANALYST_NAME = "decision_process"
CLUSTER = "Decision-Process / Cognition"
METRIC_NAME = "trace_length_outcome_correlation"

# Combined (has-outcome-data) sample floor per team, same order of
# magnitude as D's MIN_EVIDENCE_COUNT (30) -- validated by
# 03-severity-and-trend.md's cited ~100-180-observation window research
# as the right floor for a comparison this granular, not a full window.
MIN_EVIDENCE_COUNT = 30
# Each of the top-quartile/bottom-quartile buckets must independently
# clear this floor too, or a 30-sample team with a skewed trace-length
# distribution could compare 28 attempts against 2.
MIN_GROUP_SIZE = 10


def _quantile(sorted_values: list[float], q: float) -> float:
    n = len(sorted_values)
    idx = min(n - 1, max(0, round(q * (n - 1))))
    return sorted_values[idx]


def _artifact_outcome_quality(strategy_store, artifact_id: str) -> Optional[float]:
    """Mean `directional_correct` across every calibration entry for this
    artifact -- an already-computed field (not invented here), the same
    "was the forecast right" signal calibration.py exists to produce."""
    entries = strategy_store.get_calibration_entries(artifact_id)
    if not entries:
        return None
    return sum(1.0 if e.directional_correct else 0.0 for e in entries) / len(entries)


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    data_root = Path(data_root_paths["vinu_agent"])
    session_store = SessionStore(data_root / "sessions")
    team_store = TeamRunStore(data_root / "team_runs.db")
    strategy_store = get_strategy_store()

    # team_name -> list of (trace_length, outcome_quality)
    samples: dict[str, list[tuple[float, float]]] = defaultdict(list)

    for attempt in session_store.list_all_attempts():
        if not attempt.session_id:
            continue
        trace_length = float(len(attempt.react_trace or []))
        for team_run in team_store.list_by_session_id(attempt.session_id):
            if team_run.status != STATUS_DONE or not team_run.related_artifact_id:
                continue
            quality = _artifact_outcome_quality(strategy_store, team_run.related_artifact_id)
            if quality is None:
                continue
            samples[team_run.team_name].append((trace_length, quality))

    findings: list[Finding] = []
    for team_name, pairs in samples.items():
        evidence_count = len(pairs)
        if evidence_count < MIN_EVIDENCE_COUNT:
            continue

        lengths = sorted(length for length, _ in pairs)
        p75 = _quantile(lengths, 0.75)
        p25 = _quantile(lengths, 0.25)
        top_quality = [quality for length, quality in pairs if length >= p75]
        bottom_quality = [quality for length, quality in pairs if length <= p25]
        if len(top_quality) < MIN_GROUP_SIZE or len(bottom_quality) < MIN_GROUP_SIZE:
            continue

        top_mean = sum(top_quality) / len(top_quality)
        bottom_mean = sum(bottom_quality) / len(bottom_quality)
        # Signed: positive -- long-trace attempts do better; negative --
        # long-trace attempts underperform short ones (the concerning
        # case this analysis exists to catch). Matches
        # 04-reference-baseline-config.md's `lower_is_worse` polarity for
        # this exact metric.
        delta = top_mean - bottom_mean

        psi = population_stability_index(
            bottom_quality, top_quality, bin_count=2, min_samples_per_bin=1
        )

        findings.append(
            Finding(
                analyst_name=ANALYST_NAME,
                cluster=CLUSTER,
                scope_type="system",
                scope_key=team_name,
                signal_json={
                    "trace_length_outcome_correlation": delta,
                    "long_trace_quality": top_mean,
                    "short_trace_quality": bottom_mean,
                    "long_trace_p75_threshold": p75,
                    "short_trace_p25_threshold": p25,
                    "long_trace_evidence_count": len(top_quality),
                    "short_trace_evidence_count": len(bottom_quality),
                },
                evidence_count=evidence_count,
                primary_metric=delta,
                metric_name=METRIC_NAME,
                psi=psi,
                narrative=(
                    f"{team_name}: long-trace (>=P75) outcome quality {top_mean:.2f} vs. "
                    f"short-trace (<=P25) {bottom_mean:.2f}"
                ),
            )
        )
    return findings


def seed_reference_config(reflection_store) -> None:
    """Idempotent, same posture as decision_process.seed_reference_config
    and `vinu-screener seed-default`."""
    reflection_store.upsert_reference_config(
        analyst_name=ANALYST_NAME,
        scope_type="system",
        metric_name=METRIC_NAME,
        metric_polarity=POLARITY_LOWER_IS_WORSE,
        reference_window_definition="all_attempts_with_a_calibrated_outcome",
        reason="L: long-trace attempts underperforming short ones is the failure mode this analysis exists to catch",
        updated_by=ANALYST_NAME,
    )
