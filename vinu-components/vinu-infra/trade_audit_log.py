"""Append-only per-trade audit log -- the high-expectations spec's "post-
trade learning" pillar named this as a real gap: trade lifecycle facts
were scattered across vinu-live's orchestrator.py action results, the
position book, and calibration_log.py, with no single row saying "this
trade, this reasoning, this outcome."

This is a JOIN KEY, not a new data-collection effort: every field recorded
here already exists on the TradePlan/RiskBand/Position objects at the two
call sites that write it (orchestrator.py's entry and exit/reduce paths).
This module's only job is writing one row per lifecycle event, keyed by
`trade_id` (the book's own `position_id`, already the natural identity for
one open-to-close trade), so `read_by_trade_id` can later reconstruct the
whole story of one trade without re-deriving it from three different logs.

Same append-only-JSONL, best-effort-write conventions as calibration_log.py
in this same package (record() never raises -- a write failure here must
never be able to affect a real trading decision)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

DEFAULT_LOG_PATH = os.environ.get(
    "VINU_TRADE_AUDIT_LOG",
    os.environ.get("VINU_DATA_ROOT", str(Path.home() / ".vinu")) + "/trade_audit_log.jsonl",
)


def record_entry(
    trade_id: str,
    symbol: str,
    context: dict[str, Any],
    *,
    log_path: str | Path | None = None,
) -> None:
    """One row for a trade's opening event. `context` is expected to carry
    whatever of entry_decision / trade_score tier+reasons / risk_band
    snapshot / fill price+qty / artifact_id the caller has on hand --
    intentionally untyped (a plain dict, like calibration_log.record's
    `context`) so this never needs a schema migration when a new field
    becomes available upstream."""
    _record(trade_id, symbol, "entry", context, log_path=log_path)


def record_exit(
    trade_id: str,
    symbol: str,
    context: dict[str, Any],
    *,
    log_path: str | Path | None = None,
) -> None:
    """One row for a trade's closing event (full close or a partial
    reduce), joined back to its record_entry row by the same `trade_id`."""
    _record(trade_id, symbol, "exit", context, log_path=log_path)


def _record(
    trade_id: str,
    symbol: str,
    event: str,
    context: dict[str, Any],
    *,
    log_path: str | Path | None,
) -> None:
    """Best-effort append: any failure here (permissions, disk full, a
    non-serializable value in context) is swallowed, never raised -- same
    contract as calibration_log.record and every other audit/log writer in
    this codebase."""
    try:
        path = Path(log_path) if log_path is not None else Path(DEFAULT_LOG_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "trade_id": trade_id, "symbol": symbol, "event": event,
            "timestamp": time.time(), **context,
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception:  # noqa: BLE001 -- best-effort, see module docstring
        pass


def read_by_trade_id(
    trade_id: str, *, log_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """All rows (entry + any exit/reduce events) for one trade_id, in the
    order they were written. Missing file or no matching rows returns an
    empty list, not an error."""
    path = Path(log_path) if log_path is not None else Path(DEFAULT_LOG_PATH)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("trade_id") == trade_id:
                rows.append(entry)
    return rows


def read_all(*, log_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Every recorded row, for offline analysis. Missing file returns an
    empty list, not an error."""
    path = Path(log_path) if log_path is not None else Path(DEFAULT_LOG_PATH)
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries
