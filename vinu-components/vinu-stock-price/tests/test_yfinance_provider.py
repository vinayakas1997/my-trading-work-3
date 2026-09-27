"""item #19 finding #4: YFinanceProvider had no retry/backoff at all,
unlike every other provider in this directory -- the same yfinance-
flakiness pattern already fixed for vinu-agent's fundamentals_tool.py
(item #11 finding #3). These exercise the real retry loop, not just the
happy path (this provider had zero test coverage before this fix)."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pandas as pd

from vinu_stock.providers.yfinance import YFinanceProvider


def _fake_yfinance_module(ticker_factory) -> types.ModuleType:
    mod = types.ModuleType("yfinance")
    mod.Ticker = ticker_factory
    return mod


def _history_df() -> pd.DataFrame:
    idx = pd.to_datetime(["2020-01-01", "2020-01-02"], utc=True)
    return pd.DataFrame(
        {"Open": [1.0, 2.0], "High": [1.5, 2.5], "Low": [0.5, 1.5], "Close": [1.2, 2.2], "Volume": [100, 200]},
        index=idx,
    )


def _ticker(history_result=None, history_side_effect=None, info: dict | None = None) -> MagicMock:
    t = MagicMock()
    if history_side_effect is not None:
        t.history.side_effect = history_side_effect
    else:
        t.history.return_value = history_result
    t.info = info or {}
    return t


class TestFetchBarsRetry:
    def test_succeeds_first_attempt_no_retry(self) -> None:
        ticker = _ticker(history_result=_history_df())
        factory = MagicMock(return_value=ticker)
        fake_module = _fake_yfinance_module(factory)
        with patch.dict(sys.modules, {"yfinance": fake_module}), patch("time.sleep") as mock_sleep:
            result = YFinanceProvider().fetch_bars("AAPL", 0, 1_000_000)
        assert result.success is True
        assert len(result.bars) == 2
        mock_sleep.assert_not_called()

    def test_retries_after_a_transient_failure_then_succeeds(self) -> None:
        ticker = _ticker(history_side_effect=[ConnectionError("network blip"), _history_df()])
        # side_effect on the bound `.history` mock, not the Ticker factory --
        # each fetch_bars call constructs a fresh Ticker but reuses it as one
        # object across the retry loop's own attempts.
        factory = MagicMock(return_value=ticker)
        fake_module = _fake_yfinance_module(factory)
        with patch.dict(sys.modules, {"yfinance": fake_module}), patch("time.sleep") as mock_sleep:
            result = YFinanceProvider().fetch_bars("AAPL", 0, 1_000_000)
        assert result.success is True
        assert len(result.bars) == 2
        assert ticker.history.call_count == 2
        mock_sleep.assert_called_once()

    def test_permanent_failure_returns_error_after_exhausting_retries(self) -> None:
        ticker = _ticker(history_side_effect=ConnectionError("still down"))
        factory = MagicMock(return_value=ticker)
        fake_module = _fake_yfinance_module(factory)
        with patch.dict(sys.modules, {"yfinance": fake_module}), patch("time.sleep") as mock_sleep:
            result = YFinanceProvider().fetch_bars("AAPL", 0, 1_000_000)
        assert result.success is False
        assert "still down" in result.error
        assert ticker.history.call_count == 3
        assert mock_sleep.call_count == 2  # slept between attempts 1->2 and 2->3, not after the last

    def test_empty_dataframe_is_not_retried(self) -> None:
        """An empty result is a real, valid answer ("no data for this
        range"), not a transient failure -- retrying it would just waste
        wall-clock for the same empty result."""
        ticker = _ticker(history_result=pd.DataFrame())
        factory = MagicMock(return_value=ticker)
        fake_module = _fake_yfinance_module(factory)
        with patch.dict(sys.modules, {"yfinance": fake_module}), patch("time.sleep") as mock_sleep:
            result = YFinanceProvider().fetch_bars("AAPL", 0, 1_000_000)
        assert result.success is False
        assert result.error == "No data returned"
        assert ticker.history.call_count == 1
        mock_sleep.assert_not_called()


class TestEarliestAvailableRetry:
    def test_succeeds_first_attempt_no_retry(self) -> None:
        ticker = _ticker(info={"firstTradeDateEpochUtc": 12345})
        factory = MagicMock(return_value=ticker)
        fake_module = _fake_yfinance_module(factory)
        with patch.dict(sys.modules, {"yfinance": fake_module}), patch("time.sleep") as mock_sleep:
            result = YFinanceProvider().earliest_available("AAPL")
        assert result.success is True
        assert result.earliest_ts == 12345
        mock_sleep.assert_not_called()

    def test_retries_after_a_transient_failure_then_succeeds(self) -> None:
        # `.info` is a plain attribute access on the mock, not a method --
        # PropertyMock lets a second access return a different value than
        # the first, mirroring `.history()`'s side_effect list above.
        from unittest.mock import PropertyMock
        ticker = MagicMock()
        type(ticker).info = PropertyMock(side_effect=[ConnectionError("network blip"), {"firstTradeDateEpochUtc": 999}])
        factory = MagicMock(return_value=ticker)
        fake_module = _fake_yfinance_module(factory)
        with patch.dict(sys.modules, {"yfinance": fake_module}), patch("time.sleep") as mock_sleep:
            result = YFinanceProvider().earliest_available("AAPL")
        assert result.success is True
        assert result.earliest_ts == 999
        mock_sleep.assert_called_once()

    def test_permanent_failure_returns_error_after_exhausting_retries(self) -> None:
        from unittest.mock import PropertyMock
        ticker = MagicMock()
        type(ticker).info = PropertyMock(side_effect=ConnectionError("still down"))
        factory = MagicMock(return_value=ticker)
        fake_module = _fake_yfinance_module(factory)
        with patch.dict(sys.modules, {"yfinance": fake_module}), patch("time.sleep") as mock_sleep:
            result = YFinanceProvider().earliest_available("AAPL")
        assert result.success is False
        assert "still down" in result.error
        assert mock_sleep.call_count == 2

    def test_no_firstTradeDateEpochUtc_is_not_retried(self) -> None:
        ticker = _ticker(info={"symbol": "AAPL"})
        factory = MagicMock(return_value=ticker)
        fake_module = _fake_yfinance_module(factory)
        with patch.dict(sys.modules, {"yfinance": fake_module}), patch("time.sleep") as mock_sleep:
            result = YFinanceProvider().earliest_available("AAPL")
        assert result.success is False
        assert result.error == "No firstTradeDateEpochUtc in info"
        mock_sleep.assert_not_called()
