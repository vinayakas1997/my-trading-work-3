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


def rsi(s: pd.Series, period: int = 14) -> pd.Series:
    d = s.diff()
    gain = d.clip(lower=0.0)
    loss = -d.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    return out.where(avg_loss != 0.0, 100.0)


def macd(s: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    macd_line = ema(s, fast) - ema(s, slow)
    signal_line = ema(macd_line, signal)
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "hist": macd_line - signal_line})
