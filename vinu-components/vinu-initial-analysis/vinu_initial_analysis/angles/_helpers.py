from __future__ import annotations

from bisect import bisect_left, bisect_right
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


PERIODS_PER_YEAR: dict[str, int] = {
    "15min": 6552,
    "1H": 1638,
    "1D": 252,
    "1W": 52,
    "1M": 12,
    "6M": 2,
}


def periods_per_year(time_format: str) -> int:
    return PERIODS_PER_YEAR.get(time_format, 252)


def ann_factor(time_format: str) -> float:
    return float(periods_per_year(time_format) ** 0.5)


def bars_to_candle_list(bars: pd.DataFrame | None) -> list[dict]:
    if bars is None or bars.empty:
        return []
    if "bar_ts" not in bars.columns:
        return []
    return bars.to_dict("records")


def _compute_returns_series(candles: list[dict]) -> list[float]:
    sorted_c = sorted(candles, key=lambda x: x.get("bar_ts", 0))
    returns = []
    for i in range(1, len(sorted_c)):
        prev_close = sorted_c[i - 1].get("close", 0)
        curr_close = sorted_c[i].get("close", 0)
        if prev_close:
            returns.append((curr_close - prev_close) / prev_close)
    return returns


def _compute_returns_series_indexed(candles: list[dict]) -> dict[int, float]:
    """Same as _compute_returns_series but keyed by the later bar's bar_ts,
    so two different symbols' return series can be aligned by timestamp.
    """
    sorted_c = sorted(candles, key=lambda x: x.get("bar_ts", 0))
    out: dict[int, float] = {}
    for i in range(1, len(sorted_c)):
        prev_close = sorted_c[i - 1].get("close", 0)
        curr_close = sorted_c[i].get("close", 0)
        if prev_close:
            out[sorted_c[i].get("bar_ts", 0)] = (curr_close - prev_close) / prev_close
    return out


def compute_abnormal_return(
    candles: list[dict],
    event_ts: int,
    window_sec: int = 1800,
    estimation_window_sec: int = 604800,
    market_candles: list[dict] | None = None,
) -> dict[str, Any]:
    """Event-study abnormal return.

    Without market_candles: mean-adjusted-returns model — expected return
    is this stock's own average return over the estimation window. Simple,
    but attributes market-wide moves (e.g. a Fed announcement) to whatever
    news article happens to land in the same window.

    With market_candles (e.g. SPY): market-model — expected return is
    alpha + beta*market_return, with alpha/beta fit by OLS on the
    estimation window and applied to the market's ACTUAL return during
    the event window. This is the standard event-study upgrade (Brown &
    Warner 1985) and only activates when a market benchmark is available;
    callers that don't pass one keep today's behavior unchanged.
    """
    # candles must be sorted ascending by bar_ts; bisect keeps the
    # per-event windows O(log n) instead of full-list scans (Bug-7 fix).
    ts = [c.get("bar_ts", 0) for c in candles]
    lo = bisect_left(ts, event_ts - estimation_window_sec)
    pre_candles = candles[lo:bisect_left(ts, event_ts)]
    event_candles = candles[bisect_left(ts, event_ts):bisect_right(ts, event_ts + window_sec)]

    if len(pre_candles) < 10 or len(event_candles) < 2:
        return {
            "abnormal_return": 0.0,
            "car": 0.0,
            "ar_p_value": 1.0,
            "significant": False,
            "expected_return": 0.0,
            "model": "none",
        }

    pre_returns = _compute_returns_series(pre_candles)
    event_returns = _compute_returns_series(event_candles)

    market_result = None
    if market_candles:
        market_result = _try_market_model(
            pre_candles, event_candles, market_candles,
        )

    if market_result is not None:
        abnormal_returns, car, estimation_std, df, expected_return = market_result
        model = "market"
    else:
        expected_return = np.mean(pre_returns) if len(pre_returns) > 0 else 0.0
        abnormal_returns = [r - expected_return for r in event_returns]
        car = sum(abnormal_returns)
        pre_abnormal = [r - expected_return for r in pre_returns]
        estimation_std = float(np.std(pre_abnormal, ddof=1)) if len(pre_abnormal) > 1 else 0.0
        df = len(pre_abnormal) - 1
        model = "mean_adjusted"

    n_event = len(abnormal_returns)
    if n_event > 0 and estimation_std > 0 and df > 0:
        car_std = estimation_std * np.sqrt(n_event)
        t_stat = car / car_std
        p_value = float(2 * stats.t.sf(abs(t_stat), df=df))
    else:
        p_value = 1.0

    return {
        "abnormal_return": round(abnormal_returns[0], 6) if abnormal_returns else 0.0,
        "car": round(car, 6),
        "ar_p_value": round(float(p_value), 6),
        "significant": bool(p_value < 0.05),
        "expected_return": round(float(expected_return) if np.isscalar(expected_return) else float(np.mean(expected_return)), 6),
        "model": model,
    }


def _try_market_model(
    pre_candles: list[dict],
    event_candles: list[dict],
    market_candles: list[dict],
) -> tuple[list[float], float, float, int, float] | None:
    """OLS market-model fit. Returns (abnormal_returns, car, estimation_std,
    df, mean_expected_return) or None if there isn't enough timestamp-
    aligned overlap with the market series to fit a regression.
    """
    pre_stock = _compute_returns_series_indexed(pre_candles)
    market = _compute_returns_series_indexed(market_candles)
    event_stock = _compute_returns_series_indexed(event_candles)

    aligned_ts = sorted(set(pre_stock) & set(market))
    if len(aligned_ts) < 10:
        return None

    x = np.array([market[t] for t in aligned_ts])
    y = np.array([pre_stock[t] for t in aligned_ts])
    if np.std(x) == 0:
        return None

    beta, alpha = np.polyfit(x, y, 1)
    residuals = y - (alpha + beta * x)
    df = len(aligned_ts) - 2
    if df <= 0:
        return None
    estimation_std = float(np.std(residuals, ddof=0)) * np.sqrt(len(aligned_ts) / df)

    event_aligned_ts = sorted(set(event_stock) & set(market))
    if not event_aligned_ts:
        return None
    expected_returns = [alpha + beta * market[t] for t in event_aligned_ts]
    abnormal_returns = [event_stock[t] - exp_r for t, exp_r in zip(event_aligned_ts, expected_returns)]
    car = float(sum(abnormal_returns))
    return abnormal_returns, car, estimation_std, df, float(np.mean(expected_returns))


def classify_significance(ar_p_value: float) -> str:
    if ar_p_value < 0.01:
        return "highly_significant"
    elif ar_p_value < 0.05:
        return "significant"
    elif ar_p_value < 0.10:
        return "marginally_significant"
    return "insignificant"
