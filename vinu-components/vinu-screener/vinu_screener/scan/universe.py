"""Stage B (B7): coarse -> fine two-stage universe selection.

Lean's pattern: a cheap `CoarseSelectionFunction` runs over the *entire*
universe first (here, ~8000 US equities) using only fields that are cheap
to have for everyone at once — last price, last volume, dollar volume —
and only the survivors ever pay for the expensive full condition-tree
evaluation (a per-symbol OHLCV history fetch + every rule's indicators).
Screening 8000 symbols down to a few hundred before anything in B1-B5 runs
is what makes an 8000-symbol scan cycle tractable at all.

Deliberately decoupled from *how* the coarse fields are obtained — a
snapshot/quote feed is the natural cheap source, but this module only
needs a `{symbol: {"price":..., "volume":..., "dollar_volume":...}}`-
shaped mapping, so it's equally testable with a static dict or wired to
a real quote endpoint later without changing this code.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class CoarseFilter:
    """All bounds are inclusive; `None` means "no bound on this field."
    An all-`None` filter passes everything (the coarse stage becomes a
    no-op rather than an error) — a rule that doesn't want coarse
    pre-filtering just doesn't set one."""

    min_price: float | None = None
    max_price: float | None = None
    min_volume: float | None = None
    min_dollar_volume: float | None = None


def passes_coarse(snapshot: dict[str, float], filt: CoarseFilter) -> bool:
    """One symbol's cheap snapshot against one coarse filter. Missing or
    non-finite snapshot fields fail the check they'd be needed for (same
    fail-closed posture as B2's guard) rather than being treated as
    "unbounded" — an unpriceable symbol shouldn't quietly survive a
    min_price filter just because we don't know its price."""
    def _get(key: str) -> float | None:
        v = snapshot.get(key)
        try:
            v = float(v)
        except (TypeError, ValueError):
            return None
        return v if math.isfinite(v) else None

    if filt.min_price is not None:
        p = _get("price")
        if p is None or p < filt.min_price:
            return False
    if filt.max_price is not None:
        p = _get("price")
        if p is None or p > filt.max_price:
            return False
    if filt.min_volume is not None:
        v = _get("volume")
        if v is None or v < filt.min_volume:
            return False
    if filt.min_dollar_volume is not None:
        dv = _get("dollar_volume")
        if dv is None or dv < filt.min_dollar_volume:
            return False
    return True


def coarse_select(universe_snapshots: dict[str, dict[str, float]], filt: CoarseFilter) -> list[str]:
    """The symbols surviving the coarse filter, in input order. This is the
    list B6's scan loop then fetches full OHLCV history for and runs the
    fine (B1-B5) evaluation against — never the full universe."""
    return [symbol for symbol, snap in universe_snapshots.items() if passes_coarse(snap, filt)]
