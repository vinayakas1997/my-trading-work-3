"""Detective checks for look-ahead and warmup drift in the indicator/feature registry.

Phase 5 (items 5.1 and 5.2) of newer-thinking-with-discussed/the-inconsistencies-v2/
03-implementation-plan.md. The system is strong at PREVENTING leakage (as-of clamping, a
one-bar shift in the simulator) but had nothing that MEASURES it for a finished feature.
Two pure, offline checks over `apply_indicators` (or any `compute(rows, names) -> rows`):

* `lookahead_report` -- a feature's value at bar t must not change when the future is
  removed. Compute on the full series, recompute on prefixes, compare the last bars of each
  prefix. A mismatch means the value at t depended on bars after t. Also reports
  `unverifiable` features: ones that produced no value at any checked bar, because a check
  that compares None with None proves nothing (this is how a whole family of silently-dead
  features was found).
* `warmup_drift` -- the live detector computes features on a short trailing window; backtests
  compute them on long history. For recursive indicators (EMA, MACD, ATR, ADX, ...) the two
  differ by an amount that depends on the window. This measures the relative difference at
  the newest bar between a window and the full history.

Both take a deterministic synthetic OHLCV path by default, so results are reproducible. Pure
functions: no I/O, no network, nothing imported from another service.

Limits: `lookahead_report` can only see a leak that changes a value at the cut points it tries (a
whole-series maximum that happens to occur before every cut would pass), so it samples several cuts
and several trailing bars; it proves "no leak found on this path", not "no leak possible". It says
nothing about whether a value is CORRECT, only that it does not depend on the future.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

# Cumulative-from-the-first-bar indicators: their LEVEL depends on where the window starts, so a
# short live window can never reproduce a long-history level. Only changes over time are meaningful.
CUMULATIVE_FEATURES: frozenset[str] = frozenset({"obv", "accumulation_distribution_line", "vwap"})

Compute = Callable[[list[dict], Sequence[str]], list[dict]]


def synthetic_rows(n: int = 700, seed: int = 11) -> list[dict[str, Any]]:
    """A deterministic random-walk OHLCV series (daily timestamps) for reproducible checks."""
    rng = np.random.default_rng(seed)
    price = 100.0
    rows: list[dict[str, Any]] = []
    for i in range(n):
        o = price
        c = price * (1 + rng.normal(0.0003, 0.015))
        h = max(o, c) * (1 + abs(rng.normal(0, 0.004)))
        l = min(o, c) * (1 - abs(rng.normal(0, 0.004)))
        rows.append({
            "ts": 1_600_000_000 + i * 86400, "symbol": "X",
            "open": o, "high": h, "low": l, "close": c, "volume": float(rng.integers(500_000, 2_000_000)),
        })
        price = c
    return rows


def _default_compute() -> Compute:
    from vinu_tools.compute.registry import apply_indicators

    return apply_indicators


def _values_match(a: Any, b: Any, rel_tol: float, abs_tol: float = 1e-9) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        fa, fb = float(a), float(b)
    except (TypeError, ValueError):
        return a == b
    if math.isnan(fa) and math.isnan(fb):
        return True
    if math.isnan(fa) or math.isnan(fb):
        return False
    return abs(fa - fb) <= max(abs_tol, rel_tol * max(abs(fa), abs(fb)))


@dataclass(frozen=True)
class LookaheadViolation:
    feature: str
    cut: int          # the prefix length that was recomputed
    bar_index: int    # the bar whose value disagreed
    full_value: Any   # value when the whole series was available
    prefix_value: Any  # value when only bars up to `cut` were available


@dataclass
class LookaheadReport:
    violations: list[LookaheadViolation] = field(default_factory=list)
    # no non-None value at any checked bar: nothing was actually compared, so these are NOT verified clean
    unverifiable: list[str] = field(default_factory=list)
    n_features: int = 0

    @property
    def clean(self) -> bool:
        return not self.violations


def lookahead_report(
    names: Sequence[str],
    rows: list[dict] | None = None,
    *,
    cuts: Sequence[int] | None = None,
    bars_checked: int = 3,
    compute: Compute | None = None,
    rel_tol: float = 1e-9,
) -> LookaheadReport:
    """Check each feature in `names` for look-ahead. For every `cut` in `cuts` the series is
    truncated to `rows[:cut]`, recomputed, and the last `bars_checked` bars are compared with the
    same bars of the full-series run. Features are checked one at a time so a failure names its feature."""
    rows = rows if rows is not None else synthetic_rows()
    compute = compute or _default_compute()
    n = len(rows)
    cuts = list(cuts) if cuts is not None else [int(n * 0.43), int(n * 0.64), int(n * 0.86)]
    report = LookaheadReport(n_features=len(names))
    for name in names:
        full = compute(rows, [name])
        compared = 0
        violated = False
        for cut in cuts:
            if cut <= 0 or cut > n:
                continue
            prefix = compute(rows[:cut], [name])
            for k in range(cut - 1, max(cut - 1 - bars_checked, -1), -1):
                a, b = full[k].get(name), prefix[k].get(name)
                if a is not None or b is not None:
                    compared += 1
                if not _values_match(a, b, rel_tol):
                    report.violations.append(LookaheadViolation(name, cut, k, a, b))
                    violated = True
                    break
            if violated:
                break
        if compared == 0:
            report.unverifiable.append(name)
    return report


def warmup_drift(
    names: Sequence[str],
    *,
    window: int,
    rows: list[dict] | None = None,
    compute: Compute | None = None,
) -> dict[str, float | None]:
    """Relative difference at the newest bar between computing on only the last `window` bars (what a
    live poller sees) and on the full history (what a backtest sees). 0.0 = identical. None = one side
    had no value. Non-numeric features compare as equal (0.0) or different (1.0)."""
    rows = rows if rows is not None else synthetic_rows(max(window * 4, 800))
    compute = compute or _default_compute()
    if window < 2 or window > len(rows):
        raise ValueError(f"window must be in [2, {len(rows)}], got {window}")
    full = compute(rows, list(names))[-1]
    short = compute(rows[-window:], list(names))[-1]
    out: dict[str, float | None] = {}
    for name in names:
        a, b = short.get(name), full.get(name)
        if a is None or b is None:
            out[name] = None
            continue
        try:
            fa, fb = float(a), float(b)
        except (TypeError, ValueError):
            out[name] = 0.0 if a == b else 1.0
            continue
        out[name] = abs(fa - fb) / max(abs(fb), 1e-9)
    return out
