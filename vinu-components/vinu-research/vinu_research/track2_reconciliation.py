"""Item #10 (system-wide-audit-and-design/02-open-questions-strategy-
and-simulation.md): "cross-track disagreement as its own signal."

Deliberately scoped smaller than that item's original 4-state
`cross_track_check` sketch (confirmed/track1_only/track2_only/neither).
Discussed directly and narrowed: what's actually wanted right now is
visibility into the `track2_only` case specifically -- a real price move
Track 2 detected that no strategy's must-condition was watching for --
not a stored, periodically-recomputed reconciliation table for all four
states. This module is a read-time query (same "computed fresh, never
cached" convention `ticker_coverage.py`/`candidate_graveyard.py` already
established here), joining `MoveEvidenceStore` (every real move, written
unconditionally by `vinu-live`'s poller) against `SignalEvidenceStore`
(Track 1's trigger history) on the fly.

Honest caveat, not hidden: nothing in this codebase currently calls
`POST /research/signal-evidence/trigger` in production (`SignalEvidenceStore`
has its store and route, but no live writer was ever wired to it -- a
separate, pre-existing gap, not touched here). Until that writer exists,
essentially every move this reconciliation surfaces will look like
`track2_only`, which is an accurate reflection of the system's current
state, not a bug in this matching logic.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from vinu_research.storage.move_evidence_store import MoveEvidenceStore
from vinu_research.storage.signal_evidence_store import SignalEvidenceStore


def _parse_utc(iso: str) -> datetime:
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _is_confirmed_by_track1(
    move_event: dict[str, Any], *, signal_evidence_store: SignalEvidenceStore,
) -> bool:
    """A move is "confirmed" when some strategy's must-condition trigger
    fired for the same symbol within this move's own window tolerance
    (`window_seconds`, the move's granularity translated to seconds by
    the caller that recorded it) -- not an exact timestamp match, since a
    strategy's trigger and Track 2's bar-close detection can land a few
    seconds apart even when they're really "the same event."""
    window_dt = _parse_utc(move_event["window_time"])
    tolerance = timedelta(seconds=move_event["window_seconds"])
    triggers = signal_evidence_store.list_triggers(symbol=move_event["symbol"], limit=200)
    for t in triggers:
        trigger_dt = _parse_utc(t["trigger_time"])
        if abs((trigger_dt - window_dt).total_seconds()) <= tolerance.total_seconds():
            return True
    return False


def list_unconfirmed_moves(
    *,
    move_evidence_store: MoveEvidenceStore,
    signal_evidence_store: SignalEvidenceStore,
    symbol: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Real Track 2 moves (`move_detected=True`, already the only kind
    `MoveEvidenceStore` stores) with no matching Track 1 trigger on file
    -- the `track2_only` case item #10 asked to surface. Each returned
    row is the raw move event plus `confirmed_by_track1: False` (kept on
    the row rather than silently filtered out entirely, so a caller can
    still see the total move count if it wants to compute a ratio)."""
    events = move_evidence_store.list_move_events(symbol=symbol, limit=limit)
    unconfirmed = []
    for event in events:
        if not _is_confirmed_by_track1(event, signal_evidence_store=signal_evidence_store):
            event = dict(event)
            event["confirmed_by_track1"] = False
            unconfirmed.append(event)
    return unconfirmed
