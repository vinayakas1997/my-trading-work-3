"""search_trends: the high-expectations cross-check's "alternative data
... search trends" ask, built for real. pytrends has no formal API and
rate-limits aggressively, so these mock `pytrends.request.TrendReq`
directly rather than hitting the real network -- the real end-to-end
call was verified manually against the live Google Trends endpoint
while building this, not assumed to work."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.search_trends.compute import compute


def _fake_trend_req(df: pd.DataFrame | None = None, raises: Exception | None = None) -> MagicMock:
    instance = MagicMock()
    if raises is not None:
        instance.build_payload.side_effect = raises
    else:
        instance.interest_over_time.return_value = df if df is not None else pd.DataFrame()
    trend_req_cls = MagicMock(return_value=instance)
    return trend_req_cls


def _weekly_df(values: list[int], symbol: str = "AAPL", start: str = "2025-01-05") -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(values), freq="7D")
    return pd.DataFrame({symbol: values, "isPartial": [False] * (len(values) - 1) + [True]}, index=idx)


class TestComputeSuccessPath:
    def test_returns_one_row_per_week_with_search_interest(self) -> None:
        df = _weekly_df([10, 20, 30, 40, 50])
        with patch("pytrends.request.TrendReq", _fake_trend_req(df)):
            result = compute("AAPL")
        assert len(result) == 5
        assert list(result["search_interest"]) == [10, 20, 30, 40, 50]
        assert result["angle"].iloc[0] == "search_trends"

    def test_last_row_is_flagged_partial(self) -> None:
        df = _weekly_df([10, 20, 30])
        with patch("pytrends.request.TrendReq", _fake_trend_req(df)):
            result = compute("AAPL")
        assert result["is_partial"].tolist() == [False, False, True]

    def test_zscore_is_nan_before_min_periods_then_populated(self) -> None:
        df = _weekly_df([10, 10, 10, 10, 90])  # a real spike on week 5
        with patch("pytrends.request.TrendReq", _fake_trend_req(df)):
            result = compute("AAPL")
        # min_periods=4 -> first 3 rows can't have a baseline yet
        assert result["search_interest_zscore"].iloc[:3].isna().all()
        assert pd.notna(result["search_interest_zscore"].iloc[4])
        assert result["search_interest_zscore"].iloc[4] > 0  # a real spike scores positive

    def test_bar_ts_is_a_real_unix_timestamp(self) -> None:
        df = _weekly_df([10, 20])
        with patch("pytrends.request.TrendReq", _fake_trend_req(df)):
            result = compute("AAPL")
        assert result["bar_ts"].iloc[0] == int(pd.Timestamp("2025-01-05", tz="UTC").timestamp())


class TestComputeFailureModes:
    def test_pytrends_not_installed_returns_no_data(self) -> None:
        with patch.dict("sys.modules", {"pytrends": None, "pytrends.request": None}):
            result = compute("AAPL")
        assert len(result) == 1
        assert result["status"].iloc[0] == "no_data"

    def test_build_payload_raising_returns_no_data(self) -> None:
        with patch("pytrends.request.TrendReq", _fake_trend_req(raises=RuntimeError("rate limited"))):
            result = compute("AAPL")
        assert result["status"].iloc[0] == "no_data"

    def test_empty_dataframe_from_pytrends_returns_no_data(self) -> None:
        with patch("pytrends.request.TrendReq", _fake_trend_req(pd.DataFrame())):
            result = compute("AAPL")
        assert result["status"].iloc[0] == "no_data"

    def test_keyword_column_missing_returns_no_data(self) -> None:
        # A real pytrends quirk: the requested keyword can come back
        # under different casing/absent entirely on certain queries.
        df = pd.DataFrame({"different_keyword": [1, 2]}, index=pd.date_range("2025-01-05", periods=2, freq="7D"))
        with patch("pytrends.request.TrendReq", _fake_trend_req(df)):
            result = compute("AAPL")
        assert result["status"].iloc[0] == "no_data"

    def test_all_nan_values_returns_no_data(self) -> None:
        df = pd.DataFrame(
            {"AAPL": [np.nan, np.nan], "isPartial": [False, True]},
            index=pd.date_range("2025-01-05", periods=2, freq="7D"),
        )
        with patch("pytrends.request.TrendReq", _fake_trend_req(df)):
            result = compute("AAPL")
        assert result["status"].iloc[0] == "no_data"
