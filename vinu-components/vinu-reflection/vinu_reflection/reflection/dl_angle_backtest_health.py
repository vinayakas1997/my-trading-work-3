"""Analysis Q -- weight-lineage staleness, reframed. Design reference:
missing-pieces-of-system/maturity-agentic-system/thinking-1/
02-decided-pattern/25-A-Y-details/01-forecast-intelligence.md ("Q").

Was deferred 2026-09-19 as a "dependency-cost tradeoff" (`WeightsStore`
lives in vinu-initial-analysis, the one service too dependency-heavy to
mount-and-import). Re-investigated 2026-09-20 and found to be a
different, deeper problem than cost: `weights_ref` (this analysis's
whole premise) is written ONLY by each DL angle's offline walk-forward
`backtest.py` module (via `run_walk_forward`'s `weights_sink`, see
`vinu-tools/vinu_tools/compute/backtest/walk_forward.py`). The LIVE
forecast path each angle actually runs on schedule (`compute.py`,
dispatched by `vinu_initial_analysis.runner.AngleRunner`) never saves or
references a checkpoint at all. There is no "currently-live model
checkpoint" concept anywhere in production for these angles -- Q's
original premise (is the live checkpoint stale, joined to real trade
outcomes via `angle_calibration_entries`) has nothing real to point at.
Confirmed further: `angle_calibration_entries` has no `weights_ref` or
`symbol` column, and `Artifact.origin_angles` comes from an LLM's
free-form self-report (`angles_used`), never a specific checkpoint.

What IS real: `orchestration_registry.py` maps every DL angle to its
`backtest.py` entry point, invoked on a real (if only quarterly,
`vinu_initial_analysis/quarters.py`) schedule, writing an immutable
`tier2` Parquet record with real `bar_ts`/`hit`/`weights_ref` columns for
every walk-forward step. That's a genuine, self-contained, real
backtest-accuracy history -- just not a live-trade one. Reframed here as
two honest questions computable entirely from it, no join to vinu-
research/vinu-agent needed at all:

Primary (accuracy trend): adjacent-window PSI trend on the `hit` series
(chronological by `bar_ts`), same shape `angle_trust.py` (A) already
uses -- a declining hit-rate across the walk-forward series is real
evidence of degrading forecast quality, without inventing a "weights_ref
generation" concept that doesn't naturally apply to angles retrained
fresh at every single step (see `lstm/backtest.py`'s own docstring).

Secondary (staleness): compares the stored run's own `stored_at`
(`AngleStorage`'s fixed metadata column) against now. `VINU_TIER2_PERIOD_
MONTHS` is read directly as an env var (default 3, matching `quarters.py`'s
own `DEFAULT_PERIOD_MONTHS`) -- never importing `vinu_initial_analysis`
itself, same posture `_initial_analysis_parquet.py` establishes. More
than 2x that period since the last recompute means this angle's backtest
record itself has gone stale, independent of what it once showed.

Reads via `_initial_analysis_parquet.py` (torch-free, pandas/pyarrow
only) against `data_root_paths["vinu_initial_analysis"]`.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from vinu_infra.reflection import (
    Finding,
    POLARITY_HIGHER_IS_WORSE,
    POLARITY_LOWER_IS_WORSE,
    population_stability_index,
)

from vinu_reflection.reflection._initial_analysis_parquet import (
    list_analyzed_symbols,
    read_latest_run,
    to_utc_datetime,
)

ANALYST_NAME = "dl_angle_backtest_health"
CLUSTER = "Forecast Intelligence"
ACCURACY_METRIC_NAME = "hit_rate_trend"
STALENESS_METRIC_NAME = "backtest_staleness_days"

# The real 7 -- ARIMA is listed alongside these in the design doc's own
# text but never calls weights_sink (a classical per-step refit with
# nothing meaningful to checkpoint), confirmed by reading every one of
# these 8 backtest.py modules directly rather than trusting the doc's
# count.
DL_ANGLES = (
    "dlinear", "itransformer", "lpatchtst", "lstm",
    "patchtst", "tft", "tips_regime_aware_transformer",
)

# Same order of magnitude as A's angle_trust.py -- both are per-bar
# (typically daily) chronological series of comparable length.
CURRENT_WINDOW = 30
REFERENCE_WINDOW_MAX = 90
MIN_REFERENCE_WINDOW = 30

DEFAULT_TIER2_PERIOD_MONTHS = 3
STALENESS_MULTIPLIER = 2.0


def _staleness_threshold_days() -> float:
    try:
        months = float(os.environ.get("VINU_TIER2_PERIOD_MONTHS", str(DEFAULT_TIER2_PERIOD_MONTHS)))
    except ValueError:
        months = DEFAULT_TIER2_PERIOD_MONTHS
    return months * 30.0 * STALENESS_MULTIPLIER


def _accuracy_finding(symbol: str, angle_name: str, hits: list[float]) -> Finding | None:
    if len(hits) < CURRENT_WINDOW + MIN_REFERENCE_WINDOW:
        return None
    window = hits[-(CURRENT_WINDOW + REFERENCE_WINDOW_MAX):]
    current = window[-CURRENT_WINDOW:]
    reference = window[:-CURRENT_WINDOW]
    if len(reference) < MIN_REFERENCE_WINDOW:
        return None
    current_rate = sum(current) / len(current)
    reference_rate = sum(reference) / len(reference)
    delta = current_rate - reference_rate  # negative = accuracy fell
    psi = population_stability_index(reference, current, bin_count=2, min_samples_per_bin=1)
    return Finding(
        analyst_name=ANALYST_NAME,
        cluster=CLUSTER,
        scope_type="ticker",
        scope_key=f"{symbol}:{angle_name}",
        signal_json={
            "hit_rate": current_rate,
            "reference_hit_rate": reference_rate,
            "n_steps": len(current) + len(reference),
        },
        evidence_count=len(current) + len(reference),
        primary_metric=delta,
        metric_name=ACCURACY_METRIC_NAME,
        psi=psi,
        narrative=(
            f"{symbol}:{angle_name} backtest hit rate {current_rate:.2f} (latest "
            f"{len(current)} steps) vs {reference_rate:.2f} before that"
        ),
    )


def _staleness_finding(symbol: str, angle_name: str, stored_at: Any) -> Finding | None:
    stored_ts = to_utc_datetime(stored_at)
    if stored_ts is None:
        return None
    age_days = (datetime.now(timezone.utc) - stored_ts).total_seconds() / 86400.0
    threshold = _staleness_threshold_days()
    if age_days < threshold:
        return None
    return Finding(
        analyst_name=ANALYST_NAME,
        cluster=CLUSTER,
        scope_type="ticker",
        # A distinct scope_key from the accuracy finding's -- reflection_
        # beliefs' real primary key is (analyst_name, scope_type,
        # scope_key), with no metric_name column, so two different
        # metrics sharing one scope_key would silently overwrite each
        # other's belief row every cycle both happen to fire.
        scope_key=f"{symbol}:{angle_name}:staleness",
        signal_json={"age_days": age_days, "threshold_days": threshold},
        evidence_count=1,
        primary_metric=age_days,
        metric_name=STALENESS_METRIC_NAME,
        psi=0.0,
        domain_floor_breached=True,
        narrative=(
            f"{symbol}:{angle_name} backtest record is {age_days:.0f} days old "
            f"(> {threshold:.0f}-day floor) -- overdue for its next quarterly recompute"
        ),
    )


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    data_root = Path(data_root_paths["vinu_initial_analysis"])
    findings: list[Finding] = []
    for symbol in list_analyzed_symbols(data_root):
        for angle_name in DL_ANGLES:
            df = read_latest_run(data_root, symbol, angle_name)
            if df.empty or "hit" not in df.columns or "bar_ts" not in df.columns:
                continue
            df = df.sort_values("bar_ts")
            hits = [float(h) for h in df["hit"].tolist() if h is not None]

            accuracy_finding = _accuracy_finding(symbol, angle_name, hits)
            if accuracy_finding is not None:
                findings.append(accuracy_finding)

            if "stored_at" in df.columns and not df["stored_at"].empty:
                staleness_finding = _staleness_finding(symbol, angle_name, df["stored_at"].iloc[-1])
                if staleness_finding is not None:
                    findings.append(staleness_finding)
    return findings


def seed_reference_config(reflection_store) -> None:
    reflection_store.upsert_reference_config(
        analyst_name=ANALYST_NAME,
        scope_type="ticker",
        metric_name=ACCURACY_METRIC_NAME,
        metric_polarity=POLARITY_LOWER_IS_WORSE,
        reference_window_definition="dl_angle_backtest_hit_chronological",
        reason="Q: a falling walk-forward hit rate for this (symbol, angle) "
        "means its own backtest-evaluated accuracy is genuinely degrading",
        updated_by=ANALYST_NAME,
    )
    reflection_store.upsert_reference_config(
        analyst_name=ANALYST_NAME,
        scope_type="ticker",
        metric_name=STALENESS_METRIC_NAME,
        metric_polarity=POLARITY_HIGHER_IS_WORSE,
        reference_window_definition="flat_backtest_recompute_age_threshold",
        reason="Q: a backtest record far older than the expected quarterly "
        "recompute cadence means this angle's own evaluation has gone stale",
        updated_by=ANALYST_NAME,
    )
