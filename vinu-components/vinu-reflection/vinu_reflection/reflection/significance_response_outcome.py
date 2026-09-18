"""Analysis F -- human-in-the-loop as a measured variable, not an assumed
good. Design reference: missing-pieces-of-system/maturity-agentic-system/
thinking-1/02-decided-pattern/25-A-Y-details/05-governance-freshness.md
("F").

Was "not attempted, 2026-09-19" -- "downstream outcomes for the flagged
tickers" wasn't a checked, concrete join yet. Checked now: `significance_
flags` (`vinu_agent/agent/significance_triage.py`) already has exactly
the columns this needs -- `ticker`, `created_at`, `resolved` -- it was
just missing a way to read every row (`SignificanceFlagStore` only had
`get_flag(flag_id)`, a single lookup, and `response_rate()`, aggregate
counts with no per-row access). Added `all_flags()`.

"Downstream outcome for the flagged ticker" reuses the exact weak
symbol+time join `rebalance_bypass.py` (U) already established against
`trade_audit_log.jsonl`'s real exit rows: the first exit for that ticker
at or after the flag's `created_at`. No new join key needed on
`significance_flags` itself, unlike O's real blocker -- `ticker` +
`created_at` already are one.

One real caveat, not a bug: `llm_failure_rate` flags use a sentinel
ticker (`LLM_FAILURE_SENTINEL_TICKER = "SYSTEM"`, per
`significance_triage.py`), not a real tradable symbol -- the weak join
naturally never finds a matching exit for that flag_type, so it simply
never accumulates evidence here. Correct, not a gap: "did a human
response change this position's outcome" doesn't apply to a system-wide
LLM-failure alert in the first place.

`created_at` is an ISO `%Y-%m-%dT%H:%M:%SZ` string; `trade_audit_log.
jsonl`'s `timestamp` is a raw `time.time()` float -- `_parse_created_at`
converts once so both sides compare as epoch seconds.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from vinu_infra.reflection import (
    Finding,
    POLARITY_LOWER_IS_WORSE,
    population_stability_index,
)
from vinu_infra.trade_audit_log import read_all as read_trade_audit_log

ANALYST_NAME = "significance_response_outcome"
CLUSTER = "Governance & Freshness"
METRIC_NAME = "response_outcome_delta"

# Significance flags are gated by their own detection thresholds (repeated
# rejections, a large-funding dollar ceiling, a thesis-contradicting
# close) -- infrequent by design, same order of magnitude as U's critical
# bypasses, not D/C's per-cycle volume.
MIN_EVIDENCE_PER_GROUP = 5


def _parse_created_at(created_at: str) -> float | None:
    try:
        return (
            datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=timezone.utc)
            .timestamp()
        )
    except ValueError:
        return None


def _outcome_labels(
    flags: list[Any], exits_by_ticker: dict[str, list[tuple[float, float]]],
) -> tuple[dict[str, list[float]], dict[str, list[float]]]:
    """Splits every flag into responded/unresponded label lists, per
    `reason` (flag_type) -- 1.0 = the next exit for that ticker at or
    after the flag's `created_at` was profitable, 0.0 = it wasn't. A flag
    with no later exit for its ticker at all (position never closed
    after the flag, or the sentinel "SYSTEM" ticker) contributes no
    label -- there's no real outcome to score."""
    responded: dict[str, list[float]] = defaultdict(list)
    unresponded: dict[str, list[float]] = defaultdict(list)
    for flag in flags:
        created_ts = _parse_created_at(flag.created_at)
        if created_ts is None:
            continue
        candidates = exits_by_ticker.get(flag.ticker, [])
        outcome_pnl = next((pnl for ts, pnl in candidates if ts >= created_ts), None)
        if outcome_pnl is None:
            continue
        label = 1.0 if outcome_pnl > 0 else 0.0
        (responded if flag.resolved else unresponded)[flag.reason].append(label)
    return responded, unresponded


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    """`data_root_paths["vinu_agent"]` must point at a mounted copy of
    vinu-agent's own data root (`significance_flags.db` lives there,
    same as `ticker_ledger.db`); `data_root_paths["vinu_live"]` for
    `trade_audit_log.jsonl` (same mount `rebalance_bypass.py`/
    `loss_attribution.py` already use)."""
    from vinu_agent.agent.significance_triage import SignificanceFlagStore

    agent_root = Path(data_root_paths["vinu_agent"])
    flag_store = SignificanceFlagStore(agent_root / "significance_flags.db")
    flags = flag_store.all_flags()
    if not flags:
        return []

    live_root = Path(data_root_paths["vinu_live"])
    exits_by_ticker: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for row in read_trade_audit_log(log_path=live_root / "trade_audit_log.jsonl"):
        if row.get("event") != "exit":
            continue
        ticker = row.get("symbol")
        pnl = row.get("realized_pnl")
        ts = row.get("timestamp")
        if ticker is None or pnl is None or ts is None:
            continue
        try:
            exits_by_ticker[ticker].append((float(ts), float(pnl)))
        except (TypeError, ValueError):
            continue
    for rows in exits_by_ticker.values():
        rows.sort(key=lambda pair: pair[0])

    responded, unresponded = _outcome_labels(flags, exits_by_ticker)

    findings: list[Finding] = []
    for reason in set(responded) | set(unresponded):
        responded_labels = responded.get(reason, [])
        unresponded_labels = unresponded.get(reason, [])
        if len(responded_labels) < MIN_EVIDENCE_PER_GROUP or len(unresponded_labels) < MIN_EVIDENCE_PER_GROUP:
            continue
        responded_rate = sum(responded_labels) / len(responded_labels)
        unresponded_rate = sum(unresponded_labels) / len(unresponded_labels)
        delta = responded_rate - unresponded_rate
        psi = population_stability_index(
            unresponded_labels, responded_labels, bin_count=2, min_samples_per_bin=1,
        )
        findings.append(
            Finding(
                analyst_name=ANALYST_NAME,
                cluster=CLUSTER,
                scope_type="system",
                scope_key=reason,
                signal_json={
                    "responded_outcome_rate": responded_rate,
                    "unresponded_outcome_rate": unresponded_rate,
                    "responded_evidence_count": len(responded_labels),
                    "unresponded_evidence_count": len(unresponded_labels),
                },
                evidence_count=len(responded_labels) + len(unresponded_labels),
                primary_metric=delta,
                metric_name=METRIC_NAME,
                psi=psi,
                narrative=(
                    f"{reason}: responded-to flags {responded_rate:.2f} positive-outcome rate "
                    f"vs. {unresponded_rate:.2f} for unresponded ones"
                ),
            )
        )
    return findings


def seed_reference_config(reflection_store) -> None:
    reflection_store.upsert_reference_config(
        analyst_name=ANALYST_NAME,
        scope_type="system",
        metric_name=METRIC_NAME,
        metric_polarity=POLARITY_LOWER_IS_WORSE,
        reference_window_definition="responded_vs_unresponded_subsequent_exit_outcomes",
        reason="F: unresponded flags doing no worse (or better) than responded "
        "ones means the human-in-the-loop step isn't earning its own alert "
        "fatigue cost for this flag_type",
        updated_by=ANALYST_NAME,
    )
