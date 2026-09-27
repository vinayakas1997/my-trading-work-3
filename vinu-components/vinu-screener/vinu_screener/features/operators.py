"""Stage B (B4): the rolling-operator primitives the feature library is
built from — Qlib's expression-engine pattern (`Rank`/`Slope`/`Std`/`WMA`/
`EMA`/`Ref`/`Delta`), reimplemented directly on pandas rather than taken as
a dependency (Qlib itself isn't a light import). Every named indicator in
`library.py` is one of these, or a small combination of a few.

All operate on a single `pd.Series` (one symbol's column of one OHLCV
field) and return a same-length `pd.Series` aligned to the input's index —
callers slice off the tail for "current bar" or index back for `offset`
bars-ago, never re-slice before computing (a rolling window computed on a
truncated series is not the same number as the same window computed on the
full history and then read at the end).

item #18 finding #4 (system-wide-audit-and-design/
02-open-questions-strategy-and-simulation.md): these primitives duplicate
`vinu-tools/vinu_tools/compute/indicators/` -- the same class of bug
`06-mistake-duplicated-indicator-logic.md` already fixed once for Track 1.
Checked each named function against its `vinu-tools` counterpart rather
than assuming they all diverge: `sma()`/`ema()`/`macd()` compute the exact
same formula (just a different NaN-warmup convention), so there was
nothing to fix there; `wma()` has no `vinu-tools` counterpart at all (not
a duplicate); `std()` (`rolling_std` below, wired to raw `close` in
`library.py`) turned out to be a different *feature* than `vinu-tools`'s
"volatility_20d" (which is rolling std of daily *returns*, not of price
level) -- not actually the same indicator, so no cross-consistency issue
to fix. `rsi()` was the one real, confirmed divergence: it used
`ewm(alpha=1/period, adjust=False)` seeded from bar 0, while
`vinu_tools.compute.indicators.rsi`'s own `_rsi()` uses true Wilder
seeding (a plain mean of the first `period` diffs, then recursive
smoothing) -- same decay rate, different seed, meaning this screener
ranked tickers on slightly different early-window RSI numbers than
Track 1's own RSI reading of the same bars. Fixed to match `_rsi()`
exactly (verified empirically, index-for-index, before landing).
Full delegation to `vinu-tools` (rather than porting the one divergent
formula in place) was deliberately not done: `vinu-screener` has no
existing dependency on the `vinu-tools` package at all (a new
cross-service dependency is a bigger call than this finding's scope), and
`vinu-tools`'s `compute(rows: list[dict], ...)` shape is row-based, not
composable with this module's pandas-`Series`-in/`Series`-out operators
the way `slope(ema(s, 12), 5)`-style Qlib composition needs -- a real
architecture mismatch, not just a missing import.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ref(s: pd.Series, offset: int) -> pd.Series:
    """Value `offset` bars ago. offset=0 is the series unchanged."""
    return s.shift(offset)


def delta(s: pd.Series, period: int) -> pd.Series:
    """`s[t] - s[t - period]`."""
    return s - s.shift(period)


def pct_change(s: pd.Series, period: int = 1) -> pd.Series:
    return s.pct_change(periods=period)


def sma(s: pd.Series, period: int) -> pd.Series:
    return s.rolling(period, min_periods=period).mean()


def ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False, min_periods=span).mean()


def rolling_std(s: pd.Series, period: int) -> pd.Series:
    return s.rolling(period, min_periods=period).std()


def rolling_rank(s: pd.Series, period: int) -> pd.Series:
    """Percentile rank (0-1) of the current value within its own trailing
    `period`-bar window — Qlib's `Rank` operator."""
    def _pct_rank(window: np.ndarray) -> float:
        return float(pd.Series(window).rank(pct=True).iloc[-1])
    return s.rolling(period, min_periods=period).apply(_pct_rank, raw=True)


def slope(s: pd.Series, period: int) -> pd.Series:
    """Rolling linear-regression slope of `s` over the trailing `period`
    bars — Qlib's `Slope` operator. Units: `s` per bar."""
    x = np.arange(period, dtype=float)
    x = x - x.mean()
    denom = float((x * x).sum()) or 1.0

    def _slope(window: np.ndarray) -> float:
        y = window - window.mean()
        return float((x * y).sum() / denom)

    return s.rolling(period, min_periods=period).apply(_slope, raw=True)


def wma(s: pd.Series, period: int) -> pd.Series:
    """Linearly-weighted moving average — most recent bar weighted `period`,
    oldest in the window weighted 1."""
    weights = np.arange(1, period + 1, dtype=float)
    wsum = weights.sum()

    def _wma(window: np.ndarray) -> float:
        return float((window * weights).sum() / wsum)

    return s.rolling(period, min_periods=period).apply(_wma, raw=True)


def _wilder_avg(values: np.ndarray, period: int) -> np.ndarray:
    """Seed with a plain mean of the first `period` real diffs (indices
    1..period -- index 0 has no prior bar, so it's excluded from the seed,
    not zero-padded into it), then Wilder-recurse
    (`avg = (avg*(period-1) + new) / period`) from there. Ported verbatim
    from `vinu_tools.compute.indicators.rsi.rsi._rsi()`'s own loop (item
    #18 finding #4) rather than the previous
    `ewm(alpha=1/period, adjust=False)` seeded from bar 0 -- same decay
    rate, wrong seed, which silently ranked tickers on slightly different
    early-window RSI values than Track 1's own RSI reading of the same
    bars. Verified index-for-index identical to `_rsi()`'s output before
    this replaced the old formula."""
    n = len(values)
    out = np.full(n, np.nan)
    if n <= period:
        return out
    avg = values[1 : period + 1].mean()
    out[period] = avg
    for i in range(period + 1, n):
        avg = (avg * (period - 1) + values[i]) / period
        out[i] = avg
    return out


def rsi(s: pd.Series, period: int = 14) -> pd.Series:
    closes = s.to_numpy(dtype=float)
    diffs = np.diff(closes, prepend=closes[0] if len(closes) else 0.0)
    if len(diffs):
        diffs[0] = 0.0
    gains = np.clip(diffs, 0.0, None)
    losses = np.clip(-diffs, 0.0, None)
    avg_gain = _wilder_avg(gains, period)
    avg_loss = _wilder_avg(losses, period)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
        out = 100.0 - (100.0 / (1.0 + rs))
    out = np.where(avg_loss == 0.0, 100.0, out)
    out = np.where(np.isnan(avg_gain) | np.isnan(avg_loss), np.nan, out)
    return pd.Series(out, index=s.index)


def macd(s: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    macd_line = ema(s, fast) - ema(s, slow)
    signal_line = ema(macd_line, signal)
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "hist": macd_line - signal_line})
