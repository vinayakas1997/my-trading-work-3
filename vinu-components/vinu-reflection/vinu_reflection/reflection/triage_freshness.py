"""Analysis R -- is the Planner ever triaging against silently stale
angle data. Design reference: missing-pieces-of-system/
maturity-agentic-system/thinking-1/02-decided-pattern/25-A-Y-details/
05-governance-freshness.md ("R").

Was blocked until 2026-09-20: `ticker_summaries` is deliberately
non-versioned, so "was the Planner ever triaging against stale data at
an arbitrary past timestamp" is unanswerable after the fact -- that
scope was never buildable and still isn't. The new writer that closes a
narrower, real version of the same question is
`vinu_agent/agent/scheduler_workers.py`'s `_log_triage_freshness()`,
called from `make_planner_on_yes`'s `_on_yes` at the real "Planner
triage event" call site: it checks LIVE, at the moment each triage
happens, whether the run it acted on was already behind the true latest
run, and logs one of three exact event_types (`triage_freshness_fresh`/
`_stale`/`_unknown`) to the existing `TickerLedgerStore` -- deliberately
not free text, so this module never has to substring-match a
human-readable string to recover the outcome.

Windowing follows `angle_trust.py`'s precedent (two adjacent,
non-overlapping windows over the chronological event stream, compared
via the shared PSI machinery) rather than the design doc's literal
"trailing band" phrasing -- same reasoning A gave: PSI's "how much did
this distribution move" question is a strict generalization of a
percentile-band test, and reuses proven code instead of a second
significance mechanism for one analysis. `_unknown` events (a live
lookup failure, not a stale/fresh verdict) are excluded from the
trend series entirely -- they answer a different question ("is the
freshness check itself working"), not "was the data stale."
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

ANALYST_NAME = "triage_freshness"
CLUSTER = "Governance & Freshness"
METRIC_NAME = "stale_fraction_trend"

# Every ticker in the watchlist gets triaged roughly once per
# `planner_worker_interval_sec` (1800s default) *when ChangeGate says
# something changed* -- less frequent than a per-call metric like D's,
# more frequent than U/Y/O's genuinely rare events, so a smaller window
# than A's 30/90 is the right order of magnitude while still being a
# real two-window comparison, not a single-cycle overreaction.
CURRENT_WINDOW = 20
REFERENCE_WINDOW_MAX = 60
MIN_REFERENCE_WINDOW = 20

# This analysis's own Condition (secondary): "a specific symbol shows
# this pattern repeatedly (>= 3 occurrences)".
REPEAT_OFFENDER_MIN_STALE_COUNT = 3


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    """`data_root_paths["vinu_agent"]` must point at a mounted copy of
    vinu-agent's own data root (same mount D/K/etc. already use);
    `ticker_ledger.db` lives there."""
    from vinu_agent.agent.scheduler_workers import (
        TRIAGE_FRESHNESS_FRESH,
        TRIAGE_FRESHNESS_STALE,
    )
    from vinu_agent.storage.ticker_ledger import TickerLedgerStore

    data_root = Path(data_root_paths["vinu_agent"])
    ledger = TickerLedgerStore(data_root / "ticker_ledger.db")

    # One query, true insertion order across both types -- see
    # `list_events_by_types`'s own docstring for why two separate
    # per-type reads re-merged by `timestamp` can't be trusted here.
    combined_events = ledger.list_events_by_types([TRIAGE_FRESHNESS_STALE, TRIAGE_FRESHNESS_FRESH])
    stale_events = [e for e in combined_events if e.event_type == TRIAGE_FRESHNESS_STALE]
    fresh_events = [e for e in combined_events if e.event_type == TRIAGE_FRESHNESS_FRESH]

    findings: list[Finding] = []

    # Primary (system-wide): the combined chronological (is_stale, ticker)
    # stream, already in true insertion order.
    combined = [
        (1.0 if e.event_type == TRIAGE_FRESHNESS_STALE else 0.0, e.ticker) for e in combined_events
    ]
    if len(combined) >= CURRENT_WINDOW + MIN_REFERENCE_WINDOW:
        window = combined[-(CURRENT_WINDOW + REFERENCE_WINDOW_MAX):]
        current = window[-CURRENT_WINDOW:]
        reference = window[:-CURRENT_WINDOW]
        if len(reference) >= MIN_REFERENCE_WINDOW:
            current_labels = [row[0] for row in current]
            reference_labels = [row[0] for row in reference]
            current_fraction = sum(current_labels) / len(current_labels)
            reference_fraction = sum(reference_labels) / len(reference_labels)
            delta = current_fraction - reference_fraction

            psi = population_stability_index(
                reference_labels, current_labels, bin_count=2, min_samples_per_bin=1,
            )

            findings.append(
                Finding(
                    analyst_name=ANALYST_NAME,
                    cluster=CLUSTER,
                    scope_type="system",
                    scope_key="triage_freshness",
                    signal_json={
                        "stale_fraction": current_fraction,
                        "reference_stale_fraction": reference_fraction,
                        "n_incidents": int(sum(current_labels)),
                    },
                    evidence_count=len(current) + len(reference),
                    primary_metric=delta,
                    metric_name=METRIC_NAME,
                    psi=psi,
                    narrative=(
                        f"triage freshness: {current_fraction:.2f} stale in the last "
                        f"{len(current)} triage cycles, vs {reference_fraction:.2f} before that"
                    ),
                )
            )

    # Secondary (per-ticker repeat offenders): this analysis's own
    # Condition names a flat repeat-count threshold, not a windowed
    # trend -- implemented literally, no PSI needed for this half.
    stale_by_ticker: dict[str, int] = defaultdict(int)
    total_by_ticker: dict[str, int] = defaultdict(int)
    for e in stale_events:
        stale_by_ticker[e.ticker] += 1
        total_by_ticker[e.ticker] += 1
    for e in fresh_events:
        total_by_ticker[e.ticker] += 1

    for ticker, stale_count in stale_by_ticker.items():
        if stale_count < REPEAT_OFFENDER_MIN_STALE_COUNT:
            continue
        total = total_by_ticker[ticker]
        findings.append(
            Finding(
                analyst_name=ANALYST_NAME,
                cluster=CLUSTER,
                scope_type="ticker",
                scope_key=ticker,
                signal_json={"stale_count": stale_count, "total_triage_count": total},
                evidence_count=total,
                primary_metric=float(stale_count),
                metric_name="repeat_stale_triage_count",
                # A flat repeat-count threshold, not a distribution shift --
                # no PSI is computed for this half (there's no reference
                # window a threshold-crossing makes sense to compare
                # against). `domain_floor_breached=True` is the same
                # "significant regardless of PSI" exception A/V already use
                # for their own absolute-floor checks, applied here since
                # crossing the threshold IS the whole finding.
                psi=0.0,
                domain_floor_breached=True,
                narrative=f"{ticker}: triaged against stale data {stale_count} of {total} times",
            )
        )
    return findings


def seed_reference_config(reflection_store) -> None:
    """Idempotent, same "seed on every worker-cycle start" posture as
    every other analyst here. Both metric_names are seeded even though
    the secondary (`repeat_stale_triage_count`) has no real reference
    window -- `write_finding()` already falls back to
    POLARITY_HIGHER_IS_WORSE (the semantically correct default here
    anyway) when unseeded, but explicit beats implicit for a metric this
    module writes on every qualifying cycle."""
    reflection_store.upsert_reference_config(
        analyst_name=ANALYST_NAME,
        scope_type="system",
        metric_name=METRIC_NAME,
        metric_polarity=POLARITY_HIGHER_IS_WORSE,
        reference_window_definition="triage_freshness_fresh_or_stale_events_chronological",
        reason="R: a rising stale-triage fraction means the Planner is "
        "increasingly acting on angle data it hasn't caught up to yet",
        updated_by=ANALYST_NAME,
    )
    reflection_store.upsert_reference_config(
        analyst_name=ANALYST_NAME,
        scope_type="ticker",
        metric_name="repeat_stale_triage_count",
        metric_polarity=POLARITY_HIGHER_IS_WORSE,
        reference_window_definition="flat_repeat_count_threshold_no_window",
        reason="R: a ticker repeatedly triaged against stale data is a "
        "worse outcome the more often it happens",
        updated_by=ANALYST_NAME,
    )
