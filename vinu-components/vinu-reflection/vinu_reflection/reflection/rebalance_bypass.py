"""Analysis U -- critical rebalance-bypass justification. Design
reference: missing-pieces-of-system/maturity-agentic-system/thinking-1/
02-decided-pattern/25-A-Y-details/03-execution-money-flow.md ("U").

Was blocked until 2026-09-20: `RebalanceRequestQueue`'s working queue
(`vinu-live/vinu_live/trade_plan/rebalance_intake.py`) is one-row-per-
symbol and `consume()` deleted the row once evaluated -- no historical
log of past requests existed at all. The new writer that closes that gap
is `rebalance_request_history` (same file), an append-only table
`consume()` now writes to before deleting the working-queue row. This
module is the read+join side.

"the position's subsequent realized P&L" (this analysis's own Fetch) is
read from `trade_audit_log.jsonl`'s real exit rows -- same source B
(`regime_strategy_coverage.py`) already established is the only real
per-real-trade record (`bench_history` is a per-artifact backtest
series, can't answer this). For each historical request, "subsequent"
means the first exit for that symbol at or after `requested_at` --
the position the request was actually about.
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
from vinu_infra.trade_audit_log import read_all as read_trade_audit_log

ANALYST_NAME = "rebalance_bypass"
CLUSTER = "Execution & Money-Flow"
METRIC_NAME = "critical_outcome_delta"

# Critical bypass requests are "rare events by design" (this analysis's
# own Manageability note) -- a much lower floor than D/C's 30 is the
# right order of magnitude, same reasoning K/O used for their own
# evidence floors. Applies per-group (critical vs. non-critical each
# need this many, not the pooled total).
MIN_EVIDENCE_PER_GROUP = 5


def _outcome_labels(
    history: list[Any], exits_by_symbol: dict[str, list[tuple[float, float]]],
) -> tuple[dict[str, list[float]], dict[str, list[float]]]:
    """Splits every historical request into critical/non-critical label
    lists, per symbol -- 1.0 = the next exit for that symbol at or after
    `requested_at` was profitable, 0.0 = it wasn't. A request with no
    later exit for its symbol at all (position never closed, or closed
    before the request) contributes no label -- there's no real outcome
    to score."""
    critical: dict[str, list[float]] = defaultdict(list)
    noncritical: dict[str, list[float]] = defaultdict(list)
    for req in history:
        candidates = exits_by_symbol.get(req.symbol, [])
        outcome_pnl = next((pnl for ts, pnl in candidates if ts >= req.requested_at), None)
        if outcome_pnl is None:
            continue
        label = 1.0 if outcome_pnl > 0 else 0.0
        (critical if req.critical else noncritical)[req.symbol].append(label)
    return critical, noncritical


def _finding(
    scope_type: str, scope_key: str, critical_labels: list[float], noncritical_labels: list[float],
) -> Finding:
    critical_rate = sum(critical_labels) / len(critical_labels)
    noncritical_rate = sum(noncritical_labels) / len(noncritical_labels)
    delta = critical_rate - noncritical_rate
    psi = population_stability_index(
        noncritical_labels, critical_labels, bin_count=2, min_samples_per_bin=1,
    )
    return Finding(
        analyst_name=ANALYST_NAME,
        cluster=CLUSTER,
        scope_type=scope_type,
        scope_key=scope_key,
        signal_json={
            "critical_outcome_rate": critical_rate,
            "noncritical_outcome_rate": noncritical_rate,
            "critical_evidence_count": len(critical_labels),
            "noncritical_evidence_count": len(noncritical_labels),
        },
        evidence_count=len(critical_labels) + len(noncritical_labels),
        primary_metric=delta,
        metric_name=METRIC_NAME,
        psi=psi,
        narrative=(
            f"{scope_key}: critical bypass outcome rate {critical_rate:.2f} vs. "
            f"non-critical {noncritical_rate:.2f}"
        ),
    )


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    """`data_root_paths["vinu_live"]` must point at a mounted copy of
    vinu-live's own data root (same mount `loss_attribution.py` already
    uses for `trade_audit_log.jsonl`; `rebalance_requests.db` lives in
    the same directory)."""
    from vinu_live.trade_plan.rebalance_intake import RebalanceRequestQueue

    live_root = Path(data_root_paths["vinu_live"])
    queue = RebalanceRequestQueue(live_root / "rebalance_requests.db")
    history = queue.all_history()
    if not history:
        return []

    exits_by_symbol: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for row in read_trade_audit_log(log_path=live_root / "trade_audit_log.jsonl"):
        if row.get("event") != "exit":
            continue
        symbol = row.get("symbol")
        pnl = row.get("realized_pnl")
        ts = row.get("timestamp")
        if symbol is None or pnl is None or ts is None:
            continue
        try:
            exits_by_symbol[symbol].append((float(ts), float(pnl)))
        except (TypeError, ValueError):
            continue
    for rows in exits_by_symbol.values():
        rows.sort(key=lambda pair: pair[0])

    critical, noncritical = _outcome_labels(history, exits_by_symbol)

    findings: list[Finding] = []

    # System-wide rollup (this analysis's own Storage note: "rolls up to
    # scope_type=system... when a single symbol's evidence_count is too
    # low to be meaningful alone").
    system_critical = [label for labels in critical.values() for label in labels]
    system_noncritical = [label for labels in noncritical.values() for label in labels]
    if len(system_critical) >= MIN_EVIDENCE_PER_GROUP and len(system_noncritical) >= MIN_EVIDENCE_PER_GROUP:
        findings.append(_finding("system", "critical_bypass", system_critical, system_noncritical))

    # Per-symbol, only where a single symbol alone has enough evidence on
    # both sides to be meaningful without rolling up.
    for symbol in set(critical) | set(noncritical):
        crit_labels = critical.get(symbol, [])
        noncrit_labels = noncritical.get(symbol, [])
        if len(crit_labels) >= MIN_EVIDENCE_PER_GROUP and len(noncrit_labels) >= MIN_EVIDENCE_PER_GROUP:
            findings.append(_finding("ticker", symbol, crit_labels, noncrit_labels))

    return findings


def seed_reference_config(reflection_store) -> None:
    """Idempotent, same "seed on every worker-cycle start" posture as
    every other analyst here. One row covers both scope_types -- same
    reasoning K's single row covers both its scope_key values."""
    for scope_type in ("system", "ticker"):
        reflection_store.upsert_reference_config(
            analyst_name=ANALYST_NAME,
            scope_type=scope_type,
            metric_name=METRIC_NAME,
            metric_polarity=POLARITY_LOWER_IS_WORSE,
            reference_window_definition="critical_vs_noncritical_subsequent_exit_outcomes",
            reason="U: critical bypasses doing worse than non-critical requests "
            "means the bypass isn't earning the protective rule it overrides",
            updated_by=ANALYST_NAME,
        )
