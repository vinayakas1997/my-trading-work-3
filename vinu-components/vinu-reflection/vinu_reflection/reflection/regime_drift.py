"""Analysis J -- is the whole-market regime drifting in a way that should
change how much the system trusts its own strategies right now. Design
reference: missing-pieces-of-system/maturity-agentic-system/thinking-1/
02-decided-pattern/25-A-Y-details/06-external-signal-cross-check.md ("J").

Was blocked until 2026-09-20: J's original framing ("compare churn-volume
spikes to the timing of regime_tag relabeling events") assumed a
"regime relabeling event" stream that doesn't exist -- `Artifact.regime_tag`
is written once at artifact-creation time and never updated (see that
design doc's own "Blocked" note). That's a dead end, not a spec gap to
fill with a new invented classification scheme.

What's real instead: `market_regime_analogue.get_market_regime_stats_for_today()`
already computes a genuine, system-wide market-regime signal once per
calendar day -- a KNN match of "today's" market pattern against historical
regime windows, giving positive_ratio/avg_return/median_return/max_drawdown
across the matches. It just had nowhere durable to land (an in-memory,
process-lifetime day-cache only). `MarketRegimeHistoryStore`
(vinu-research/vinu_research/storage/market_regime_history.py, new) gives
it one: one row per day, written the first time that day's stats are
computed. This module reads that history and watches `positive_ratio`
drift, using the same adjacent-window PSI trend as `triage_freshness.py`/
`angle_trust.py` -- a distribution shift in how often the market's
closest historical analogues resolved positively IS a regime-change
signal, without inventing a new classification on top of a real one that
already exists.

Two real caveats, not implementation gaps: `regime_analogue_enabled` is
off by default (config.py), and the write only happens on a calendar day
some author_trade_plan() call actually runs the Phase 4 branch -- sparser
than a guaranteed daily heartbeat. MIN_EVIDENCE_COUNT below is sized
accordingly (in trading-day terms, not calendar-day terms).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from vinu_infra.reflection import (
    Finding,
    POLARITY_LOWER_IS_WORSE,
    population_stability_index,
)

ANALYST_NAME = "regime_drift"
CLUSTER = "External-Signal Cross-Check"
METRIC_NAME = "positive_ratio_trend"

# One row at most per day this fires, and only when regime_analogue_enabled
# -- a materially sparser cadence than R's per-triage-cycle events, so a
# smaller pair of windows than R's 20/60 is the right order of magnitude
# while still being a real two-window comparison, not a single-day
# overreaction to one KNN read.
CURRENT_WINDOW = 10
REFERENCE_WINDOW_MAX = 30
MIN_REFERENCE_WINDOW = 10


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    """Reads vinu-research's MarketRegimeHistoryStore via
    get_market_regime_history_store() (VINU_RESEARCH_DATA_ROOT), same
    env-var-direct pattern regime_strategy_coverage.py/paper_live_correlation.py/
    mandate_limit_friction.py already established -- data_root_paths has no
    "vinu_research" key in the real worker wiring."""
    from vinu_agent.broker.research_link import get_market_regime_history_store

    store = get_market_regime_history_store()
    history = store.all_history()

    if len(history) < CURRENT_WINDOW + MIN_REFERENCE_WINDOW:
        return []

    window = history[-(CURRENT_WINDOW + REFERENCE_WINDOW_MAX):]
    current = window[-CURRENT_WINDOW:]
    reference = window[:-CURRENT_WINDOW]
    if len(reference) < MIN_REFERENCE_WINDOW:
        return []

    current_values = [float(row["positive_ratio"]) for row in current]
    reference_values = [float(row["positive_ratio"]) for row in reference]
    current_mean = sum(current_values) / len(current_values)
    reference_mean = sum(reference_values) / len(reference_values)
    delta = current_mean - reference_mean

    psi = population_stability_index(
        reference_values, current_values, bin_count=5, min_samples_per_bin=2,
    )

    return [
        Finding(
            analyst_name=ANALYST_NAME,
            cluster=CLUSTER,
            scope_type="system",
            scope_key="market_regime",
            signal_json={
                "positive_ratio": current_mean,
                "reference_positive_ratio": reference_mean,
                "latest_date": current[-1]["date"],
                "latest_n_matches": current[-1]["n_matches"],
            },
            evidence_count=len(current) + len(reference),
            primary_metric=delta,
            metric_name=METRIC_NAME,
            psi=psi,
            narrative=(
                f"market regime: {current_mean:.2f} positive-match ratio over the last "
                f"{len(current)} days, vs {reference_mean:.2f} before that"
            ),
        )
    ]


def seed_reference_config(reflection_store) -> None:
    reflection_store.upsert_reference_config(
        analyst_name=ANALYST_NAME,
        scope_type="system",
        metric_name=METRIC_NAME,
        metric_polarity=POLARITY_LOWER_IS_WORSE,
        reference_window_definition="market_regime_history_positive_ratio_chronological",
        reason="J: a falling positive-match ratio means the market's closest "
        "historical analogues increasingly resolved badly -- a real regime "
        "shift the system's strategies weren't necessarily built for",
        updated_by=ANALYST_NAME,
    )
