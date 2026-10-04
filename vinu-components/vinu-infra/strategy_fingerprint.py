"""What identifies a validated live-decision strategy, shared by research (which validates) and live (which checks).

A validation only counts for the exact rules that were tested. The fingerprint covers the trigger conditions, the bar size
and the hold length; change any of them and the old validation no longer matches, so an edited strategy cannot trade on an
approval earned by a different one. Sizing and stop are not part of it: the validation tests the setup, not the risk dial.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

_INTERVALS = {"1m", "5m", "15m", "30m", "1h", "4h", "1d", "1wk"}
_WORDS = {"daily": "1d", "day": "1d", "hourly": "1h", "weekly": "1wk", "week": "1wk", "1w": "1wk"}

DEFAULT_HOLD_BARS = 20     # used when a strategy sets no maximum hold (the validation still needs a holding period)


def to_interval(schedule: str | None) -> str | None:
    """A strategy's `schedule` word as a bar size the stock service accepts, or None when it is not one."""
    key = (schedule or "").strip().lower()
    key = _WORDS.get(key, key)
    return key if key in _INTERVALS else None


def hold_bars(max_hold_bars: Any) -> int:
    try:
        n = int(max_hold_bars or 0)
    except (TypeError, ValueError):
        n = 0
    return n if n > 0 else DEFAULT_HOLD_BARS


def fingerprint(must_conditions: list[dict[str, Any]], schedule: str | None, max_hold_bars: Any) -> str:
    canonical = json.dumps(
        {
            "must": sorted((json.dumps(c, sort_keys=True, default=str) for c in (must_conditions or []))),
            "interval": to_interval(schedule),
            "hold": hold_bars(max_hold_bars),
        },
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
