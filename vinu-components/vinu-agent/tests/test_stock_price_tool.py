"""item #11 finding #2: stock_price_tool.py's as-of date-clamping logic
prevents look-ahead bias in backtests but had zero test coverage -- "a
regression there would silently leak post-decision-date data into a
backtest and nothing would catch it." These tests exercise exactly that
clamp path against a real (mocked-HTTP) execute() call, not the helper
functions in isolation."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from vinu_agent.tools.stock_price_tool import StockPriceTool


def _tool(as_of: str | None = None) -> StockPriceTool:
    tool = StockPriceTool()
    tool._services_config = {"vinu_stock_price": "http://stock-api:8081"}
    tool._as_of = as_of
    return tool


def _mock_response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = payload
    return resp


class TestAsOfClamping:
    def test_end_date_beyond_as_of_is_clamped_to_as_of(self) -> None:
        with patch("httpx.get", return_value=_mock_response({})) as mock_get:
            result = json.loads(_tool(as_of="2025-06-01T00:00:00Z").execute(
                symbol="AAPL", start_date="2025-05-01", end_date="2025-12-31",
            ))
        params = mock_get.call_args.kwargs["params"]
        assert params["to"] == 1748736000  # 2025-06-01T00:00:00Z
        assert result["clamped_end_to_as_of"] is True

    def test_end_date_within_as_of_is_not_clamped(self) -> None:
        with patch("httpx.get", return_value=_mock_response({})) as mock_get:
            result = json.loads(_tool(as_of="2025-06-01T00:00:00Z").execute(
                symbol="AAPL", start_date="2025-05-01", end_date="2025-05-15",
            ))
        params = mock_get.call_args.kwargs["params"]
        assert params["to"] == 1747267200  # 2025-05-15T00:00:00Z
        assert "clamped_end_to_as_of" not in result

    def test_no_end_date_defaults_to_as_of_not_wall_clock_now(self) -> None:
        """A caller that omits end_date must still never see data past the
        replay decision point -- defaulting to real time.time() here would
        be an even more direct look-ahead leak than an unclamped explicit
        end_date."""
        with patch("httpx.get", return_value=_mock_response({})) as mock_get:
            _tool(as_of="2025-06-01T00:00:00Z").execute(symbol="AAPL", start_date="2025-05-01")
        params = mock_get.call_args.kwargs["params"]
        assert params["to"] == 1748736000  # 2025-06-01T00:00:00Z

    def test_no_as_of_set_uses_wall_clock_and_never_clamps(self) -> None:
        """Live (non-replay) use: _as_of is None, so with no explicit
        end_date "now" is the only available ceiling and no
        clamped_end_to_as_of flag is set."""
        with patch("httpx.get", return_value=_mock_response({})) as mock_get, \
                patch("time.time", return_value=1748736000):
            result = json.loads(_tool(as_of=None).execute(symbol="AAPL"))
        params = mock_get.call_args.kwargs["params"]
        assert params["to"] == 1748736000
        assert "clamped_end_to_as_of" not in result

    def test_no_as_of_set_with_a_future_explicit_end_date_is_not_clamped_either(self) -> None:
        """Without _as_of there is nothing to clamp against at all -- an
        explicit end_date, even a far-future one, passes straight through.
        This is a live-mode caller's own responsibility, not this tool's;
        the clamp only exists once a replay _as_of is actually set."""
        with patch("httpx.get", return_value=_mock_response({})) as mock_get:
            result = json.loads(_tool(as_of=None).execute(
                symbol="AAPL", start_date="2025-05-01", end_date="2025-12-31",
            ))
        params = mock_get.call_args.kwargs["params"]
        assert params["to"] == 1767139200  # 2025-12-31T00:00:00Z, unclamped
        assert "clamped_end_to_as_of" not in result

    def test_start_after_end_is_corrected_to_a_30_day_window_before_end(self) -> None:
        with patch("httpx.get", return_value=_mock_response({})) as mock_get:
            result = json.loads(_tool(as_of="2025-06-01T00:00:00Z").execute(
                symbol="AAPL", start_date="2025-06-15", end_date="2025-05-01",
            ))
        params = mock_get.call_args.kwargs["params"]
        assert params["to"] == params["from"] + 30 * 86400
        assert result["clamped_end_to_as_of"] is True

    def test_default_start_date_is_30_days_before_the_effective_end(self) -> None:
        with patch("httpx.get", return_value=_mock_response({})) as mock_get:
            _tool(as_of="2025-06-01T00:00:00Z").execute(symbol="AAPL", end_date="2025-06-01")
        params = mock_get.call_args.kwargs["params"]
        assert params["from"] == params["to"] - 30 * 86400

    def test_symbol_uppercased_in_url(self) -> None:
        with patch("httpx.get", return_value=_mock_response({})) as mock_get:
            _tool().execute(symbol="aapl", start_date="2025-05-01", end_date="2025-05-15")
        args, _ = mock_get.call_args
        assert args[0].endswith("/stock/candles/AAPL")
