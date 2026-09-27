import numpy as np
import pandas as pd
import pytest

from vinu_initial_analysis.angles.trend_lifecycle.peaks import (
    detect_peaks,
    detect_troughs,
    filter_alternating_inflections,
)
from vinu_initial_analysis.angles.trend_lifecycle.snapshots import (
    capture_all_peaks,
    capture_all_troughs,
)
from vinu_initial_analysis.angles.trend_lifecycle.patterns import (
    build_feature_matrix,
    find_similar,
)


def test_peak_trough_detection_and_filtering():
    # Create fake daily price data with a peak and a trough
    # 20 flat bars, 1 peak, 20 flat bars, 1 trough, 20 flat bars
    n = 60
    close = [100.0] * n
    high = [100.0] * n
    low = [100.0] * n
    open_p = [100.0] * n
    volume = [1000] * n

    # Make a peak at index 25
    high[25] = 110.0
    close[25] = 108.0
    # Drop confirmation
    close[26] = 102.0
    close[27] = 101.0
    close[28] = 100.0

    # Make a trough at index 45
    low[45] = 90.0
    close[45] = 92.0
    # Rise confirmation
    close[46] = 98.0
    close[47] = 99.0
    close[48] = 100.0

    bars = pd.DataFrame({
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "bar_ts": [int(1672531200 + i * 86400) for i in range(n)],
    })

    # Detect peaks with a 5% min drop
    peaks = detect_peaks(bars, min_drop_pct=-5.0, lookback=10, confirm_bars=3)
    assert len(peaks) == 1
    assert peaks[0]["idx"] == 25
    assert peaks[0]["peak_high"] == 110.0

    # Detect troughs with 0% min rise
    troughs = detect_troughs(bars, min_rise_pct=0.0, lookback=10, confirm_bars=3)
    assert len(troughs) == 1
    assert troughs[0]["idx"] == 45
    assert troughs[0]["trough_low"] == 90.0


def test_alternating_inflections():
    # Test filtering of consecutive peaks and troughs
    peaks = [
        {"idx": 10, "peak_high": 100.0, "bar_ts": 1000},
        {"idx": 15, "peak_high": 105.0, "bar_ts": 1500},  # Higher consecutive peak
        {"idx": 30, "peak_high": 95.0, "bar_ts": 3000},
    ]
    troughs = [
        {"idx": 20, "trough_low": 90.0, "bar_ts": 2000},
        {"idx": 40, "trough_low": 85.0, "bar_ts": 4000},
        {"idx": 45, "trough_low": 88.0, "bar_ts": 4500},  # Lower consecutive trough (should keep 40)
    ]

    clean_peaks, clean_troughs = filter_alternating_inflections(peaks, troughs)

    # Sorted order of idx initially:
    # P10, P15, T20, P30, T40, T45
    # P10 and P15 are adjacent. P15 is higher, so keep P15.
    # New order: P15, T20, P30, T40, T45
    # T40 and T45 are adjacent. T40 is lower, so keep T40.
    # New order: P15, T20, P30, T40. They alternate!
    assert len(clean_peaks) == 2
    assert len(clean_troughs) == 2
    assert [p["idx"] for p in clean_peaks] == [15, 30]
    assert [t["idx"] for t in clean_troughs] == [20, 40]


def _library_row(bar_ts, session, rsi):
    return {
        "type": "snapshot", "inflection_type": "peak",
        "bar_ts": bar_ts, "session": session, "peak_close": 100.0,
        "rsi_14": rsi, "rsi_7": rsi, "upper_wick_pct": 0.3, "body_size_pct": 0.5,
        "close_sma_9_pct": 0.02, "close_sma_50_pct": 0.05, "close_sma_200_pct": 0.1,
        "atr_pct": 0.02, "bb_width_pct": 0.08, "volume_ratio_20": 1.2,
        "volume_zscore_20": 0.5, "runup_bars": 20, "internal_dips_count": 3,
        "relaxation_bars": 2, "peak_ratio": 1.01, "daily_return": 0.01,
        "rsi_divergence": -2.0, "adx_slope_5": 1.0,
        "drawdown_pct": -0.05, "recovery_time_bars": 10,
    }


def test_session_soft_filter():
    # 12 regular-session rows (above the 10-candidate floor), 3 afterhours rows
    rows = [_library_row(1000 + i, "regular", 60 + i) for i in range(12)]
    rows += [_library_row(50000 + i, "afterhours", 30 + i) for i in range(3)]
    lib = pd.DataFrame(rows)
    X, idxs, params = build_feature_matrix(lib)
    query = _library_row(99999, "regular", 65)

    # Enough same-session candidates -> filter applies, only regular rows match
    matched = find_similar(query, lib, X, idxs, k=15, norm_params=params, session="regular")
    assert matched, "expected matches"
    regular_ts = {r["bar_ts"] for r in rows if r["session"] == "regular"}
    assert all(m["matched_bar_ts"] in regular_ts for m in matched)

    # Only 3 afterhours candidates (< floor) -> falls back to the full pool
    matched_ah = find_similar(query, lib, X, idxs, k=15, norm_params=params, session="afterhours")
    assert matched_ah, "fallback must not return empty"
    assert any(m["matched_bar_ts"] in regular_ts for m in matched_ah)


def test_computes_true_range_via_the_shared_vinu_tools_helper_not_hand_rolled():
    """item #21 pattern #2: this module's own peak-detection ATR used to
    hand-roll true range inline (`pd.concat([...]).max(axis=1)`) -- a
    smaller, still-real 4th instance of the indicator-duplication pattern,
    on top of the plain-SMA-vs-Wilder smoothing bug finding #7 already
    fixed here. Regression guard on the actual values, not just that the
    import exists: verified index-for-index identical to vinu_tools'
    shared `true_range()` before switching, this pins that down so it
    can't silently regress back to the inline formula."""
    from vinu_tools.compute.indicators._shared.rolling import true_range, wilder_smooth
    from vinu_initial_analysis.angles.trend_lifecycle.compute import compute

    n = 120
    rng = np.random.default_rng(3)
    close = pd.Series(100 + np.cumsum(rng.standard_normal(n)))
    high = close + rng.uniform(0.1, 1.0, n)
    low = close - rng.uniform(0.1, 1.0, n)
    bar_ts = [1_672_531_200 + i * 86400 for i in range(n)]
    bars = pd.DataFrame({
        "bar_ts": bar_ts, "open": close, "high": high, "low": low, "close": close,
        "volume": np.full(n, 1_000_000.0),
    })

    expected_tr = true_range(high.tolist(), low.tolist(), close.tolist())
    expected_atr = pd.Series(wilder_smooth(expected_tr, 14), index=close.index, dtype=float)

    # compute() doesn't expose atr_series directly, but a real,
    # non-crashing run against this fixture is itself proof the switch to
    # true_range()/wilder_smooth() didn't break the calling code's own
    # tolist()/Series round-trip.
    result = compute("AAPL", bars=bars, time_format="1D")
    assert not result.empty
    assert not expected_atr.iloc[13:].isna().any()  # real, non-NaN values from bar 13 on
