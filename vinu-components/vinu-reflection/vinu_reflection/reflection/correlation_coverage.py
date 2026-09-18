"""Analysis E (pair piece) -- cross-package systemic risk via pairwise
correlation. For every pair of symbols **currently held together**
(never the full watchlist -- the one real quadratic-scaling risk in the
whole 25-analysis set), checks whether their flagged co-movement has
been climbing. Design reference:
missing-pieces-of-system/maturity-agentic-system/thinking-1/02-decided-pattern/
25-A-Y-details/02-regime-risk-coverage.md ("E", pair piece only -- the
concentration piece needs a new vinu-portfolio mount, not attempted here).

**Real data-shape correction, found while implementing**:
`correlation_monitor_history` (vinu-live/vinu_live/trade_plan/
correlation_monitor_store.py) is written every real trading cycle (so
its `checked_at`/`n_flagged` sequence is complete), but each row's
`flagged` JSON list only contains pairs whose **co-movement already
crossed `runtime_corr_threshold`** that cycle -- pairs that stayed below
threshold leave no correlation value in this store at all. This means a
pair's *continuous* correlation history (what the design doc's "trailing
8-week P90" literally implies) isn't reconstructable -- only the
sequence of values from cycles where the pair was already flagged.
Implemented as the real, available signal instead: for each currently-
held pair, gather every historical `flagged` entry for that pair (in
cycle order) and compare its most recent 3 values against its prior up
to 8 (matching the design doc's own "3+ consecutive checks" /
"trailing 8-week" numbers, reused here as occurrence-counts rather than
calendar weeks -- flagged occurrences, not weekly cadence, is what this
store actually gives). This can't catch a pair drifting slowly toward
the threshold while staying under it (the literal "slow boil" scenario
this analysis exists for) -- it only tracks pairs that have already
crossed threshold at least `CURRENT_WINDOW + MIN_REFERENCE_WINDOW`
times. A real gap, not a design nitpick; worth a dedicated writer
(record every pair's raw correlation, not just flagged ones) if this
matters enough to close.
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

from vinu_live.book.positions import BookBackend, list_open_positions
from vinu_live.trade_plan.correlation_monitor_store import CorrelationMonitorStore

ANALYST_NAME = "regime_risk_coverage"
CLUSTER = "Regime & Risk Coverage"
METRIC_NAME = "correlation_trend"

# Matches the design doc's own numbers ("3+ consecutive weekly checks",
# "trailing 8-week P90") -- reused here as flagged-occurrence counts,
# not calendar weeks, per the module docstring above.
CURRENT_WINDOW = 3
REFERENCE_WINDOW_MAX = 8
MIN_REFERENCE_WINDOW = 3
# How many recent correlation_monitor_history rows to scan for flagged
# occurrences -- cheap (local sqlite), generous so a rarely-flagged pair
# still has a fair chance to accumulate enough evidence.
MAX_CYCLES_SCANNED = 5000


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    """`data_root_paths["vinu_live"]` must point at a mounted copy of
    vinu-live's own data root (docker-compose.yml mounts `./data/live`
    read-only into this service at `/live-data`, the same mount
    `loss_attribution.py` already uses)."""
    data_root = Path(data_root_paths["vinu_live"])
    book = BookBackend(str(data_root / "trade_plan_book.db"))
    positions = list_open_positions(book)
    held_symbols = sorted({p.symbol for p in positions})
    if len(held_symbols) < 2:
        return []
    held_pairs = {
        frozenset((held_symbols[i], held_symbols[j]))
        for i in range(len(held_symbols))
        for j in range(i + 1, len(held_symbols))
    }

    corr_store = CorrelationMonitorStore(str(data_root / "correlation_monitor.db"))
    # list_recent() returns newest-first; reverse to chronological order
    # so "most recent 3" / "prior up to 8" below is unambiguous.
    entries = list(reversed(corr_store.list_recent(limit=MAX_CYCLES_SCANNED)))

    per_pair_history: dict[frozenset, list[float]] = defaultdict(list)
    for entry in entries:
        for flagged_pair in entry.flagged:
            pair = flagged_pair.get("pair")
            correlation = flagged_pair.get("correlation")
            if not pair or len(pair) != 2 or correlation is None:
                continue
            key = frozenset(pair)
            if key not in held_pairs:
                continue
            per_pair_history[key].append(float(correlation))

    findings: list[Finding] = []
    for pair_key, values in per_pair_history.items():
        if len(values) < CURRENT_WINDOW + MIN_REFERENCE_WINDOW:
            continue

        window = values[-(CURRENT_WINDOW + REFERENCE_WINDOW_MAX):]
        current = window[-CURRENT_WINDOW:]
        reference = window[:-CURRENT_WINDOW]
        if len(reference) < MIN_REFERENCE_WINDOW:
            continue

        current_mean = _mean(current)
        reference_mean = _mean(reference)
        delta = current_mean - reference_mean

        psi = population_stability_index(reference, current, bin_count=2, min_samples_per_bin=1)

        symbol_a, symbol_b = sorted(pair_key)
        scope_key = f"{symbol_a}|{symbol_b}"

        findings.append(
            Finding(
                analyst_name=ANALYST_NAME,
                cluster=CLUSTER,
                scope_type="ticker_pair",
                scope_key=scope_key,
                signal_json={
                    "correlation_trend": delta,
                    "weeks_climbing": len(current),
                    "current_flagged_correlation": current_mean,
                    "reference_flagged_correlation": reference_mean,
                },
                evidence_count=len(window),
                primary_metric=delta,
                metric_name=METRIC_NAME,
                psi=psi,
                narrative=(
                    f"{scope_key}: flagged correlation {current_mean:.2f} "
                    f"(latest {len(current)}) vs. {reference_mean:.2f} (prior {len(reference)})"
                ),
            )
        )
    return findings


def seed_reference_config(reflection_store) -> None:
    """Idempotent, same posture as every other analyst's
    seed_reference_config in this service."""
    reflection_store.upsert_reference_config(
        analyst_name=ANALYST_NAME,
        scope_type="ticker_pair",
        metric_name=METRIC_NAME,
        metric_polarity=POLARITY_HIGHER_IS_WORSE,
        reference_window_definition="up_to_8_prior_flagged_occurrences_before_the_latest_3",
        reason="E (pair): rising correlation between co-held positions is a concentration risk",
        updated_by=ANALYST_NAME,
    )
