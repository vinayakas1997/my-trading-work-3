"""Analysis A -- angle trust trajectories. Per angle, checks whether its
brier_score has genuinely drifted between an older reference window and
its most recent entries, plus a hard domain-floor check (a forecaster
worse than random needs no drift to be significant). Design reference:
missing-pieces-of-system/maturity-agentic-system/thinking-1/02-decided-pattern/
25-A-Y-details/01-forecast-intelligence.md ("A").

**Implementation note on the Condition**: the design doc's original
phrasing ("trailing-30-entry mean brier_score moves outside its own
trailing-90-entry P10/P90 band") describes a scalar-vs-percentile-band
test. Implemented instead as two adjacent, non-overlapping windows
(reference = the up-to-90 entries immediately before the most recent
30, current = the most recent 30) compared via the same shared PSI
machinery every other analyst in this service already uses
(`vinu_infra.reflection.population_stability_index`) -- reuses proven,
tested code instead of adding a second significance-testing mechanism
for one analysis, and PSI's own "how much did this distribution move"
question is a strict generalization of a percentile-band check, not a
different question.

`ticker_cluster_breakdown` (the second half of the original `signal_json`
shape, from `artifacts.universe`) was not implemented -- scoped down to
`regime_breakdown` only, same "build what's real and tested, not every
listed field" posture already applied to D/L's `signal_json` scope-downs.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from vinu_infra.reflection import (
    Finding,
    POLARITY_HIGHER_IS_WORSE,
    population_stability_index,
)

from vinu_agent.broker.research_link import get_strategy_store

ANALYST_NAME = "forecast_intelligence"
CLUSTER = "Forecast Intelligence"
METRIC_NAME = "brier_trend"

CURRENT_WINDOW = 30
REFERENCE_WINDOW_MAX = 90
MIN_REFERENCE_WINDOW = 30
# Brier score >= 0.5 is "no better than a coin flip" -- the domain-floor
# exception 03-severity-and-trend.md allows, forcing `significant`
# regardless of PSI (a forecaster this bad doesn't need to have drifted
# to matter).
DOMAIN_FLOOR_BRIER = 0.5


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    strategy_store = get_strategy_store()

    findings: list[Finding] = []
    for angle_name in strategy_store.distinct_angle_names():
        entries = strategy_store.get_angle_calibration_entries(angle_name)
        if len(entries) < CURRENT_WINDOW + MIN_REFERENCE_WINDOW:
            continue

        # Trailing 120 entries max: the most recent 30 ("current") plus up
        # to 90 immediately before them ("reference") -- matches the
        # design doc's window sizes without overlapping the two windows.
        window = entries[-(CURRENT_WINDOW + REFERENCE_WINDOW_MAX):]
        current = window[-CURRENT_WINDOW:]
        reference = window[:-CURRENT_WINDOW]
        if len(reference) < MIN_REFERENCE_WINDOW:
            continue

        current_briers = [e.brier_score for e in current]
        reference_briers = [e.brier_score for e in reference]
        current_mean = _mean(current_briers)
        reference_mean = _mean(reference_briers)
        delta = current_mean - reference_mean

        psi = population_stability_index(reference_briers, current_briers)
        directional_accuracy = _mean([1.0 if e.directional_correct else 0.0 for e in current])

        regime_totals: dict[str, list[float]] = defaultdict(list)
        for entry in current:
            artifact = strategy_store.get_artifact(entry.artifact_id)
            regime_tag = artifact.regime_tag if artifact else ""
            regime_totals[regime_tag].append(entry.brier_score)
        regime_breakdown = {
            regime_tag: {"n": len(briers), "brier": _mean(briers)}
            for regime_tag, briers in regime_totals.items()
        }

        findings.append(
            Finding(
                analyst_name=ANALYST_NAME,
                cluster=CLUSTER,
                scope_type="angle",
                scope_key=angle_name,
                signal_json={
                    "brier_trend": delta,
                    "directional_accuracy": directional_accuracy,
                    "regime_breakdown": regime_breakdown,
                    "current_window_brier": current_mean,
                    "reference_window_brier": reference_mean,
                },
                evidence_count=len(window),
                primary_metric=delta,
                metric_name=METRIC_NAME,
                psi=psi,
                domain_floor_breached=current_mean >= DOMAIN_FLOOR_BRIER,
                narrative=(
                    f"{angle_name}: brier {current_mean:.3f} (latest {CURRENT_WINDOW}) "
                    f"vs. {reference_mean:.3f} (prior {len(reference)})"
                ),
            )
        )
    return findings


def seed_reference_config(reflection_store) -> None:
    """Idempotent, same posture as every other analyst's
    seed_reference_config in this service."""
    reflection_store.upsert_reference_config(
        analyst_name=ANALYST_NAME,
        scope_type="angle",
        metric_name=METRIC_NAME,
        metric_polarity=POLARITY_HIGHER_IS_WORSE,
        reference_window_definition="trailing_90_entries_before_the_latest_30",
        reason="A: a higher brier_score means worse forecasts (0 = perfect)",
        updated_by=ANALYST_NAME,
    )
