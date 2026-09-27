"""item #11 finding #2: correlation_tool.py's as-of clamp had zero test
coverage, same pattern as stock_price_tool.py/news_tool.py."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from vinu_agent.tools.correlation_tool import CorrelationTool


def _tool(as_of: str | None = None) -> CorrelationTool:
    tool = CorrelationTool()
    tool._services_config = {"vinu_initial_analysis": "http://correlation-api:8083"}
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
        assert params["to_ts"] == 1748736000  # 2025-06-01T00:00:00Z
        assert result["clamped_end_to_as_of"] is True

    def test_end_date_within_as_of_is_not_clamped(self) -> None:
        with patch("httpx.get", return_value=_mock_response({})) as mock_get:
            result = json.loads(_tool(as_of="2025-06-01T00:00:00Z").execute(
                symbol="AAPL", start_date="2025-05-01", end_date="2025-05-15",
            ))
        params = mock_get.call_args.kwargs["params"]
        assert params["to_ts"] == 1747267200  # 2025-05-15T00:00:00Z
        assert "clamped_end_to_as_of" not in result

    def test_no_as_of_set_never_clamps(self) -> None:
        with patch("httpx.get", return_value=_mock_response({})) as mock_get:
            result = json.loads(_tool(as_of=None).execute(
                symbol="AAPL", start_date="2025-05-01", end_date="2025-12-31",
            ))
        params = mock_get.call_args.kwargs["params"]
        assert params["to_ts"] == 1767139200  # 2025-12-31T00:00:00Z, unclamped
        assert "clamped_end_to_as_of" not in result

    def test_symbol_uppercased_in_url(self) -> None:
        with patch("httpx.get", return_value=_mock_response({})) as mock_get:
            _tool().execute(symbol="aapl", start_date="2025-05-01", end_date="2025-05-15")
        args, _ = mock_get.call_args
        assert args[0].endswith("/analysis/correlation/AAPL")
