"""Analysis E (concentration piece) -- per sleeve (style tag), checks
whether allocated weight concentration has drifted between an older
reference window and the most recent daily allocations. Design reference:
missing-pieces-of-system/maturity-agentic-system/thinking-1/02-decided-pattern/
25-A-Y-details/02-regime-risk-coverage.md ("E", concentration piece).

**Real data-shape correction, found while implementing**: the design
doc's Fetch offers "`vol_annualized` or weight concentration" as
alternatives. Checked `AllocationHistoryStore`
(`vinu-portfolio/vinu_portfolio/storage/allocation_history.py`) and its
one real writer (`service.py`'s `compute_daily_allocation()`,
~line 890): `sleeves` is `{style_tag: summed_target_weight}` -- a real,
persisted weight-concentration series. No per-sleeve `vol_annualized` is
tracked anywhere in this table or its writer. Implemented against the
weight-concentration signal, the one the doc's own "or" already
anticipated might be the available one.

Windowing follows the same two-adjacent-windows PSI pattern as every
other trailing-comparison analysis in this service (A/C/E-pair/H).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from vinu_infra.reflection import (
    Finding,
    POLARITY_HIGHER_IS_WORSE,
    population_stability_index,
)

from vinu_portfolio.storage.allocation_history import AllocationHistoryStore

ANALYST_NAME = "regime_risk_coverage"
CLUSTER = "Regime & Risk Coverage"
METRIC_NAME = "weight_trend"

CURRENT_WINDOW = 30
REFERENCE_WINDOW_MAX = 90
MIN_REFERENCE_WINDOW = 30


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    """`data_root_paths["vinu_portfolio"]` must point at a mounted copy
    of vinu-portfolio's own data root (docker-compose.yml mounts
    `./data/portfolio` read-only into this service at `/portfolio-data`)."""
    data_root = Path(data_root_paths["vinu_portfolio"])
    store = AllocationHistoryStore(str(data_root / "allocation_history.db"))

    # list_allocations() returns newest-first; reverse to chronological
    # order (oldest allocation_date first) for the window slicing below.
    allocations = list(reversed(store.list_allocations()))
    if len(allocations) < CURRENT_WINDOW + MIN_REFERENCE_WINDOW:
        return []

    sleeve_names: set[str] = set()
    for allocation in allocations:
        sleeve_names.update(allocation.sleeves.keys())

    findings: list[Finding] = []
    for sleeve in sleeve_names:
        # A day with no allocation to this sleeve is real information
        # (0.0 weight that day), not missing data -- included as-is.
        series = [allocation.sleeves.get(sleeve, 0.0) for allocation in allocations]

        window = series[-(CURRENT_WINDOW + REFERENCE_WINDOW_MAX):]
        current = window[-CURRENT_WINDOW:]
        reference = window[:-CURRENT_WINDOW]
        if len(reference) < MIN_REFERENCE_WINDOW:
            continue

        current_mean = _mean(current)
        reference_mean = _mean(reference)
        delta = current_mean - reference_mean

        psi = population_stability_index(reference, current)

        findings.append(
            Finding(
                analyst_name=ANALYST_NAME,
                cluster=CLUSTER,
                scope_type="strategy_family",
                scope_key=sleeve,
                signal_json={
                    "weight_trend": delta,
                    "current_weight": current_mean,
                    "reference_weight": reference_mean,
                },
                evidence_count=len(window),
                primary_metric=delta,
                metric_name=METRIC_NAME,
                psi=psi,
                narrative=(
                    f"{sleeve}: allocated weight {current_mean:.3f} (latest {CURRENT_WINDOW} days) "
                    f"vs. {reference_mean:.3f} (prior {len(reference)} days)"
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
        metric_polarity=POLARITY_HIGHER_IS_WORSE,
        reference_window_definition="trailing_90_days_before_the_latest_30",
        reason="E (concentration): a sleeve consuming a rising share of allocated weight is a concentration risk",
        updated_by=ANALYST_NAME,
    )
