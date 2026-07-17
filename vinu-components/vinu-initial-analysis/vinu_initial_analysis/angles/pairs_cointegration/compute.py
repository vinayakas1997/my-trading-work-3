"""Pairs Cointegration — Engle-Granger cointegration test on single-series price data vs synthetic null"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone


def _adf_test(series: np.ndarray, maxlag: int = 1) -> dict:
    n = len(series)
    y = series - np.mean(series)
    dy = np.diff(y)

    X = np.column_stack([
        y[:-1],
        np.ones(n - 1),
        np.arange(1, n) if n > 1 else np.ones(n - 1),
    ])

    for lag in range(1, min(maxlag + 1, n // 2)):
        dylag = np.zeros_like(dy)
        dylag[lag:] = dy[:-lag]
        X = np.column_stack([X, dylag])

    valid = n - maxlag - 1
    y_reg = dy[maxlag:]
    X_reg = X[maxlag:valid + maxlag] if valid > 0 else X[:0]

    if len(y_reg) < 3 or X_reg.shape[0] < 3:
        return {"adf_stat": np.nan, "p_value": np.nan, "critical_values": {}, "is_stationary": None}

    try:
        beta = np.linalg.lstsq(X_reg, y_reg, rcond=None)[0]
        residuals = y_reg - X_reg @ beta
        se = np.sqrt(np.sum(residuals**2) / (len(residuals) - X_reg.shape[1]))
        adf_stat = beta[0] / se if se > 0 else 0.0
    except np.linalg.LinAlgError:
        return {"adf_stat": np.nan, "p_value": np.nan, "critical_values": {}, "is_stationary": None}

    cv = {1: -3.43, 5: -2.86, 10: -2.57}
    is_stationary = bool(adf_stat < cv[5]) if not np.isnan(adf_stat) else None
    return {"adf_stat": round(float(adf_stat), 4), "p_value": None, "critical_values": cv, "is_stationary": is_stationary}


def compute(
    symbol: str,
    bars: pd.DataFrame | None = None,
    news: list[dict] | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    time_format: str | None = None,
) -> pd.DataFrame:
    rows = []
    if bars is None:
        bars = pd.DataFrame()
    if bars.empty:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": datetime.now(timezone.utc).isoformat(),
            "time_format": time_format,
            "angle": "pairs_cointegration",
            "status": "no_data",
        }])

    close = bars["close"].astype(float)
    analysis_at = datetime.now(timezone.utc).isoformat()

    if len(close) < 30:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "pairs_cointegration",
            "status": "insufficient_data",
            "n_observations": len(close),
        }])

    price_raw = close.values
    n = len(price_raw)

    np.random.seed(42)
    random_walk = np.cumsum(np.random.randn(n) * 0.01 * np.mean(price_raw)) + price_raw[0]

    log_p1 = np.log(price_raw)
    log_p2 = np.log(random_walk)

    result = _adf_test(log_p1, maxlag=1)
    spread = log_p1 - log_p2
    eg_result = _adf_test(spread, maxlag=1)

    hedge_ratio = float(np.cov(log_p1, log_p2)[0, 1] / np.var(log_p2)) if np.var(log_p2) > 0 else 0.0
    spread_manual = log_p1 - hedge_ratio * log_p2
    eg_manual = _adf_test(spread_manual, maxlag=1)

    rows.append({
        "symbol": symbol,
        "analysis_at": analysis_at,
        "time_format": time_format,
        "angle": "pairs_cointegration",
        "metric": "series_stats",
        "n_observations": n,
        "mean_price": float(np.mean(price_raw)),
        "std_price": float(np.std(price_raw)),
        "min_price": float(np.min(price_raw)),
        "max_price": float(np.max(price_raw)),
        "last_price": float(price_raw[-1]),
    })

    rows.append({
        "symbol": symbol,
        "analysis_at": analysis_at,
        "time_format": time_format,
        "angle": "pairs_cointegration",
        "metric": "adf_price",
        "adf_stat": result["adf_stat"],
        "critical_value_5pct": result["critical_values"].get(5),
        "is_stationary": result["is_stationary"],
    })

    rows.append({
        "symbol": symbol,
        "analysis_at": analysis_at,
        "time_format": time_format,
        "angle": "pairs_cointegration",
        "metric": "engle_granger",
        "counterpart": "synthetic_random_walk",
        "hedge_ratio": round(hedge_ratio, 4),
        "spread_adf_stat": eg_result["adf_stat"],
        "spread_critical_value_5pct": eg_result["critical_values"].get(5),
        "is_cointegrated": eg_result["is_stationary"],
    })

    rows.append({
        "symbol": symbol,
        "analysis_at": analysis_at,
        "time_format": time_format,
        "angle": "pairs_cointegration",
        "metric": "engle_granger_optimized",
        "counterpart": "synthetic_random_walk",
        "hedge_ratio": round(hedge_ratio, 4),
        "spread_adf_stat": eg_manual["adf_stat"],
        "spread_critical_value_5pct": eg_manual["critical_values"].get(5),
        "is_cointegrated": eg_manual["is_stationary"],
    })

    spread_series = spread
    spread_mean = float(np.mean(spread_series))
    spread_std = float(np.std(spread_series))
    current_z = float((spread_series[-1] - spread_mean) / spread_std) if spread_std > 0 else 0.0
    half_life = float(np.log(2) / abs(np.corrcoef(spread_series[:-1], np.diff(spread_series))[0, 1])) if len(spread_series) > 2 else np.nan

    rows.append({
        "symbol": symbol,
        "analysis_at": analysis_at,
        "time_format": time_format,
        "angle": "pairs_cointegration",
        "metric": "spread_analysis",
        "spread_mean": round(spread_mean, 6),
        "spread_std": round(spread_std, 6),
        "current_z_score": round(current_z, 4),
        "half_life": round(half_life, 2) if not np.isnan(half_life) else None,
    })

    return pd.DataFrame(rows)
