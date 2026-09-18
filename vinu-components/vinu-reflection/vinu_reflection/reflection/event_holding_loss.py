"""Analysis Y -- earnings/macro-event holding loss. Design reference:
missing-pieces-of-system/maturity-agentic-system/thinking-1/02-decided-pattern/
25-A-Y-details/03-execution-money-flow.md ("Y").

Was blocked until 2026-09-20: `EventsStore.replace_kind()`
(`vinu-stock-price/vinu_stock/events/store.py`) does a full
DELETE-then-INSERT of a calendar kind's rows on every pull -- `events`
is deliberately just "the current lookahead snapshot," so a closed
trade's `[entry_ts, exit_ts]` window (almost always already in the past
by the time this analysis runs) would very likely find the overlapping
event already gone. The new writer that closes that gap is
`events_archive` (same file), populated right before that delete. This
module is the read+join side, checking overlap against BOTH `events`
(a very recent trade might still overlap something not yet superseded
by a later pull) and `events_archive` (everything else) via
`upcoming()`/`archived_overlapping()`.

Closed trades come from `trade_audit_log.jsonl`'s real entry+exit pairs,
joined by `trade_id` -- same source B (`regime_strategy_coverage.py`)
established as the only real per-real-trade record.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from vinu_infra.reflection import (
    Finding,
    POLARITY_LOWER_IS_WORSE,
    population_stability_index,
)
from vinu_infra.trade_audit_log import read_all as read_trade_audit_log

ANALYST_NAME = "event_holding_loss"
CLUSTER = "Execution & Money-Flow"
METRIC_NAME = "event_overlap_pnl_delta"

# Primary is system-wide (this analysis's own Manageability note: "bounded
# to a single row") -- 20 is a smaller floor than D/C's 30 since event
# overlap is a real but not dominant fraction of all closed trades.
MIN_EVIDENCE_COUNT = 20
# Secondary per-ticker only "when it diverges meaningfully" -- needs its
# own smaller evidence floor to be worth computing at all.
MIN_EVIDENCE_COUNT_PER_TICKER = 10


def _closed_trades(rows: list[dict[str, Any]]) -> list[tuple[str, float, float, float]]:
    """Joins entry+exit rows by trade_id -> (symbol, entry_ts, exit_ts,
    realized_pnl) for every trade that actually has both. A trade_id
    with only an entry (still open) or only an exit (entry predates this
    log's retention) contributes nothing -- there's no real window to
    check overlap against."""
    entries: dict[str, tuple[str, float]] = {}
    exits: dict[str, tuple[float, float]] = {}
    for row in rows:
        trade_id = row.get("trade_id")
        symbol = row.get("symbol")
        ts = row.get("timestamp")
        if trade_id is None or symbol is None or ts is None:
            continue
        try:
            ts = float(ts)
        except (TypeError, ValueError):
            continue
        if row.get("event") == "entry":
            entries[trade_id] = (symbol, ts)
        elif row.get("event") == "exit":
            pnl = row.get("realized_pnl")
            if pnl is None:
                continue
            try:
                exits[trade_id] = (ts, float(pnl))
            except (TypeError, ValueError):
                continue

    closed: list[tuple[str, float, float, float]] = []
    for trade_id, (symbol, entry_ts) in entries.items():
        exit_row = exits.get(trade_id)
        if exit_row is None:
            continue
        exit_ts, pnl = exit_row
        closed.append((symbol, entry_ts, exit_ts, pnl))
    return closed


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    """`data_root_paths["vinu_live"]` and `["vinu_stock"]` must point at
    mounted copies of each service's own data root (same mounts
    `loss_attribution.py`/`ingest_health.py` already use)."""
    from vinu_stock.events.store import EventsStore

    live_root = Path(data_root_paths["vinu_live"])
    stock_root = Path(data_root_paths["vinu_stock"])
    events_store = EventsStore(stock_root / "vinu_events.db")

    rows = read_trade_audit_log(log_path=live_root / "trade_audit_log.jsonl")
    closed_trades = _closed_trades(rows)
    if len(closed_trades) < MIN_EVIDENCE_COUNT:
        return []

    def _overlaps(symbol: str, entry_ts: float, exit_ts: float) -> bool:
        if events_store.upcoming(symbol, entry_ts, exit_ts):
            return True
        return bool(events_store.archived_overlapping(symbol, entry_ts, exit_ts))

    overlapping_pnls: list[float] = []
    non_overlapping_pnls: list[float] = []
    by_symbol_overlapping: dict[str, list[float]] = {}
    by_symbol_non_overlapping: dict[str, list[float]] = {}

    for symbol, entry_ts, exit_ts, pnl in closed_trades:
        bucket = overlapping_pnls if _overlaps(symbol, entry_ts, exit_ts) else non_overlapping_pnls
        bucket.append(pnl)
        by_symbol = by_symbol_overlapping if bucket is overlapping_pnls else by_symbol_non_overlapping
        by_symbol.setdefault(symbol, []).append(pnl)

    findings: list[Finding] = []
    if overlapping_pnls and non_overlapping_pnls:
        mean_overlap = sum(overlapping_pnls) / len(overlapping_pnls)
        mean_non_overlap = sum(non_overlapping_pnls) / len(non_overlapping_pnls)
        delta = mean_overlap - mean_non_overlap
        psi = population_stability_index(
            non_overlapping_pnls, overlapping_pnls, bin_count=2, min_samples_per_bin=1,
        )
        findings.append(
            Finding(
                analyst_name=ANALYST_NAME,
                cluster=CLUSTER,
                scope_type="system",
                scope_key="earnings_event_effect",
                signal_json={
                    "mean_pnl_delta": delta,
                    "n_overlapping_trades": len(overlapping_pnls),
                    "n_non_overlapping_trades": len(non_overlapping_pnls),
                },
                evidence_count=len(overlapping_pnls) + len(non_overlapping_pnls),
                primary_metric=delta,
                metric_name=METRIC_NAME,
                psi=psi,
                narrative=(
                    f"event-overlapping trades: mean pnl {mean_overlap:.2f} vs. "
                    f"{mean_non_overlap:.2f} for non-overlapping"
                ),
            )
        )

        # Secondary, per-ticker: only symbols with enough of their own
        # evidence on both sides, and only when their own delta actually
        # diverges from the system baseline (this analysis's own Storage
        # note: "only written when it diverges from the system baseline").
        for symbol, overlap_labels in by_symbol_overlapping.items():
            non_overlap_labels = by_symbol_non_overlapping.get(symbol, [])
            total = len(overlap_labels) + len(non_overlap_labels)
            if len(overlap_labels) < 3 or not non_overlap_labels or total < MIN_EVIDENCE_COUNT_PER_TICKER:
                continue
            symbol_mean_overlap = sum(overlap_labels) / len(overlap_labels)
            symbol_mean_non_overlap = sum(non_overlap_labels) / len(non_overlap_labels)
            symbol_delta = symbol_mean_overlap - symbol_mean_non_overlap
            # "Diverges" from the system baseline: this symbol's delta
            # moves in the opposite direction, or is meaningfully larger
            # in magnitude, than the system-wide delta.
            diverges = (symbol_delta < 0) != (delta < 0) or abs(symbol_delta) > abs(delta) * 2
            if not diverges:
                continue
            psi_symbol = population_stability_index(
                non_overlap_labels, overlap_labels, bin_count=2, min_samples_per_bin=1,
            )
            findings.append(
                Finding(
                    analyst_name=ANALYST_NAME,
                    cluster=CLUSTER,
                    scope_type="ticker",
                    scope_key=symbol,
                    signal_json={
                        "mean_pnl_delta": symbol_delta,
                        "n_overlapping_trades": len(overlap_labels),
                        "n_non_overlapping_trades": len(non_overlap_labels),
                        "system_mean_pnl_delta": delta,
                    },
                    evidence_count=total,
                    primary_metric=symbol_delta,
                    metric_name=METRIC_NAME,
                    psi=psi_symbol,
                    narrative=(
                        f"{symbol}: event-overlap pnl delta {symbol_delta:.2f} diverges from "
                        f"system-wide {delta:.2f}"
                    ),
                )
            )

    return findings


def seed_reference_config(reflection_store) -> None:
    """Idempotent, same "seed on every worker-cycle start" posture as
    every other analyst here. One row covers both scope_types -- same
    reasoning K/U's single row covers both of theirs."""
    for scope_type in ("system", "ticker"):
        reflection_store.upsert_reference_config(
            analyst_name=ANALYST_NAME,
            scope_type=scope_type,
            metric_name=METRIC_NAME,
            metric_polarity=POLARITY_LOWER_IS_WORSE,
            reference_window_definition="event_overlapping_vs_non_overlapping_closed_trades",
            reason="Y: trades held through an earnings/macro event doing worse "
            "than trades that weren't means the event-risk exposure isn't being priced in",
            updated_by=ANALYST_NAME,
        )
