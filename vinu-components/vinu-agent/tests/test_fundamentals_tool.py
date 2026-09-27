"""item #11 finding #3 / item #19 finding #4: fundamentals_tool.py had no
retry/backoff around yfinance -- a single broad except turned any
transient network blip into a permanent error for that turn. These tests
exercise the real retry loop, not just the happy path (previously zero
coverage on this file at all, item #11 finding #2)."""

from __future__ import annotations

import json
import sys
import types
from unittest.mock import MagicMock, patch

from vinu_agent.tools.fundamentals_tool import FundamentalsTool


def _fake_yfinance_module(ticker_factory) -> types.ModuleType:
    mod = types.ModuleType("yfinance")
    mod.Ticker = ticker_factory
    return mod


def _ticker_with_info(info: dict) -> MagicMock:
    t = MagicMock()
    t.info = info
    return t


class TestFundamentalsToolRetry:
    def test_succeeds_first_attempt_no_retry(self) -> None:
        ticker = _ticker_with_info({"symbol": "AAPL", "longName": "Apple Inc."})
        fake_module = _fake_yfinance_module(MagicMock(return_value=ticker))
        with patch.dict(sys.modules, {"yfinance": fake_module}), patch("time.sleep") as mock_sleep:
            result = json.loads(FundamentalsTool().execute(symbol="aapl"))
        assert result["symbol"] == "AAPL"
        fake_module.Ticker.assert_called_once_with("AAPL")
        mock_sleep.assert_not_called()

    def test_retries_after_a_transient_failure_then_succeeds(self) -> None:
        ticker = _ticker_with_info({"symbol": "AAPL", "longName": "Apple Inc."})
        factory = MagicMock(side_effect=[ConnectionError("network blip"), ticker])
        fake_module = _fake_yfinance_module(factory)
        with patch.dict(sys.modules, {"yfinance": fake_module}), patch("time.sleep") as mock_sleep:
            result = json.loads(FundamentalsTool().execute(symbol="AAPL"))
        assert result["symbol"] == "AAPL"
        assert factory.call_count == 2
        mock_sleep.assert_called_once()

    def test_permanent_failure_returns_error_after_exhausting_retries(self) -> None:
        factory = MagicMock(side_effect=ConnectionError("still down"))
        fake_module = _fake_yfinance_module(factory)
        with patch.dict(sys.modules, {"yfinance": fake_module}), patch("time.sleep") as mock_sleep:
            result = json.loads(FundamentalsTool().execute(symbol="AAPL"))
        assert result["status"] == "error"
        assert "still down" in result["error"]
        assert factory.call_count == 3
        assert mock_sleep.call_count == 2  # slept between attempts 1->2 and 2->3, not after the last

    def test_unknown_symbol_returns_error_without_retrying(self) -> None:
        """info coming back without a "symbol" key isn't a transient
        failure -- it's a real "not found" result, so retrying it would
        just waste 3x the wall-clock for the same answer."""
        ticker = _ticker_with_info({})
        fake_module = _fake_yfinance_module(MagicMock(return_value=ticker))
        with patch.dict(sys.modules, {"yfinance": fake_module}), patch("time.sleep") as mock_sleep:
            result = json.loads(FundamentalsTool().execute(symbol="ZZZZ"))
        assert result["status"] == "error"
        assert "not found" in result["error"]
        mock_sleep.assert_not_called()


class TestFundamentalsToolMetrics:
    def test_summary_metric_is_the_default(self) -> None:
        ticker = _ticker_with_info({
            "symbol": "AAPL", "longName": "Apple Inc.", "trailingPE": 28.5, "marketCap": 3_000_000_000_000,
        })
        fake_module = _fake_yfinance_module(MagicMock(return_value=ticker))
        with patch.dict(sys.modules, {"yfinance": fake_module}):
            result = json.loads(FundamentalsTool().execute(symbol="AAPL"))
        assert result["summary"]["pe_ratio"] == 28.5
        assert "ratios" not in result

    def test_all_metric_includes_statements_when_available(self) -> None:
        import pandas as pd

        ticker = _ticker_with_info({"symbol": "AAPL", "longName": "Apple Inc."})
        ticker.financials = pd.DataFrame({"2024": [100.0]})
        ticker.balance_sheet = pd.DataFrame({"2024": [200.0]})
        ticker.cashflow = pd.DataFrame({"2024": [50.0]})
        fake_module = _fake_yfinance_module(MagicMock(return_value=ticker))
        with patch.dict(sys.modules, {"yfinance": fake_module}):
            result = json.loads(FundamentalsTool().execute(symbol="AAPL", metric="all"))
        assert "income_statement" in result
        assert "balance_sheet" in result
        assert "cash_flow" in result
