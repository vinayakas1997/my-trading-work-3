"""Snapshot capture -- at every peak/trough, compute ALL indicators as a flat feature vector.

Every column uses FIXED periods that never change.
This guarantees Peak_A and Peak_B are directly comparable forever.
"""

from __future__ import annotations

import pandas as pd
import numpy as np


_LOOKAHEAD_BARS = {
    "1D": 60,
    "1W": 60,
    "4H": 120,
    "1H": 120,
    "15min": 240,
}


def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean().replace(0, np.nan)
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _compute_macd(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    ema12 = series.ewm(span=12).mean()
    ema26 = series.ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    return macd, signal


def _compute_all_indicators(bars: pd.DataFrame) -> pd.DataFrame:
    """Compute ALL indicators for every bar and return as a DataFrame aligned to bars index."""
    close = bars["close"].astype(float)
    high = bars["high"].astype(float)
    low = bars["low"].astype(float)
    vol = bars["volume"].astype(float)

    rows = []
    indicators = {}

    indicators["sma_9"] = close.rolling(9).mean()
    indicators["sma_21"] = close.rolling(21).mean()
    indicators["sma_50"] = close.rolling(50).mean()
    indicators["sma_200"] = close.rolling(200).mean()
    indicators["ema_12"] = close.ewm(span=12).mean()
    indicators["ema_26"] = close.ewm(span=26).mean()

    indicators["rsi_14"] = _compute_rsi(close, 14)
    indicators["rsi_7"] = _compute_rsi(close, 7)

    macd_line, macd_signal = _compute_macd(close)
    indicators["macd"] = macd_line
    indicators["macd_signal"] = macd_signal
    indicators["macd_hist"] = macd_line - macd_signal

    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    indicators["atr_14"] = tr.rolling(14).mean()
    indicators["volatility_20d"] = close.pct_change().rolling(20).std()

    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    indicators["bb_upper_20"] = bb_mid + 2 * bb_std
    indicators["bb_mid_20"] = bb_mid
    indicators["bb_lower_20"] = bb_mid - 2 * bb_std
    indicators["bb_width_pct"] = (bb_mid + 2 * bb_std - (bb_mid - 2 * bb_std)) / bb_mid

    indicators["obv"] = (vol * ((close.diff() > 0).astype(int) * 2 - 1)).cumsum()
    indicators["volume_ratio_20"] = vol / vol.rolling(20).mean()
    indicators["volume_zscore_20"] = (vol - vol.rolling(20).mean()) / vol.rolling(20).std().replace(0, np.nan)
    cmf = ((2 * close - high - low) / (high - low).replace(0, np.nan) * vol).rolling(20).sum() / vol.rolling(20).sum().replace(0, np.nan)
    indicators["cmf_20"] = cmf

    indicators["daily_return"] = close.pct_change()
    indicators["high_low_spread"] = (high - low) / close
    indicators["close_sma_9_pct"] = (close - indicators["sma_9"]) / indicators["sma_9"]
    indicators["close_sma_50_pct"] = (close - indicators["sma_50"]) / indicators["sma_50"]
    indicators["close_sma_200_pct"] = (close - indicators["sma_200"]) / indicators["sma_200"]

    # ADX and ADX slope (raw 5-bar difference per spec)
    adx_period = 14
    high_diff = high.diff()
    low_diff = low.diff()
    plus_dm_arr = np.where((high_diff > low_diff.abs()) & (high_diff > 0), high_diff, 0)
    minus_dm_arr = np.where((low_diff.abs() > high_diff) & (low_diff < 0), low_diff.abs(), 0)
    plus_dm = pd.Series(plus_dm_arr, index=high.index)
    minus_dm = pd.Series(minus_dm_arr, index=low.index)
    smoothed_tr = tr.ewm(alpha=1 / adx_period, adjust=False).mean().replace(0, np.nan)
    smoothed_plus_dm = plus_dm.ewm(alpha=1 / adx_period, adjust=False).mean()
    smoothed_minus_dm = minus_dm.ewm(alpha=1 / adx_period, adjust=False).mean()
    plus_di = 100 * smoothed_plus_dm / smoothed_tr
    minus_di = 100 * smoothed_minus_dm / smoothed_tr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / adx_period, adjust=False).mean()
    indicators["adx_14"] = adx
    indicators["adx_slope_5"] = adx - adx.shift(5)

    # CCI_20
    tp = (high + low + close) / 3
    tp_sma = tp.rolling(20).mean()
    tp_mad = tp.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean())
    indicators["cci_20"] = (tp - tp_sma) / (0.015 * tp_mad.replace(0, np.nan))

    # Williams %R_14
    hh_14 = high.rolling(14).max()
    ll_14 = low.rolling(14).min()
    indicators["williams_r_14"] = -100 * (hh_14 - close) / (hh_14 - ll_14).replace(0, np.nan)

    # Stochastic %K_14, %D_14
    stoch_k = 100 * (close - ll_14) / (hh_14 - ll_14).replace(0, np.nan)
    indicators["stoch_k_14"] = stoch_k
    indicators["stoch_d_14"] = stoch_k.rolling(3).mean()

    df = pd.DataFrame(indicators, index=bars.index)
    return df


def compute_indicators(bars: pd.DataFrame) -> pd.DataFrame:
    """Compute the full indicator frame once so callers can reuse it across captures."""
    return _compute_all_indicators(bars)


def _compute_candle_shape(bars: pd.DataFrame, idx: int) -> dict:
    """Compute candle shape metrics at the given bar index."""
    o, h, l, c = (
        bars["open"].iloc[idx],
        bars["high"].iloc[idx],
        bars["low"].iloc[idx],
        bars["close"].iloc[idx],
    )
    candle_range = h - l
    if candle_range == 0:
        return {"upper_wick_pct": 0.0, "body_size_pct": 0.0}
    upper_wick = h - max(o, c)
    body = abs(c - o)
    return {
        "upper_wick_pct": round(upper_wick / candle_range, 4),
        "body_size_pct": round(body / candle_range, 4),
    }


def _compute_session_label(bars: pd.DataFrame, idx: int) -> str:
    """Determine session label (premarket/regular/afterhours) based on bar timestamp."""
    if "bar_ts" not in bars.columns:
        return "unknown"
    ts = bars["bar_ts"].iloc[idx]
    if pd.isna(ts):
        return "unknown"
    dt = pd.Timestamp(ts, unit="s", tz="UTC")
    et = dt.tz_convert("America/New_York")
    hour = et.hour
    minute = et.minute
    total_min = hour * 60 + minute
    if total_min < 4 * 60 + 0:
        return "closed"
    elif total_min < 9 * 60 + 30:
        return "premarket"
    elif total_min < 16 * 60 + 0:
        return "regular"
    else:
        return "afterhours"


def _calculate_peak_outcomes(bars: pd.DataFrame, idx: int, peak_high: float, tf: str = "1D") -> tuple:
    """Scan forward from peak to compute drawdown and recovery bars.

    Scans up to max lookahead bars. Returns (drawdown_pct, recovery_time_bars, mature).
    drawdown_pct is negative (loss). recovery_time_bars is bars to first close >= peak_high.
    mature is False when the full lookahead window is not yet available — such
    outcomes are provisional and must be recomputed on later runs.
    """
    max_bars = _LOOKAHEAD_BARS.get(tf, 60)
    n = len(bars)
    end = min(idx + max_bars, n)
    mature = (idx + max_bars) <= n
    if end <= idx + 1:
        return None, None, False

    closes = bars["close"].astype(float).values
    lows = bars["low"].astype(float).values

    recovery_bars = None
    for j in range(idx + 1, end):
        if closes[j] >= peak_high:
            recovery_bars = j - idx
            # Recovery observed — outcome is final even if window was truncated
            mature = True
            break

    # Drawdown is measured peak -> lowest low BEFORE recovery (or full window)
    dd_end = idx + recovery_bars + 1 if recovery_bars is not None else end
    min_low = lows[idx:dd_end].min()
    drawdown_pct = round(float((min_low - peak_high) / peak_high), 4)

    return drawdown_pct, recovery_bars, mature


def capture_snapshot(
    bars: pd.DataFrame,
    indicators_df: pd.DataFrame,
    idx: int,
    inflection_type: str,
    prev_trough_idx: int | None = None,
    prev_peak_idx: int | None = None,
    prev_peak_close: float | None = None,
    tf: str = "1D",
) -> dict:
    """Capture a full indicator snapshot at the given bar index.

    Returns a flat dict with all identity, context, indicator, and structure columns.
    """
    if idx >= len(bars) or idx >= len(indicators_df):
        return {}
    bar = bars.iloc[idx]
    ind = indicators_df.iloc[idx]
    ts = int(bars["bar_ts"].iloc[idx]) if "bar_ts" in bars.columns else 0

    # day_of_week / hour in Eastern Time, consistent with the session label
    day_of_week = -1
    hour = -1
    if ts > 0:
        et = pd.Timestamp(ts, unit="s", tz="UTC").tz_convert("America/New_York")
        day_of_week = et.dayofweek
        hour = et.hour

    vol_raw = bar["volume"] if "volume" in bar else None
    peak_volume = int(vol_raw) if vol_raw is not None and pd.notna(vol_raw) else 0

    snapshot = {
        "type": "snapshot",
        "peak_id": f"{ts}_{inflection_type}",
        "inflection_type": inflection_type,
        "bar_ts": ts,
        "bar_idx": int(idx),
        "peak_close": round(float(bar["close"]), 2),
        "peak_high": round(float(bar["high"]), 2),
        "peak_low": round(float(bar["low"]), 2),
        "peak_volume": peak_volume,
        "session": _compute_session_label(bars, idx),
        "day_of_week": day_of_week,
        "hour": hour,
    }

    indicators_to_store = [
        "sma_9", "sma_21", "sma_50", "sma_200",
        "ema_12", "ema_26",
        "rsi_14", "rsi_7",
        "macd", "macd_signal", "macd_hist",
        "atr_14", "volatility_20d",
        "bb_upper_20", "bb_mid_20", "bb_lower_20", "bb_width_pct",
        "obv", "volume_ratio_20", "volume_zscore_20", "cmf_20",
        "daily_return", "high_low_spread",
        "close_sma_9_pct", "close_sma_50_pct", "close_sma_200_pct",
        "adx_14", "adx_slope_5",
        "cci_20", "williams_r_14", "stoch_k_14", "stoch_d_14",
    ]
    for col in indicators_to_store:
        val = ind.get(col) if hasattr(ind, "get") else ind[col] if col in ind else None
        if val is not None and (isinstance(val, float) or isinstance(val, np.floating)):
            val = float(val) if not np.isnan(val) else None
        elif isinstance(val, np.integer):
            val = int(val)
        snapshot[col] = val

    candle_shape = _compute_candle_shape(bars, idx)
    snapshot["upper_wick_pct"] = candle_shape["upper_wick_pct"]
    snapshot["body_size_pct"] = candle_shape["body_size_pct"]

    # Scale-invariant ATR for pattern matching (spec section 6: ATR / Close)
    atr_val = snapshot.get("atr_14")
    close_val = float(bar["close"])
    if atr_val is not None and close_val > 0:
        snapshot["atr_pct"] = round(float(atr_val) / close_val, 6)
    else:
        snapshot["atr_pct"] = None

    if inflection_type == "peak" and prev_trough_idx is not None:
        snapshot["runup_bars"] = int(idx - prev_trough_idx)
        trough_close = float(bars["close"].iloc[prev_trough_idx])
        snapshot["return_from_prev_trough"] = round((float(bar["close"]) - trough_close) / trough_close, 4)
        internal_dips = 0
        for j in range(prev_trough_idx + 1, idx):
            if float(bars["close"].iloc[j]) < float(bars["low"].iloc[j - 1]):
                internal_dips += 1
        snapshot["internal_dips_count"] = internal_dips
    else:
        snapshot["runup_bars"] = None
        snapshot["return_from_prev_trough"] = None
        snapshot["internal_dips_count"] = None

    if inflection_type == "peak" and prev_peak_close is not None:
        snapshot["peak_ratio"] = round(float(bar["close"]) / prev_peak_close, 4)
    else:
        snapshot["peak_ratio"] = None

    # RSI divergence: RSI_14 at current peak - RSI_14 at previous peak (spec line 120)
    if inflection_type == "peak" and prev_peak_idx is not None:
        if prev_peak_idx < len(indicators_df):
            prev_rsi = indicators_df.iloc[prev_peak_idx].get("rsi_14")
            curr_rsi = ind.get("rsi_14")
            if prev_rsi is not None and curr_rsi is not None:
                snapshot["rsi_divergence"] = round(float(curr_rsi) - float(prev_rsi), 4)
            else:
                snapshot["rsi_divergence"] = None
        else:
            snapshot["rsi_divergence"] = None
    else:
        snapshot["rsi_divergence"] = None

    # Relaxation bars: for peaks scan backward, for troughs scan forward
    relaxation_bars = 0
    if inflection_type == "peak":
        for j in range(idx - 1, max(idx - 15, 0), -1):
            c = float(bars["close"].iloc[j])
            if c <= float(bar["close"]) * 1.01 and c >= float(bar["close"]) * 0.99:
                relaxation_bars += 1
            else:
                break
    else:  # trough — count forward bars that stay near trough close
        n = len(bars)
        for j in range(idx + 1, min(idx + 15, n)):
            c = float(bars["close"].iloc[j])
            if c <= float(bar["close"]) * 1.02 and c >= float(bar["close"]) * 0.98:
                relaxation_bars += 1
            else:
                break
    snapshot["relaxation_bars"] = relaxation_bars

    # Outcome fields (will be backfilled by caller for peaks).
    # outcome_mature=False marks provisional outcomes computed on a truncated
    # forward window — they get recomputed on later runs once more bars exist.
    snapshot["drawdown_pct"] = None
    snapshot["recovery_time_bars"] = None
    snapshot["outcome_mature"] = False
    snapshot["trough_price"] = None
    snapshot["trough_ts"] = None
    snapshot["next_peak_price"] = None
    snapshot["total_swing_pct"] = None

    if inflection_type == "peak":
        drawdown_pct, recovery_bars, mature = _calculate_peak_outcomes(bars, idx, float(bar["high"]), tf)
        snapshot["drawdown_pct"] = drawdown_pct
        snapshot["recovery_time_bars"] = recovery_bars
        snapshot["outcome_mature"] = mature

    if inflection_type == "trough" and prev_peak_close is not None and prev_peak_close > 0:
        trough_c = float(bar["close"])
        # Drawdown = how far price fell from the previous peak to this trough
        snapshot["drawdown_pct"] = round((trough_c - prev_peak_close) / prev_peak_close, 4)
        # Recovery = bars forward until close closes back above prev peak level
        n = len(bars)
        max_bars = _LOOKAHEAD_BARS.get(tf, 60)
        recovery_bars = None
        for j in range(idx + 1, min(idx + max_bars, n)):
            if float(bars["close"].iloc[j]) >= prev_peak_close:
                recovery_bars = j - idx
                break
        snapshot["recovery_time_bars"] = recovery_bars
        snapshot["outcome_mature"] = recovery_bars is not None or (idx + max_bars) <= n

    return snapshot


def capture_all_peaks(
    bars: pd.DataFrame,
    peaks: list[dict],
    prev_troughs: list[dict],
    prev_peaks: list[dict],
    tf: str = "1D",
    indicators_df: pd.DataFrame | None = None,
) -> list[dict]:
    """Capture snapshots for all detected peaks, then backfill outcome fields."""
    if bars.empty:
        return []
    if indicators_df is None:
        indicators_df = _compute_all_indicators(bars)
    snapshots = []
    sorted_troughs = sorted(prev_troughs, key=lambda x: x["idx"])
    sorted_peaks = sorted(prev_peaks, key=lambda x: x["idx"])

    for peak in peaks:
        idx = peak["idx"]
        prev_trough_idx = None
        for t in reversed(sorted_troughs):
            if t["idx"] < idx:
                prev_trough_idx = t["idx"]
                break
        prev_peak_idx = None
        prev_peak_close = None
        for p in reversed(sorted_peaks):
            if p["idx"] < idx:
                prev_peak_idx = p["idx"]
                prev_peak_close = p.get("peak_close")
                break
        snap = capture_snapshot(
            bars, indicators_df, idx, "peak",
            prev_trough_idx=prev_trough_idx,
            prev_peak_idx=prev_peak_idx,
            prev_peak_close=prev_peak_close,
            tf=tf,
        )
        if snap:
            snapshots.append(snap)

    # Backfill outcome fields that reference subsequent extrema
    for snap in snapshots:
        idx = snap["bar_idx"]
        next_trough = None
        for t in sorted_troughs:
            if t["idx"] > idx:
                next_trough = t
                break
        if next_trough is not None:
            snap["trough_price"] = next_trough.get("trough_low")
            snap["trough_ts"] = next_trough.get("bar_ts")
            next_peak = None
            for p in sorted_peaks:
                if p["idx"] > next_trough["idx"]:
                    next_peak = p
                    break
            if next_peak is not None:
                snap["next_peak_price"] = next_peak.get("peak_close")
                snap["total_swing_pct"] = round(
                    (next_peak["peak_close"] - snap["peak_close"]) / snap["peak_close"], 4
                )
            else:
                snap["next_peak_price"] = None
                snap["total_swing_pct"] = None
        else:
            snap["trough_price"] = None
            snap["trough_ts"] = None
            snap["next_peak_price"] = None
            snap["total_swing_pct"] = None

    return snapshots


def capture_all_troughs(
    bars: pd.DataFrame,
    troughs: list[dict],
    prev_peaks: list[dict] | None = None,
    tf: str = "1D",
    indicators_df: pd.DataFrame | None = None,
) -> list[dict]:
    """Capture snapshots for all detected troughs.

    prev_peaks is used to compute drawdown_pct and recovery_time_bars
    (how far from the previous peak, and how long to recover back to it).
    """
    if bars.empty or not troughs:
        return []
    if indicators_df is None:
        indicators_df = _compute_all_indicators(bars)
    sorted_peaks = sorted(prev_peaks, key=lambda x: x["idx"]) if prev_peaks else []
    snapshots = []
    for trough in troughs:
        idx = trough["idx"]
        # Find the most recent peak before this trough
        prev_peak_close = None
        for p in reversed(sorted_peaks):
            if p["idx"] < idx:
                prev_peak_close = p.get("peak_close")
                break
        snap = capture_snapshot(
            bars, indicators_df, idx, "trough",
            prev_peak_close=prev_peak_close,
            tf=tf,
        )
        if snap:
            snapshots.append(snap)
    return snapshots
