"""Analyses I and X -- does vinu-screener's factor ranker (I) / condition-
rule alert engine (X) actually predict anything the main pipeline
independently agrees with. Same shape for both (the design doc says so
explicitly for X: "same shape as I"), so implemented together in one
module. Design reference:
missing-pieces-of-system/maturity-agentic-system/thinking-1/02-decided-pattern/
25-A-Y-details/06-external-signal-cross-check.md ("I", "X").

**The real "did the main pipeline independently agree" signal**: the
Planner triage hook writes a `candidate_proposed` event
(`CANDIDATE_PROPOSED_EVENT_TYPE`, `vinu_agent/agent/thesis_intake_gate.py`)
into `ticker_ledger` (vinu-agent) whenever it independently proposes a
symbol as a thesis candidate -- a real, checkable, per-symbol,
per-timestamp signal, not something this analysis has to invent.
"Agreement" = a `candidate_proposed` event for the same symbol within
`AGREEMENT_WINDOW_HOURS` of the churn/fire event, either side (the
design doc's "within a trailing window of the same event" doesn't
specify a direction; a symmetric window is the more defensible
provisional reading -- the pipeline could plausibly have flagged the
symbol shortly before the screener did, not only after).

Windowing follows the same two-adjacent-windows PSI pattern as every
other trailing-comparison analysis in this service (A/C/E/H).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from vinu_infra.reflection import (
    Finding,
    POLARITY_LOWER_IS_WORSE,
    population_stability_index,
)

from vinu_agent.agent.thesis_intake_gate import CANDIDATE_PROPOSED_EVENT_TYPE
from vinu_agent.storage.ticker_ledger import TickerLedgerStore
from vinu_screener.audit.watch_history import WatchAuditStore
from vinu_screener.rankers.churn import RankerChurnStore
from vinu_screener.rankers.store import RankerStore

ANALYST_NAME = "external_signal_cross_check"
CLUSTER = "External-Signal Cross-Check"
METRIC_NAME = "agreement_rate"

AGREEMENT_WINDOW_HOURS = 48.0
CURRENT_WINDOW = 10
REFERENCE_WINDOW_MAX = 30
MIN_REFERENCE_WINDOW = 10
MAX_EVENTS_SCANNED = 1000


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _parse_ts(timestamp: str) -> Optional[float]:
    try:
        return (
            datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=timezone.utc)
            .timestamp()
        )
    except (ValueError, TypeError):
        return None


def _pipeline_agreed(ticker_ledger_store: TickerLedgerStore, symbol: str, event_at: float) -> bool:
    window_start = event_at - AGREEMENT_WINDOW_HOURS * 3600
    window_end = event_at + AGREEMENT_WINDOW_HOURS * 3600
    for event in ticker_ledger_store.get_events(symbol):
        if event.event_type != CANDIDATE_PROPOSED_EVENT_TYPE:
            continue
        ts = _parse_ts(event.timestamp)
        if ts is not None and window_start <= ts <= window_end:
            return True
    return False


def _trend_finding(scope_key: str, agreement_flags: list[float]) -> Optional[Finding]:
    if len(agreement_flags) < CURRENT_WINDOW + MIN_REFERENCE_WINDOW:
        return None
    window = agreement_flags[-(CURRENT_WINDOW + REFERENCE_WINDOW_MAX):]
    current = window[-CURRENT_WINDOW:]
    reference = window[:-CURRENT_WINDOW]
    if len(reference) < MIN_REFERENCE_WINDOW:
        return None

    current_rate = _mean(current)
    reference_rate = _mean(reference)
    delta = current_rate - reference_rate
    psi = population_stability_index(reference, current, bin_count=2, min_samples_per_bin=1)

    return Finding(
        analyst_name=ANALYST_NAME,
        cluster=CLUSTER,
        scope_type="system",
        scope_key=scope_key,
        signal_json={
            "agreement_rate": current_rate,
            "reference_agreement_rate": reference_rate,
            "n_events": len(window),
        },
        evidence_count=len(window),
        primary_metric=delta,
        metric_name=METRIC_NAME,
        psi=psi,
        narrative=(
            f"{scope_key}: pipeline-agreement rate {current_rate:.2f} (latest {CURRENT_WINDOW}) "
            f"vs. {reference_rate:.2f} (prior {len(reference)})"
        ),
    )


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    """`data_root_paths["vinu_screener"]` must point at a mounted copy of
    vinu-screener's own data root; `data_root_paths["vinu_agent"]` at
    vinu-agent's (both already mounted for other analysts in this
    service)."""
    screener_root = Path(data_root_paths["vinu_screener"])
    agent_root = Path(data_root_paths["vinu_agent"])
    ticker_ledger_store = TickerLedgerStore(agent_root / "ticker_ledger.db")

    findings: list[Finding] = []

    # I -- factor ranker churn ("entered top-N") vs. independent pipeline interest.
    ranker_store = RankerStore(str(screener_root / "screener_rankers.db"))
    churn_store = RankerChurnStore(str(screener_root / "screener_ranker_churn.db"))
    for stored in ranker_store.all():
        ranker_id = stored.ranker.ranker_id
        entered = [
            e for e in reversed(churn_store.history(ranker_id, limit=MAX_EVENTS_SCANNED))
            if e.kind == "entered"
        ]
        flags = [
            1.0 if _pipeline_agreed(ticker_ledger_store, e.symbol, e.at) else 0.0
            for e in entered
        ]
        finding = _trend_finding(ranker_id, flags)
        if finding is not None:
            findings.append(finding)

    # X -- condition-rule alert fires vs. independent pipeline interest.
    watch_store = WatchAuditStore(str(screener_root / "screener_audit.db"))
    fires_by_rule: dict[str, list] = {}
    for record in reversed(watch_store.history(limit=MAX_EVENTS_SCANNED)):
        fires_by_rule.setdefault(record.rule_id, []).append(record)
    for rule_id, records in fires_by_rule.items():
        flags = [
            1.0 if _pipeline_agreed(ticker_ledger_store, r.symbol, r.fired_at) else 0.0
            for r in records
        ]
        finding = _trend_finding(rule_id, flags)
        if finding is not None:
            findings.append(finding)

    return findings


def seed_reference_config(reflection_store) -> None:
    """Idempotent, same posture as every other analyst's
    seed_reference_config in this service. One row covers both I and X
    -- same analyst_name/scope_type/metric_name, since they share
    `agreement_rate`'s polarity."""
    reflection_store.upsert_reference_config(
        analyst_name=ANALYST_NAME,
        scope_type="system",
        metric_name=METRIC_NAME,
        metric_polarity=POLARITY_LOWER_IS_WORSE,
        reference_window_definition="trailing_30_events_before_the_latest_10",
        reason="I/X: a ranker/rule the main pipeline never independently agrees with isn't predicting anything",
        updated_by=ANALYST_NAME,
    )
