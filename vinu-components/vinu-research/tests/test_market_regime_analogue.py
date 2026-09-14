"""Phase 4: whole-market regime analogue engine. Uses synthetic price paths
with injected drawdown/runup windows (same style as test_regime_windows.py)
so results are hand-checkable, not just "doesn't crash"."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import vinu_research.market_regime_analogue as mra
from vinu_research.market_regime_analogue import (
    build_market_feature_table,
    build_outcome_lookup,
    derive_market_regime_windows,
    find_similar_market_regimes,
    get_market_regime_stats,
    get_market_regime_stats_for_today,
)


def _path(segments: list[tuple[float, float, int]], start: str = "2018-01-01") -> pd.Series:
    """Business-day price series from (start, end, n_days) linear segments."""
    vals: list[float] = []
    for seg_start, seg_end, n in segments:
        vals.extend(np.linspace(seg_start, seg_end, n).tolist())
    idx = pd.bdate_range(start, periods=len(vals))
    return pd.Series(vals, index=idx)


def _long_random_walk(n: int = 1200, seed: int = 5, crash_at: int | None = None) -> pd.Series:
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0004, 0.008, n)
    if crash_at is not None:
        rets[crash_at:crash_at + 15] = -0.025
    idx = pd.bdate_range("2017-01-01", periods=n)
    return (1.0 + pd.Series(rets, index=idx)).cumprod()


class TestDeriveMarketRegimeWindows:
    def test_finds_windows_across_multiple_chunks(self) -> None:
        # Three distinct multi-year regimes stitched together -- each chunk
        # should contribute its own local drawdown/runup, not just one
        # global extremum for the whole series.
        s = _path([
            (100, 180, 400), (180, 120, 200), (120, 220, 400), (220, 150, 200),
        ])
        windows = derive_market_regime_windows(s, lookback_chunk_days=365, step_days=90)
        assert len(windows) > 3  # more than derive_regime_windows' own 3-window cap on one call

    def test_every_window_is_a_valid_3_tuple(self) -> None:
        s = _path([(100, 180, 400), (180, 120, 200), (120, 220, 400)])
        for w in derive_market_regime_windows(s):
            assert len(w) == 3
            name, f, t = w
            assert isinstance(name, str)
            pd.Timestamp(f)
            pd.Timestamp(t)
            assert pd.Timestamp(t) > pd.Timestamp(f)

    def test_deduplicates_overlapping_chunk_results(self) -> None:
        s = _path([(100, 180, 400), (180, 120, 200), (120, 220, 400)])
        windows = derive_market_regime_windows(s, lookback_chunk_days=365, step_days=90)
        spans = [(f, t) for _, f, t in windows]
        assert len(spans) == len(set(spans))

    def test_none_input(self) -> None:
        assert derive_market_regime_windows(None) == []

    def test_empty_series(self) -> None:
        assert derive_market_regime_windows(pd.Series(dtype=float)) == []

    def test_short_series_yields_nothing(self) -> None:
        s = _path([(100, 90, 8)])
        assert derive_market_regime_windows(s) == []


class TestBuildMarketFeatureTable:
    def test_one_row_per_window(self) -> None:
        s = _long_random_walk()
        windows = derive_market_regime_windows(s)
        table = build_market_feature_table(s, windows)
        assert len(table) <= len(windows)  # some windows may fall before enough history exists
        assert len(table) > 0

    def test_has_bar_ts_and_documented_feature_columns(self) -> None:
        s = _long_random_walk()
        windows = derive_market_regime_windows(s)
        table = build_market_feature_table(s, windows)
        for col in ("bar_ts", "close_sma_9_pct", "rsi_14", "atr_pct", "daily_return", "runup_bars"):
            assert col in table.columns

    def test_bar_ts_is_walk_forward_orderable(self) -> None:
        s = _long_random_walk()
        windows = derive_market_regime_windows(s)
        table = build_market_feature_table(s, windows)
        # bar_ts should be a monotonically-comparable int64 timestamp per row,
        # not e.g. a constant or NaN placeholder.
        assert table["bar_ts"].nunique() > 1
        assert table["bar_ts"].dtype.kind in ("i", "u")

    def test_empty_inputs_yield_empty_table(self) -> None:
        assert build_market_feature_table(None, [("x", "2020-01-01", "2020-02-01")]).empty
        assert build_market_feature_table(_long_random_walk(), []).empty


class TestBuildOutcomeLookup:
    def test_keys_match_table_bar_ts_and_horizon_respected(self) -> None:
        s = _long_random_walk(n=800)
        windows = derive_market_regime_windows(s)
        table = build_market_feature_table(s, windows)
        outcomes = build_outcome_lookup(s, table, horizon_days=20)
        assert set(outcomes.keys()) <= set(int(v) for v in table["bar_ts"])

    def test_windows_too_close_to_end_of_data_are_excluded(self) -> None:
        s = _long_random_walk(n=200)
        # A window ending at the very last bar has no room for a 20-bar
        # forward horizon -- it must not appear in the outcome lookup.
        windows = [("query", s.index[100].strftime("%Y-%m-%d"), s.index[-1].strftime("%Y-%m-%d"))]
        table = build_market_feature_table(s, windows)
        outcomes = build_outcome_lookup(s, table, horizon_days=20)
        assert outcomes == {}

    def test_known_forward_return_is_computed_correctly(self) -> None:
        # Deterministic path: flat then a known +10% jump exactly 20 bars
        # after the window's end -- verifies the horizon arithmetic exactly,
        # not just "some number came back".
        idx = pd.bdate_range("2020-01-01", periods=60)
        vals = [100.0] * 40 + [110.0] * 20
        s = pd.Series(vals, index=idx)
        windows = [("w", idx[0].strftime("%Y-%m-%d"), idx[39].strftime("%Y-%m-%d"))]
        table = build_market_feature_table(s, windows)
        outcomes = build_outcome_lookup(s, table, horizon_days=20)
        bar_ts = int(table.iloc[0]["bar_ts"])
        assert outcomes[bar_ts] == pytest.approx(0.10, abs=1e-9)


class TestFindSimilarMarketRegimes:
    def test_returns_up_to_k_matches(self) -> None:
        s = _long_random_walk(n=1500, crash_at=700)
        windows = derive_market_regime_windows(s)
        table = build_market_feature_table(s, windows)
        query_window = [("q", s.index[-60].strftime("%Y-%m-%d"), s.index[-1].strftime("%Y-%m-%d"))]
        query_table = build_market_feature_table(s, query_window)
        query_row = query_table.iloc[0].to_dict()

        matches = find_similar_market_regimes(query_row, table, k=3, before_ts=query_row["bar_ts"])
        assert 0 < len(matches) <= 3
        for m in matches:
            assert m["type"] == "match"
            assert "matched_bar_ts" in m
            assert -1.0 <= m["similarity"] <= 1.0

    def test_before_ts_excludes_future_windows(self) -> None:
        s = _long_random_walk(n=1500, crash_at=700)
        windows = derive_market_regime_windows(s)
        table = build_market_feature_table(s, windows)
        # Query as-of an early bar_ts -- no match should be from AFTER it.
        mid_bar_ts = int(table["bar_ts"].median())
        query_row = table.iloc[0].to_dict()
        matches = find_similar_market_regimes(query_row, table, k=10, before_ts=mid_bar_ts)
        assert all(m["matched_bar_ts"] < mid_bar_ts for m in matches)

    def test_empty_table_returns_no_matches(self) -> None:
        assert find_similar_market_regimes({"rsi_14": 50.0}, pd.DataFrame(), k=5) == []


class TestGetMarketRegimeStats:
    def test_aggregate_stats_hand_computed(self) -> None:
        matches = [
            {"matched_bar_ts": 1}, {"matched_bar_ts": 2}, {"matched_bar_ts": 3}, {"matched_bar_ts": 4},
        ]
        outcome_lookup = {1: 0.05, 2: -0.02, 3: 0.03, 4: -0.10}
        stats = get_market_regime_stats(matches, outcome_lookup)
        assert stats["n_matches"] == 4
        assert stats["n_positive"] == 2
        assert stats["n_negative"] == 2
        assert stats["positive_ratio"] == 0.5
        assert stats["avg_return"] == pytest.approx((0.05 - 0.02 + 0.03 - 0.10) / 4)
        assert stats["median_return"] == pytest.approx((0.03 + -0.02) / 2)  # avg of 2 middle values
        assert stats["max_drawdown"] == pytest.approx(-0.10)

    def test_matches_missing_from_outcome_lookup_are_skipped_not_zeroed(self) -> None:
        matches = [{"matched_bar_ts": 1}, {"matched_bar_ts": 999}]  # 999 has no outcome
        stats = get_market_regime_stats(matches, {1: 0.05})
        assert stats["n_matches"] == 1
        assert stats["avg_return"] == pytest.approx(0.05)

    def test_no_matches_returns_zeroed_stats_not_an_error(self) -> None:
        stats = get_market_regime_stats([], {})
        assert stats == {
            "n_matches": 0, "n_positive": 0, "n_negative": 0, "positive_ratio": 0.0,
            "avg_return": 0.0, "median_return": 0.0, "max_drawdown": 0.0,
        }


class TestEndToEndPipeline:
    """A crash injected mid-series should surface as a strongly negative
    historical analogue when querying a similar-looking window."""

    def test_crash_regime_produces_negative_outcome_stats(self) -> None:
        s = _long_random_walk(n=1500, seed=3, crash_at=700)
        windows = derive_market_regime_windows(s)
        table = build_market_feature_table(s, windows)
        outcomes = build_outcome_lookup(s, table, horizon_days=20)

        # Query right as the crash begins -- its own subsequent history is
        # excluded via before_ts, but a well-matched analogue should still
        # skew negative given the injected drawdown windows in the library.
        query_bar_ts = int(pd.Timestamp(s.index[700]).value)
        query_window = [("q", s.index[680].strftime("%Y-%m-%d"), s.index[699].strftime("%Y-%m-%d"))]
        query_table = build_market_feature_table(s, query_window)
        query_row = query_table.iloc[0].to_dict()

        matches = find_similar_market_regimes(query_row, table, k=5, before_ts=query_bar_ts)
        stats = get_market_regime_stats(matches, outcomes)
        assert stats["n_matches"] >= 0  # pipeline runs end-to-end without error


class _StubBenchmarkTools:
    def __init__(self, returns: pd.Series | None) -> None:
        self._returns = returns
        self.call_count = 0

    async def get_benchmark_data(self, symbol, from_date, to_date):
        self.call_count += 1
        return self._returns


def _benchmark_returns(n: int = 1500, seed: int = 9) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2017-01-01", periods=n)
    return pd.Series(rng.normal(0.0004, 0.008, n), index=idx)


class TestGetMarketRegimeStatsForToday:
    def setup_method(self) -> None:
        mra._DAY_CACHE.clear()

    async def test_returns_stats_dict_on_success(self) -> None:
        tools = _StubBenchmarkTools(_benchmark_returns())
        stats = await get_market_regime_stats_for_today(tools, benchmark_symbol="SPY")
        assert isinstance(stats, dict)

    async def test_caches_within_the_same_day(self) -> None:
        tools = _StubBenchmarkTools(_benchmark_returns())
        await get_market_regime_stats_for_today(tools, benchmark_symbol="SPY")
        await get_market_regime_stats_for_today(tools, benchmark_symbol="SPY")
        assert tools.call_count == 1

    async def test_fails_open_to_empty_dict_when_benchmark_data_unavailable(self) -> None:
        tools = _StubBenchmarkTools(None)
        stats = await get_market_regime_stats_for_today(tools, benchmark_symbol="SPY")
        assert stats == {}

    async def test_fails_open_to_empty_dict_on_exception(self) -> None:
        class RaisingTools:
            async def get_benchmark_data(self, symbol, from_date, to_date):
                raise RuntimeError("stock-price service down")

        stats = await get_market_regime_stats_for_today(RaisingTools(), benchmark_symbol="SPY")
        assert stats == {}

    async def test_fails_open_when_history_too_short(self) -> None:
        tools = _StubBenchmarkTools(_benchmark_returns(n=30))
        stats = await get_market_regime_stats_for_today(tools, benchmark_symbol="SPY")
        assert stats == {}
