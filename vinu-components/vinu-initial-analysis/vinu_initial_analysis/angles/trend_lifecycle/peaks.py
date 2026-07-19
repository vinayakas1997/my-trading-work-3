"""Peak/trough detection using custom rolling-window method.

Detects extrema with 20-bar lookback and 3-bar forward confirmation.
Guarantees detection at the right edge (no boundary issues like argrelextrema).
"""

from __future__ import annotations

import pandas as pd
import numpy as np


def detect_peaks(
    bars: pd.DataFrame,
    min_drop_pct: float = 0.0,
    lookback: int = 20,
    confirm_bars: int = 3,
    atr_series: pd.Series | None = None,
) -> list[dict]:
    """Detect peaks: price > max(prev `lookback`) AND next `confirm_bars` close < peak_close.

    Uses per-bar dynamic ATR threshold when atr_series is provided. The hard-coded
    min_drop_pct is an absolute floor: the required drop is the LARGER magnitude of
    the floor or 2 * ATR / close, i.e. min() on signed negative values.

    Returns list of dicts with peak index, timestamp, price, etc.
    """
    if bars is None or bars.empty or len(bars) < lookback + confirm_bars + 1:
        return []
    close = bars["close"].astype(float).values
    high = bars["high"].astype(float).values
    ts = bars["bar_ts"].values if "bar_ts" in bars.columns else np.arange(len(bars))
    atr_vals = atr_series.values if atr_series is not None else None
    peaks = []
    for i in range(lookback, len(bars) - confirm_bars):
        peak_high = high[i]
        prev_max = np.max(high[i - lookback : i])
        if peak_high <= prev_max:
            continue
        peak_close = close[i]
        confirmed = True
        for j in range(1, confirm_bars + 1):
            if close[i + j] >= peak_close:
                confirmed = False
                break
        if not confirmed:
            continue
        # Measure the drop over the forward window (up to `lookback` bars),
        # stopping early if price recloses above the peak high — the 3-bar
        # confirmation only establishes formation, the full drop takes longer.
        min_close = close[i + 1]
        for j in range(i + 1, min(i + lookback + 1, len(bars))):
            if close[j] >= peak_high:
                break
            if close[j] < min_close:
                min_close = close[j]
        drop_pct = (min_close - peak_high) / peak_high * 100
        effective_threshold = min_drop_pct
        if atr_vals is not None and not np.isnan(atr_vals[i]) and close[i] > 0:
            dynamic = -2.0 * atr_vals[i] / close[i] * 100
            effective_threshold = min(min_drop_pct, dynamic)
        if drop_pct > effective_threshold:
            continue
        peaks.append({
            "idx": i,
            "bar_ts": int(ts[i]),
            "peak_high": float(peak_high),
            "peak_close": float(close[i]),
        })
    return peaks


def detect_troughs(
    bars: pd.DataFrame,
    min_rise_pct: float = 0.0,
    lookback: int = 20,
    confirm_bars: int = 3,
    atr_series: pd.Series | None = None,
) -> list[dict]:
    """Detect troughs: price < min(prev `lookback`) AND next `confirm_bars` close > trough_close.

    Symmetric to detect_peaks: min_rise_pct is an absolute floor, and when
    atr_series is provided the required rise is the LARGER of the floor
    or 2 * ATR / close.
    """
    if bars is None or bars.empty or len(bars) < lookback + confirm_bars + 1:
        return []
    close = bars["close"].astype(float).values
    low = bars["low"].astype(float).values
    ts = bars["bar_ts"].values if "bar_ts" in bars.columns else np.arange(len(bars))
    atr_vals = atr_series.values if atr_series is not None else None
    troughs = []
    for i in range(lookback, len(bars) - confirm_bars):
        trough_low = low[i]
        prev_min = np.min(low[i - lookback : i])
        if trough_low >= prev_min:
            continue
        trough_close = close[i]
        confirmed = True
        for j in range(1, confirm_bars + 1):
            if close[i + j] <= trough_close:
                confirmed = False
                break
        if not confirmed:
            continue
        # Measure the rise over the forward window (up to `lookback` bars),
        # stopping early if price recloses below the trough low.
        max_close = close[i + 1]
        for j in range(i + 1, min(i + lookback + 1, len(bars))):
            if close[j] <= trough_low:
                break
            if close[j] > max_close:
                max_close = close[j]
        rise_pct = (max_close - trough_low) / trough_low * 100
        effective_threshold = min_rise_pct
        if atr_vals is not None and not np.isnan(atr_vals[i]) and close[i] > 0:
            dynamic = 2.0 * atr_vals[i] / close[i] * 100
            effective_threshold = max(min_rise_pct, dynamic)
        if rise_pct < effective_threshold:
            continue
        troughs.append({
            "idx": i,
            "bar_ts": int(ts[i]),
            "trough_low": float(trough_low),
            "trough_close": float(close[i]),
        })
    return troughs


def filter_alternating_inflections(
    peaks: list[dict],
    troughs: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Filter peaks and troughs so that they strictly alternate.

    If there are consecutive peaks without a trough in between, keep the one with the higher peak_high.
    If there are consecutive troughs without a peak in between, keep the one with the lower trough_low.
    """
    if not peaks and not troughs:
        return [], []

    # Combine and sort by bar index
    items = []
    for p in peaks:
        items.append({"type": "peak", "idx": p["idx"], "data": p})
    for t in troughs:
        items.append({"type": "trough", "idx": t["idx"], "data": t})
    items.sort(key=lambda x: x["idx"])

    changed = True
    while changed:
        changed = False
        filtered = []
        i = 0
        while i < len(items):
            current = items[i]
            if i + 1 < len(items):
                next_item = items[i + 1]
                if current["type"] == next_item["type"]:
                    # Consecutive of same type!
                    if current["type"] == "peak":
                        # Keep the one with the higher peak_high
                        if current["data"]["peak_high"] >= next_item["data"]["peak_high"]:
                            filtered.append(current)
                        else:
                            filtered.append(next_item)
                    else:
                        # Keep the one with the lower trough_low
                        if current["data"]["trough_low"] <= next_item["data"]["trough_low"]:
                            filtered.append(current)
                        else:
                            filtered.append(next_item)
                    # Skip both of them in next iteration (we've handled both)
                    i += 2
                    changed = True
                    # Append the rest and break to repeat search
                    filtered.extend(items[i:])
                    break
                else:
                    filtered.append(current)
                    i += 1
            else:
                filtered.append(current)
                i += 1
        items = filtered

    clean_peaks = [item["data"] for item in items if item["type"] == "peak"]
    clean_troughs = [item["data"] for item in items if item["type"] == "trough"]
    return clean_peaks, clean_troughs


def merge_inflections(
    peaks: list[dict],
    troughs: list[dict],
    bars: pd.DataFrame,
) -> list[dict]:
    """Merge peaks and troughs into a single time-ordered inflection list.

    Each inflection is tagged as 'peak' or 'trough' with its bar index.
    Returns list sorted by bar index.
    """
    inflections = []
    for p in peaks:
        inflections.append({"type": "peak", "idx": p["idx"], "bar_ts": p["bar_ts"]})
    for t in troughs:
        inflections.append({"type": "trough", "idx": t["idx"], "bar_ts": t["bar_ts"]})
    inflections.sort(key=lambda x: x["idx"])
    return inflections

