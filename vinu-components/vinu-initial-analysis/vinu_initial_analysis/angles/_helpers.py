from __future__ import annotations

from bisect import bisect_left, bisect_right
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


PERIODS_PER_YEAR: dict[str, int] = {
    # 15min/1H assume a 6.5-hour regular trading day x 252 trading days/year
    # (390min/15=26/day, 390min/60=6.5/day) -- 1min/5min/4H extend the same
    # convention (390/1=390, 390/5=78, 6.5/4=1.625 bars/day respectively);
    # added for 02-backtesting_44_metrics's decided 9-timeframe widening
    # (04-enhancement-of-each-angle/02-backtesting_44_metrics.md SS3) --
    # previously missing here, which would have silently fallen back to
    # 252 (the 1D value) via periods_per_year()'s .get(..., 252) default,
    # badly miscalculating ann_vol/cagr/sharpe/sortino/calmar for these
    # three timeframes.
    "1min": 98280,
    "5min": 19656,
    "15min": 6552,
    "1H": 1638,
    "4H": 410,
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
    candles_ts_index: list[int] | None = None,
    market_returns_indexed: dict[int, float] | None = None,
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

    `candles_ts_index`/`market_returns_indexed` let a caller that invokes
    this once per article (e.g. `compute_impact_for_article`, thousands of
    times per symbol against the same `candles`/`market_candles`) precompute
    these once outside that loop instead of paying for them on every call —
    rebuilding `ts` and re-sorting/re-indexing `market_candles` per call was
    an O(articles * total_bars) blowup that never finished for a
    several-thousand-article symbol over a multi-year range. Both are
    optional and computed on the fly if omitted, so single-call use
    (tests, other callers) is unaffected.
    """
    # candles must be sorted ascending by bar_ts; bisect keeps the
    # per-event windows O(log n) instead of full-list scans (Bug-7 fix).
    ts = candles_ts_index if candles_ts_index is not None else [c.get("bar_ts", 0) for c in candles]
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
            market_returns_indexed=market_returns_indexed,
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
    market_returns_indexed: dict[int, float] | None = None,
) -> tuple[list[float], float, float, int, float] | None:
    """OLS market-model fit. Returns (abnormal_returns, car, estimation_std,
    df, mean_expected_return) or None if there isn't enough timestamp-
    aligned overlap with the market series to fit a regression.
    """
    pre_stock = _compute_returns_series_indexed(pre_candles)
    market = market_returns_indexed if market_returns_indexed is not None else _compute_returns_series_indexed(market_candles)
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


def mean_with_ci(values: list[float], thin_floor: int = 10) -> dict[str, Any]:
    """Mean + sample size + 95% t-distribution CI -- the same shape
    pnl_attribution's own `_rate_with_ci` already used, generalized here
    since shock_personality needs the identical pattern for several
    different metrics (gap fill rate, drift persistence, mean
    autocorrelation, each also split by news presence -- 8+ call sites in
    one angle). `n < 2` -> `insufficient_sample` (can't fit a t-interval
    at all); `2 <= n < thin_floor` is still computed, not blocked, but
    gets a `note` flagging it as thin -- shock_personality's own decided
    "thin-sample caution below the hard floor" rule
    (04-enhancement-of-each-angle/25-shock_personality.md SS3).
    """
    n = len(values)
    if n < 2:
        return {
            "mean": float(np.mean(values)) if values else None,
            "n_observations": n,
            "confidence_interval": None,
            "status": "insufficient_sample",
        }
    mean = float(np.mean(values))
    se = float(np.std(values, ddof=1) / np.sqrt(n))
    ci = stats.t.interval(0.95, df=n - 1, loc=mean, scale=se)
    result: dict[str, Any] = {
        "mean": mean,
        "n_observations": n,
        "confidence_interval": [float(ci[0]), float(ci[1])],
        "status": "ok",
    }
    if n < thin_floor:
        result["note"] = f"thin sample, n<{thin_floor}"
    return result


def calendar_quarter_key(ts: int) -> str:
    """"YYYY-QN" real calendar quarter for a UTC unix timestamp -- coarser
    than `_tagging.tag_row`'s bare 1-4 `quarter` field (which has no
    year), needed wherever rows get grouped/sliced by real calendar
    quarter across multiple years. First needed by news_price_causality's
    aggregate-test slicing (04-enhancement-of-each-angle/19-news_price_causality.md
    SS3 — "per calendar quarter only"), reused by peer_relative_strength's
    forward-return validation slicing.
    """
    from datetime import datetime, timezone

    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    q = (dt.month - 1) // 3 + 1
    return f"{dt.year}-Q{q}"


def pearson_with_ci(x: np.ndarray, y: np.ndarray, n_bootstrap: int = 500) -> dict[str, float]:
    """Pearson correlation + bootstrapped 95% CI -- the same technique
    news_price_causality/correlation.py's `compute_correlation` uses,
    generalized here (that function is coupled to its own hourly-resample
    column names) so other angles can reuse the identical method rather
    than reinventing it. First reused by peer_relative_strength's
    forward-return validation (04-enhancement-of-each-angle/21-peer_relative_strength.md
    SS3: "same method already used in news_price_causality's correlation
    module").

    Uses `scipy.stats.bootstrap`'s `paired=True` mode to resample (x, y)
    pairs together, not `x`/`y` independently -- found and fixed during
    shock_clustering's (angle 24) real-data validation: passing
    `list(zip(x, y))` as a single un-paired sample (the original,
    correlation.py-inherited approach) lets scipy auto-vectorize the
    statistic function across bootstrap resamples in a way that silently
    decorrelates x from y per resample, collapsing the CI to the
    degenerate [-1, 1] on every real input tried, regardless of sample
    size or actual correlation strength -- confirmed via a direct A/B
    comparison against `paired=True` on the same synthetic data.
    """
    from scipy.stats import bootstrap, pearsonr

    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    if n < 5:
        return {"corr": 0.0, "p_value": 1.0, "ci_lower": 0.0, "ci_upper": 0.0, "sample_size": n}

    corr, p_value = pearsonr(x, y)

    def _stat(x_sample, y_sample):
        c, _ = pearsonr(x_sample, y_sample)
        return c

    try:
        boot = bootstrap(
            (x, y), _stat, n_resamples=n_bootstrap, confidence_level=0.95,
            method="percentile", paired=True, vectorized=False,
        )
        ci_lower, ci_upper = float(boot.confidence_interval.low), float(boot.confidence_interval.high)
        if not (np.isfinite(ci_lower) and np.isfinite(ci_upper)):
            # A small sample can draw a degenerate (constant) bootstrap
            # resample often enough that pearsonr returns NaN for some
            # resamples, poisoning the percentile CI -- falls back to a
            # zero-width CI at the real (non-bootstrapped) correlation
            # rather than surfacing NaN, same fallback as the except path.
            raise ValueError("degenerate bootstrap CI")
    except Exception:
        ci_lower = ci_upper = float(corr)

    return {
        "corr": round(float(corr), 4),
        "p_value": round(float(p_value), 6),
        "ci_lower": round(ci_lower, 4),
        "ci_upper": round(ci_upper, 4),
        "sample_size": n,
    }


def pinball_loss(q: float, forecast: float, actual: float) -> float:
    """Quantile (pinball) loss for one quantile level `q` — the standard
    proper scoring rule for a quantile forecast, penalizing under- and
    over-shoot asymmetrically per the target quantile. First needed by
    lag_llama (04-enhancement-of-each-angle/12-lag_llama.md SS3/SS7 — "no
    other angle's real code output is a full multi-level quantile
    forecast"), reused by moirai's narrower 2-level (p10/p90) band.
    """
    diff = actual - forecast
    return float(q * diff if diff >= 0 else (q - 1) * diff)


def classify_significance(ar_p_value: float) -> str:
    if ar_p_value < 0.01:
        return "highly_significant"
    elif ar_p_value < 0.05:
        return "significant"
    elif ar_p_value < 0.10:
        return "marginally_significant"
    return "insignificant"
