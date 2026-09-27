from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.search_trends.backtest import run_search_trends_backtest

_START_TS = 1_672_531_200  # 2023-01-01T00:00:00Z


def _fake_trend_req(df: pd.DataFrame) -> MagicMock:
    instance = MagicMock()
    instance.interest_over_time.return_value = df
    return MagicMock(return_value=instance)


def _weekly_trends_df(values: list[int], symbol: str = "AAPL", start: str = "2023-01-01") -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(values), freq="7D")
    return pd.DataFrame({symbol: values, "isPartial": [False] * len(values)}, index=idx)


def _daily_bars(n_days: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    price = 100.0
    rows = []
    for i in range(n_days):
        price = max(price + rng.normal(0, 1.0), 1.0)
        rows.append({"bar_ts": _START_TS + i * 86400, "close": price})
    return pd.DataFrame(rows)


class TestRunSearchTrendsBacktest:
    def test_empty_bars_returns_empty_frame(self) -> None:
        values = [10] * 20 + [90]  # a spike, but no price bars to validate against
        with patch("pytrends.request.TrendReq", _fake_trend_req(_weekly_trends_df(values))):
            result = run_search_trends_backtest("AAPL", pd.DataFrame())
        assert result.empty

    def test_no_trends_data_returns_empty_frame(self) -> None:
        with patch("pytrends.request.TrendReq", _fake_trend_req(pd.DataFrame())):
            result = run_search_trends_backtest("AAPL", _daily_bars(300, seed=1))
        assert result.empty

    def test_real_forward_return_join_produces_quarterly_rows(self) -> None:
        # 60 weeks of trend samples (~420 days) against 450 days of price
        # bars -- comfortably enough real data for at least one quarter's
        # forward_20d window to have 5+ valid samples.
        values = list(np.random.default_rng(3).integers(1, 100, size=60))
        bars = _daily_bars(450, seed=2)
        with patch("pytrends.request.TrendReq", _fake_trend_req(_weekly_trends_df(values))):
            result = run_search_trends_backtest("AAPL", bars)
        assert not result.empty
        assert "quarter_key" in result.columns
        assert "n_rows" in result.columns

    def test_forward_return_columns_appear_when_enough_samples(self) -> None:
        values = list(np.random.default_rng(4).integers(1, 100, size=60))
        bars = _daily_bars(450, seed=5)
        with patch("pytrends.request.TrendReq", _fake_trend_req(_weekly_trends_df(values))):
            result = run_search_trends_backtest("AAPL", bars)
        assert not result.empty
        # At least one quarter should have cleared the 5-sample floor for
        # at least the shortest horizon.
        assert any(col.startswith("forward_5d_corr") for col in result.columns)
