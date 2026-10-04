"""features-logic-checking: how the system finds "this looks like earlier situations" (market memory).

Worked example. A library of six earlier market peaks described by three features (RSI, ATR%, run-up bars) and what
happened after each (drawdown and bars to recover). Three are "hot" peaks (high RSI, low ATR, long run-up), three are
"calm" peaks (the opposite). Today's peak looks hot. By hand, the nearest analogues must be the hot peaks, and only
those that happened BEFORE today (walk-forward: no look-ahead).
"""

from __future__ import annotations

import pandas as pd
import pytest

from vinu_initial_analysis.angles.trend_lifecycle.patterns import (
    build_feature_matrix,
    find_similar,
    load_pattern_library,
)

# bar_ts, rsi_14, atr_pct, runup_bars, drawdown_pct, recovery_time_bars, kind
ROWS = [
    (1000, 82.0, 0.010, 30, -6.0, 12, "hot"),
    (2000, 85.0, 0.012, 34, -7.5, 15, "hot"),
    (3000, 80.0, 0.011, 28, -5.0, 10, "hot"),
    (4000, 45.0, 0.040, 5, -1.0, 3, "calm"),
    (5000, 40.0, 0.045, 4, -0.5, 2, "calm"),
    (6000, 42.0, 0.050, 6, -0.8, 3, "calm"),
]
TODAY = {"rsi_14": 83.0, "atr_pct": 0.011, "runup_bars": 31}


def _library():
    df = pd.DataFrame([
        {"type": "snapshot", "inflection_type": "peak", "bar_ts": ts, "rsi_14": rsi, "atr_pct": atr,
         "runup_bars": run, "drawdown_pct": dd, "recovery_time_bars": rec, "time_format": "1D"}
        for ts, rsi, atr, run, dd, rec, _ in ROWS
    ])
    lib = load_pattern_library(df, time_format="1D")
    X, idx, params = build_feature_matrix(lib)
    return lib, X, idx, params


def test_a_hot_peak_matches_the_hot_peaks_not_the_calm_ones():
    lib, X, idx, params = _library()
    got = find_similar(TODAY, lib, X, idx, k=3, norm_params=params)
    assert sorted(m["matched_bar_ts"] for m in got) == [1000, 2000, 3000]
    assert all(m["similarity"] > 0.9 for m in got)
    # what happened after those analogues is carried along: the evidence an analyst would quote
    by_ts = {m["matched_bar_ts"]: m for m in got}
    assert by_ts[2000]["matched_drawdown_pct"] == -7.5 and by_ts[2000]["matched_recovery_bars"] == 15


def test_the_results_are_ordered_by_similarity_best_first():
    lib, X, idx, params = _library()
    got = find_similar(TODAY, lib, X, idx, k=6, norm_params=params)
    sims = [m["similarity"] for m in got]
    assert sims == sorted(sims, reverse=True)
    assert {m["matched_bar_ts"] for m in got[:3]} == {1000, 2000, 3000}   # the hot three before the calm three


def test_only_peaks_before_the_query_may_match_so_there_is_no_look_ahead():
    lib, X, idx, params = _library()
    # today is at bar_ts 2500: only the peaks at 1000 and 2000 existed; 3000..6000 are the future and are excluded,
    # even though 3000 is the best hot match and k asks for three.
    got = find_similar(TODAY, lib, X, idx, k=3, norm_params=params, before_ts=2500)
    assert {m["matched_bar_ts"] for m in got} == {1000, 2000}


def test_nothing_earlier_means_no_analogue_not_a_guess():
    lib, X, idx, params = _library()
    assert find_similar(TODAY, lib, X, idx, k=3, norm_params=params, before_ts=1000) == []


def test_an_unusable_query_returns_nothing():
    lib, X, idx, params = _library()
    assert find_similar({"rsi_14": float("nan")}, lib, X, idx, k=3, norm_params=params) == []
    assert find_similar({"unrelated": 1.0}, lib, X, idx, k=3, norm_params=params) == []


def test_an_empty_library_gives_no_analogues():
    assert load_pattern_library(pd.DataFrame()).empty
    X, idx, params = build_feature_matrix(pd.DataFrame({"rsi_14": [float("nan")]}))
    assert find_similar(TODAY, pd.DataFrame(), X, idx, k=3, norm_params=params) == []
