"""Stage C (C13): data-derived stress windows.

`_run_stress_test` replays a candidate strategy through *fixed* historical
crisis windows (2020 COVID, 2022 rate-hike). Those are the same for every
symbol and can miss a symbol's own worst stretch. This module derives
extra windows from the symbol's actual price path over the researched
range — its deepest drawdown, its sharpest run-up, its steepest sustained
decline — so the stress check also asks "what does this strategy do in
*this instrument's* worst regime", not only in the market-wide ones.

Pure functions, no I/O. Takes a price (or cumulative-return) series;
returns `(name, from_date, to_date)` tuples in the same shape as
`ResearchConfig.stress_test_windows`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _fmt(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def _max_drawdown_window(s: pd.Series) -> tuple[str, str] | None:
    """Peak-to-trough span of the deepest drawdown in `s`."""
    running_max = s.cummax()
    dd = s / running_max - 1.0
    if dd.empty:
        return None
    trough_i = int(dd.values.argmin())
    if dd.iloc[trough_i] >= -1e-9:
        return None
    # the peak is the last index at/before the trough where s == running_max
    peak_i = int(np.where(s.values[: trough_i + 1] >= running_max.values[trough_i] - 1e-12)[0][-1])
    if trough_i <= peak_i:
        return None
    return _fmt(s.index[peak_i]), _fmt(s.index[trough_i])


def _max_runup_window(s: pd.Series) -> tuple[str, str] | None:
    """Trough-to-peak span of the largest gain (mirror of drawdown)."""
    running_min = s.cummin()
    runup = s / running_min - 1.0
    if runup.empty:
        return None
    peak_i = int(runup.values.argmax())
    if runup.iloc[peak_i] <= 1e-9:
        return None
    trough_i = int(np.where(s.values[: peak_i + 1] <= running_min.values[peak_i] + 1e-12)[0][-1])
    if peak_i <= trough_i:
        return None
    return _fmt(s.index[trough_i]), _fmt(s.index[peak_i])


def _steepest_decline_window(s: pd.Series, win: int) -> tuple[str, str] | None:
    """The `win`-bar sub-window with the most negative linear slope
    (normalised by price level)."""
    n = len(s)
    if n < win:
        return None
    x = np.arange(win, dtype=float)
    x = x - x.mean()
    denom = float((x * x).sum()) or 1.0
    vals = s.values.astype(float)
    best_slope = np.inf
    best_start = -1
    for start in range(0, n - win + 1):
        y = vals[start : start + win]
        level = y.mean() or 1.0
        slope = float((x * (y - y.mean())).sum() / denom) / level
        if slope < best_slope:
            best_slope = slope
            best_start = start
    if best_start < 0 or best_slope >= 0:
        return None
    return _fmt(s.index[best_start]), _fmt(s.index[best_start + win - 1])


def derive_regime_windows(
    series: pd.Series | None,
    *,
    min_window_days: int = 15,
    decline_window_days: int = 30,
) -> list[tuple[str, str, str]]:
    """Return up to three derived stress windows. `series` may be a price
    series or a cumulative-return path (only relative peak/trough structure
    matters). Empty list when the input is too short or flat."""
    if series is None or len(series) < min_window_days + 5:
        return []
    s = series.dropna()
    if not isinstance(s.index, pd.DatetimeIndex):
        try:
            s.index = pd.to_datetime(s.index)
        except Exception:
            return []
    s = s.sort_index()
    if len(s) < min_window_days + 5 or float(s.std()) == 0.0:
        return []

    out: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _add(name: str, span: tuple[str, str] | None) -> None:
        if not span:
            return
        f, t = span
        if f == t or (f, t) in seen:
            return
        if (pd.Timestamp(t) - pd.Timestamp(f)).days < min_window_days:
            return
        seen.add((f, t))
        out.append((name, f, t))

    _add("derived_max_drawdown", _max_drawdown_window(s))
    _add("derived_max_runup", _max_runup_window(s))
    _add("derived_steepest_decline", _steepest_decline_window(s, min(decline_window_days, len(s))))
    return out
