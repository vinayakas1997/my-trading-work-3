"""item #11 finding #2: news_tool.py's as-of date-clamping logic is the
other half of "would silently leak post-decision-date data into a
backtest and nothing would catch it" -- previously zero test coverage."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from vinu_agent.tools.news_tool import NewsTool


def _tool(as_of: str | None = None) -> NewsTool:
    tool = NewsTool()
    tool._services_config = {"vinu_news": "http://news-api:8080"}
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
                symbol="AAPL", end_date="2025-12-31",
            ))
        params = mock_get.call_args.kwargs["params"]
        assert params["to"] == 1748736000  # 2025-06-01T00:00:00Z
        assert result["clamped_end_to_as_of"] is True

    def test_end_date_within_as_of_is_not_clamped(self) -> None:
        with patch("httpx.get", return_value=_mock_response({})) as mock_get:
            result = json.loads(_tool(as_of="2025-06-01T00:00:00Z").execute(
                symbol="AAPL", end_date="2025-05-15",
            ))
        params = mock_get.call_args.kwargs["params"]
        assert params["to"] == 1747267200  # 2025-05-15T00:00:00Z
        assert "clamped_end_to_as_of" not in result

    def test_no_end_date_defaults_to_as_of_not_wall_clock_now(self) -> None:
        with patch("httpx.get", return_value=_mock_response({})) as mock_get:
            _tool(as_of="2025-06-01T00:00:00Z").execute(symbol="AAPL")
        params = mock_get.call_args.kwargs["params"]
        assert params["to"] == 1748736000  # 2025-06-01T00:00:00Z

    def test_no_as_of_set_uses_wall_clock_and_never_clamps(self) -> None:
        with patch("httpx.get", return_value=_mock_response({})) as mock_get, \
                patch("time.time", return_value=1748736000):
            result = json.loads(_tool(as_of=None).execute(symbol="AAPL"))
        params = mock_get.call_args.kwargs["params"]
        assert params["to"] == 1748736000
        assert "clamped_end_to_as_of" not in result

    def test_from_epoch_defaults_to_30_days_before_to_only_when_as_of_set(self) -> None:
        """Without _as_of, from_epoch has no default at all (stays absent
        from params) -- only a replay clamp implies a bounded lookback
        window; live queries pass their own start_date or get everything
        the service is willing to serve."""
        with patch("httpx.get", return_value=_mock_response({})) as mock_get:
            _tool(as_of="2025-06-01T00:00:00Z").execute(symbol="AAPL")
        params = mock_get.call_args.kwargs["params"]
        assert params["from"] == params["to"] - 30 * 86400

        with patch("httpx.get", return_value=_mock_response({})) as mock_get2, \
                patch("time.time", return_value=1748736000):
            _tool(as_of=None).execute(symbol="AAPL")
        assert "from" not in mock_get2.call_args.kwargs["params"]

    def test_symbol_uppercased_and_default_limit_applied(self) -> None:
        with patch("httpx.get", return_value=_mock_response({})) as mock_get:
            _tool().execute(symbol="aapl")
        args, kwargs = mock_get.call_args
        assert args[0].endswith("/news/ticker/AAPL")
        assert kwargs["params"]["limit"] == 20


class TestPerInstanceCaching:
    """item #11 finding #4: repeated identical fetches within one agent
    loop must not re-hit the network every time."""

    def test_identical_call_twice_only_fetches_once(self) -> None:
        tool = _tool(as_of="2025-06-01T00:00:00Z")
        with patch("httpx.get", return_value=_mock_response({"articles": []})) as mock_get:
            first = tool.execute(symbol="AAPL", start_date="2025-05-01", end_date="2025-05-15")
            second = tool.execute(symbol="AAPL", start_date="2025-05-01", end_date="2025-05-15")
        assert mock_get.call_count == 1
        assert first == second

    def test_different_limit_is_not_cached_together(self) -> None:
        tool = _tool(as_of="2025-06-01T00:00:00Z")
        with patch("httpx.get", return_value=_mock_response({"articles": []})) as mock_get:
            tool.execute(symbol="AAPL", limit=5)
            tool.execute(symbol="AAPL", limit=20)
        assert mock_get.call_count == 2
