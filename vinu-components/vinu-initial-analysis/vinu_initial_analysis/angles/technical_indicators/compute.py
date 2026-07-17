"""Technical Indicator Landscape"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone


def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _compute_macd(series: pd.Series) -> tuple:
    ema12 = series.ewm(span=12).mean()
    ema26 = series.ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    return macd, signal


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
            "angle": "technical_indicators",
            "status": "no_data",
        }])

    close = bars["close"].astype(float)
    high = bars["high"].astype(float)
    low = bars["low"].astype(float)
    volume = bars["volume"].astype(float)
    analysis_at = datetime.now(timezone.utc).isoformat()

    indicators = {
        "sma_9": close.rolling(9).mean(),
        "sma_21": close.rolling(21).mean(),
        "sma_50": close.rolling(50).mean(),
        "sma_200": close.rolling(200).mean(),
        "ema_12": close.ewm(span=12).mean(),
        "ema_26": close.ewm(span=26).mean(),
        "rsi_14": _compute_rsi(close, 14),
        "rsi_7": _compute_rsi(close, 7),
        "adx_14": pd.Series(np.nan, index=close.index),
        "atr_14": (high - low).rolling(14).mean(),
        "volatility_20d": close.pct_change().rolling(20).std() * np.sqrt(252),
        "obv": (volume * ((close.diff() > 0).astype(int) * 2 - 1)).cumsum(),
        "daily_return": close.pct_change(),
        "high_low_spread": (high - low) / close,
    }

    macd, macd_signal = _compute_macd(close)
    indicators["macd"] = macd
    indicators["macd_signal"] = macd_signal

    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    indicators["bb_upper_20"] = bb_mid + 2 * bb_std
    indicators["bb_mid_20"] = bb_mid
    indicators["bb_lower_20"] = bb_mid - 2 * bb_std

    indicators["volume_ratio_20"] = volume / volume.rolling(20).mean()
    cmf = ((2 * close - high - low) / (high - low).replace(0, np.nan) * volume).rolling(20).sum() / volume.rolling(20).sum().replace(0, np.nan)
    indicators["cmf_20"] = cmf

    for name, series in indicators.items():
        last_val = series.dropna().iloc[-1] if len(series.dropna()) > 0 else None
        if isinstance(last_val, (np.floating,)):
            last_val = float(last_val) if not np.isnan(last_val) else None
        elif isinstance(last_val, (np.integer,)):
            last_val = int(last_val)
        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "technical_indicators",
            "indicator": name,
            "value": last_val,
            "n_observations": int(series.notna().sum()),
        })

    return pd.DataFrame(rows)
