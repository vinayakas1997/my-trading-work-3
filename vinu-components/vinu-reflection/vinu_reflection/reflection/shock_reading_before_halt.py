"""Analysis N -- kill-switch retrospective, reframed. Design reference:
missing-pieces-of-system/maturity-agentic-system/thinking-1/
02-decided-pattern/25-A-Y-details/02-regime-risk-coverage.md ("N").

Was deferred 2026-09-19 alongside Q as a "dependency-cost tradeoff."
Re-investigated 2026-09-20: `fetch_personality_features`
(vinu-research/trade_plan_authoring.py) already reads
`shock_personality`/`shock_clustering` without the heavy import, via
`ResearchTools.get_angle_rows()` -- but that's a *live HTTP call* to a
running vinu-initial-analysis server, a first-of-its-kind dependency for
a worker where every other analyst is a pure offline file read. Reading
the same data as `_initial_analysis_parquet.py` does instead (pandas/
pyarrow only, no live service needed) avoids that architecture problem
entirely -- but surfaces a real cadence limit instead: `AngleRunner.run()`
defaults to `tier="tier2"`, and every scheduled compute call (including
the "continuous" hourly-polling mode) is deduped against the same
calendar-quarter window (`quarters.py`), so shock readings only ever
refresh once per quarter in the official record. "The trailing window
immediately before a halt" (the design doc's literal phrasing) doesn't
exist at that resolution -- reframed to "the most recent quarterly
snapshot before the halt," an honest scope-down of the same question,
same class as C dropping `risk_band` or V's system-wide scope-down.

`safety_ledger.jsonl` (`vinu_agent/broker/audit_ledger.py`) is real and
live-written: `kill_switch.halt_trading()` appends a `"halt"` event with
`payload.scope` on every real halt. Only *scoped* halts (`scope` a real
ticker, not `"global"`/`None`) join to a symbol's own shock readings --
a global halt has no single symbol to check, so it's excluded rather
than guessed at.

Each shock angle's own simplest real numeric field is used, not the
richer nested stats (`cluster_members`, `gap_fill_rate`'s confidence
interval, ...) -- `shock_personality.n_shocks` / `shock_clustering.
n_shock_dates`, both plain counts already present on every snapshot.
Condition: does this field run higher in the snapshot nearest before a
real halt than it does across this angle's other (non-halt-adjacent)
snapshots system-wide -- same two-group PSI comparison U/F already use,
not a windowed trend (halts are rare, one-off events, not a chronological
series to window).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from vinu_agent.broker.audit_ledger import HashChainedLedger
from vinu_infra.reflection import (
    Finding,
    POLARITY_LOWER_IS_WORSE,
    population_stability_index,
)

from vinu_reflection.reflection._initial_analysis_parquet import (
    list_analyzed_symbols,
    read_all_runs,
    to_utc_datetime,
)

ANALYST_NAME = "shock_reading_before_halt"
CLUSTER = "Regime & Risk Coverage"
METRIC_NAME = "shock_reading_delta_at_halt"

# angle_name -> the one plain-count field used as "the shock reading" for
# that angle (see module docstring for why the richer nested fields
# aren't used).
SHOCK_ANGLE_FIELDS = {
    "shock_personality": "n_shocks",
    "shock_clustering": "n_shock_dates",
}

# Halts are rare, one-off real events by design (this analysis's own
# Manageability note: "negligible volume, driven by rare real events") --
# a lower floor than even U's 5, applied only to the "at halt" side; the
# "normal" side draws from every routine quarterly snapshot and clears
# this trivially once any real evidence exists at all.
MIN_HALT_EVIDENCE = 3
MIN_NORMAL_EVIDENCE = 5


def _scoped_halt_timestamps(ledger: HashChainedLedger) -> dict[str, list[datetime]]:
    """symbol -> chronological halt timestamps, for real (non-"global",
    non-empty) scopes only."""
    by_symbol: dict[str, list[datetime]] = {}
    for entry in ledger.entries():
        if entry.get("event_type") != "halt":
            continue
        scope = (entry.get("payload") or {}).get("scope")
        if not scope or scope == "global":
            continue
        try:
            ts = datetime.fromisoformat(entry["ts"])
        except (KeyError, ValueError):
            continue
        by_symbol.setdefault(scope.upper(), []).append(ts)
    for timestamps in by_symbol.values():
        timestamps.sort()
    return by_symbol


def _nearest_reading_before(df, field: str, halt_ts: datetime) -> float | None:
    if df.empty or field not in df.columns or "stored_at" not in df.columns:
        return None
    stored_ts = df["stored_at"].map(to_utc_datetime)
    candidates = df[stored_ts.notna() & (stored_ts <= halt_ts)]
    if candidates.empty:
        return None
    value = candidates.iloc[-1][field]
    return float(value) if value is not None else None


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    agent_root = Path(data_root_paths["vinu_agent"])
    ledger = HashChainedLedger(agent_root / "safety_ledger.jsonl")
    halts_by_symbol = _scoped_halt_timestamps(ledger)
    if not halts_by_symbol:
        return []

    initial_analysis_root = Path(data_root_paths["vinu_initial_analysis"])
    findings: list[Finding] = []

    for angle_name, field in SHOCK_ANGLE_FIELDS.items():
        at_halt: list[float] = []
        normal: list[float] = []
        for symbol in list_analyzed_symbols(initial_analysis_root):
            df = read_all_runs(initial_analysis_root, symbol, angle_name)
            if df.empty or field not in df.columns or "stored_at" not in df.columns:
                continue
            values = [float(v) for v in df[field].tolist() if v is not None]

            halt_readings = []
            for halt_ts in halts_by_symbol.get(symbol, []):
                reading = _nearest_reading_before(df, field, halt_ts)
                if reading is not None:
                    halt_readings.append(reading)

            at_halt.extend(halt_readings)
            # "Normal" = every snapshot for this symbol, including ones
            # that happen to be a halt's nearest reading -- halts are
            # rare enough (this analysis's own premise) that a handful of
            # shared points doesn't meaningfully bias a system-wide
            # baseline built from every other symbol/quarter too.
            normal.extend(values)

        if len(at_halt) < MIN_HALT_EVIDENCE or len(normal) < MIN_NORMAL_EVIDENCE:
            continue

        at_halt_mean = sum(at_halt) / len(at_halt)
        normal_mean = sum(normal) / len(normal)
        delta = normal_mean - at_halt_mean  # negative = at-halt reading ran higher
        psi = population_stability_index(normal, at_halt, bin_count=3, min_samples_per_bin=1)

        findings.append(
            Finding(
                analyst_name=ANALYST_NAME,
                cluster=CLUSTER,
                scope_type="system",
                scope_key=f"kill_switch:{angle_name}",
                signal_json={
                    "at_halt_mean": at_halt_mean,
                    "normal_mean": normal_mean,
                    "n_halts_with_reading": len(at_halt),
                    "field": field,
                },
                evidence_count=len(at_halt) + len(normal),
                primary_metric=delta,
                metric_name=METRIC_NAME,
                psi=psi,
                narrative=(
                    f"{angle_name}: {field} averaged {at_halt_mean:.1f} in the nearest "
                    f"reading before a halt, vs {normal_mean:.1f} normally"
                ),
            )
        )
    return findings


def seed_reference_config(reflection_store) -> None:
    # One row covers both angles' findings: upsert_reference_config is
    # keyed by (analyst_name, scope_type, metric_name), and both
    # shock_personality's and shock_clustering's findings share the same
    # scope_type="system"/metric_name=METRIC_NAME -- same reasoning
    # rebalance_bypass.py's single row already uses for its own two
    # scope_key values.
    reflection_store.upsert_reference_config(
        analyst_name=ANALYST_NAME,
        scope_type="system",
        metric_name=METRIC_NAME,
        metric_polarity=POLARITY_LOWER_IS_WORSE,
        reference_window_definition="shock_reading_at_halt_vs_normal",
        reason="N: a shock reading that runs meaningfully higher right before "
        "real halts than during normal periods is a real, if coarse (quarterly-"
        "cadence), hindsight-detectable lead signal",
        updated_by=ANALYST_NAME,
    )
