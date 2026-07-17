from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


def compute_ic(
    factor_values: pd.DataFrame,
    forward_returns: pd.DataFrame,
) -> pd.Series:
    """Cross-sectional Spearman rank IC for each time period.

    Args:
        factor_values: T x N DataFrame of factor values.
        forward_returns: T x N DataFrame of forward returns (same time index).

    Returns:
        Series of IC values indexed by time.
    """
    common_idx = factor_values.index.intersection(forward_returns.index)
    fv = factor_values.loc[common_idx]
    fr = forward_returns.loc[common_idx]
    ics: list[float] = []
    valid_dates: list[pd.Timestamp] = []
    for t in common_idx:
        f = fv.loc[t].dropna()
        r = fr.loc[t].dropna()
        both = f.index.intersection(r.index)
        if len(both) < 10:
            continue
        ic, _ = spearmanr(f.loc[both], r.loc[both])
        ics.append(ic)
        valid_dates.append(t)
    return pd.Series(ics, index=pd.DatetimeIndex(valid_dates), name="IC")


def compute_ic_decay(
    factor_values: pd.DataFrame,
    forward_returns: pd.DataFrame,
    max_lag: int = 20,
) -> pd.Series:
    """Compute IC at each forward return lag to measure decay.

    For each lag ``d`` (1 to ``max_lag``), the IC is computed
    between the factor at time ``t`` and the forward return at
    ``t + d``. The resulting series shows how predictive power
    decays over time.

    Args:
        factor_values: T x N DataFrame of factor values.
        forward_returns: T x N DataFrame of forward returns.
        max_lag: Maximum number of forward periods to evaluate.

    Returns:
        Series indexed by lag (int), values are mean IC at each lag.
    """
    ics: list[float] = []
    lags: list[int] = []
    for d in range(1, max_lag + 1):
        fr_shifted = forward_returns.shift(-d)
        ic_series = compute_ic(factor_values, fr_shifted)
        if len(ic_series) == 0:
            continue
        ics.append(ic_series.mean())
        lags.append(d)
    return pd.Series(ics, index=pd.Index(lags, name="lag"), name="IC_decay")


def estimate_half_life(
    ic_decay_series: pd.Series,
    max_lag: int | None = None,
) -> float:
    """Estimate factor half-life from an IC decay curve.

    Fits an exponential decay model ``IC(lag) = IC_0 * exp(-lag / tau)``
    and returns ``tau * ln(2)``, the number of periods for IC to
    drop by 50%.

    Args:
        ic_decay_series: IC values indexed by lag (output of ``compute_ic_decay``).
        max_lag: Only use lags up to this value for fitting.

    Returns:
        Estimated half-life in periods. Returns ``inf`` if fitting fails.
    """
    from scipy.optimize import curve_fit

    series = ic_decay_series
    if max_lag is not None:
        series = series[series.index <= max_lag]
    if len(series) < 3:
        return float("inf")

    x = np.array(series.index, dtype=float)
    y = np.array(series.values, dtype=float)

    # Ensure starting value IC_0 is positive for exp model
    if y[0] <= 0:
        y = y - y.min() + 1e-6

    def exp_decay(t, ic0, tau):
        return ic0 * np.exp(-t / tau)

    try:
        popt, _ = curve_fit(
            exp_decay, x, y, p0=[y[0], max(x) / 2],
            bounds=(0, [np.inf, np.inf]), maxfev=5000,
        )
        tau = popt[1]
        return tau * np.log(2)
    except Exception:
        # Fallback: linear interpolation to find where IC drops by 50%
        half = y[0] / 2
        for i in range(1, len(y)):
            if y[i] <= half:
                frac = (half - y[i - 1]) / (y[i] - y[i - 1]) if y[i] != y[i - 1] else 0.0
                return float(x[i - 1] + frac * (x[i] - x[i - 1]))
        return float("inf")


def compute_turnover(
    factor_values: pd.DataFrame,
    quantile: float = 0.2,
) -> pd.Series:
    """Compute factor turnover — the fraction of stocks that change
    quantile membership each period.

    High turnover means the factor requires frequent rebalancing.

    Args:
        factor_values: T x N DataFrame of factor values.
        quantile: Top/bottom quantile threshold (default 0.2 = top/bottom 20%).

    Returns:
        Series of turnover values indexed by time (starting at period 1).
    """
    top = factor_values.rank(axis=1, pct=True) > (1 - quantile)
    bottom = factor_values.rank(axis=1, pct=True) < quantile

    turnover: list[float] = []
    dates: list[pd.Timestamp] = []
    for i in range(1, len(factor_values)):
        t = factor_values.index[i]
        t_prev = factor_values.index[i - 1]

        top_prev = top.loc[t_prev]
        bottom_prev = bottom.loc[t_prev]
        top_now = top.loc[t]
        bottom_now = bottom.loc[t]

        n = len(top_prev)
        if n == 0:
            continue

        # Combined top+bottom extreme groups
        extreme_prev = top_prev | bottom_prev
        extreme_now = top_now | bottom_now

        changed = (extreme_prev & ~extreme_now).sum() + (~extreme_prev & extreme_now).sum()
        turnover.append(changed / n)
        dates.append(t)

    return pd.Series(turnover, index=pd.DatetimeIndex(dates), name="turnover")
