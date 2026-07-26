from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timezone
from typing import Any


def _detect_shock_dates(
    bars: pd.DataFrame,
    gap_std_threshold: float = 2.0,
    vol_z_threshold: float = 2.0,
) -> list[str]:
    close = bars["close"].astype(float)
    open_p = bars["open"].astype(float)
    high = bars["high"].astype(float)
    low = bars["low"].astype(float)

    gaps = (open_p - close.shift(1)) / close.shift(1)
    gap_mean = gaps.mean()
    gap_std = gaps.std()

    daily_range = (high - low) / close
    vol_mean = daily_range.rolling(21).mean()
    vol_std = daily_range.rolling(21).std()

    shock_dates = []
    for i in range(len(bars)):
        date = bars.index[i] if hasattr(bars.index, '__getitem__') else str(bars.index[i])
        is_shock = False
        if not pd.isna(gaps.iloc[i]) and gap_std > 0:
            gap_z = (gaps.iloc[i] - gap_mean) / gap_std
            if abs(gap_z) > gap_std_threshold:
                is_shock = True
        if not is_shock and not pd.isna(vol_std.iloc[i]) and vol_std.iloc[i] > 0:
            vol_z = (daily_range.iloc[i] - vol_mean.iloc[i]) / vol_std.iloc[i]
            if vol_z > vol_z_threshold:
                is_shock = True
        if is_shock:
            shock_dates.append(str(date))
    return shock_dates


def _compute_shock_clusters(
    symbol: str,
    universe_prices: dict[str, np.ndarray],
    shock_dates: list[str],
    date_index: pd.Index,
    window: int = 63,
) -> dict[str, Any]:
    from vinu_tools.compute.risk.covariance import dynamic_covariance, correlation_from_covariance

    symbols = list(universe_prices.keys())
    if symbol not in symbols:
        symbols.append(symbol)

    n_assets = len(symbols)
    if n_assets < 2:
        return {
            "symbol": symbol,
            "cluster_members": [],
            "status": "single_symbol",
        }

    price_array = np.array([universe_prices[s] for s in symbols])
    cov = dynamic_covariance(price_array, window=window, use_shrinkage=True)
    corr = correlation_from_covariance(cov)

    symbol_idx = symbols.index(symbol)
    correlations = {}
    for i, other in enumerate(symbols):
        if i == symbol_idx:
            continue
        correlations[other] = float(corr[symbol_idx, i])

    sorted_members = sorted(correlations.items(), key=lambda x: -abs(x[1]))
    cluster_members = [
        {"symbol": sym, "shock_correlation": corr_val}
        for sym, corr_val in sorted_members
        if abs(corr_val) > 0.3
    ]

    return {
        "symbol": symbol,
        "cluster_members": cluster_members,
        "n_shock_dates": len(shock_dates),
        "shock_dates": shock_dates[:10],
        "status": "ok",
    }


def compute(
    symbol: str,
    bars: pd.DataFrame | None = None,
    news: list[dict] | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    time_format: str | None = None,
) -> pd.DataFrame:
    if bars is None or bars.empty:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": datetime.now(timezone.utc).isoformat(),
            "angle": "shock_clustering",
            "status": "no_data",
        }])

    analysis_at = datetime.now(timezone.utc).isoformat()
    shock_dates = _detect_shock_dates(bars)
    universe_prices = {symbol: bars["close"].astype(float).values}

    result = _compute_shock_clusters(symbol, universe_prices, shock_dates, bars.index)
    result["analysis_at"] = analysis_at
    result["angle"] = "shock_clustering"

    return pd.DataFrame([result])
