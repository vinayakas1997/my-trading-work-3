"""item #11 finding #2: session_search_tool.py had zero test coverage."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from vinu_agent.tools.session_search_tool import SessionSearchTool


class TestSessionSearchTool:
    def test_no_session_service_returns_error(self) -> None:
        tool = SessionSearchTool()
        result = json.loads(tool.execute(query="AAPL earnings"))
        assert result["status"] == "error"

    def test_search_results_are_returned(self) -> None:
        tool = SessionSearchTool()
        tool._session_service = MagicMock(search=MagicMock(return_value=[{"id": 1}, {"id": 2}]))
        result = json.loads(tool.execute(query="AAPL earnings"))
        assert result["status"] == "ok"
        assert result["results"] == [{"id": 1}, {"id": 2}]

    def test_results_truncated_to_ten(self) -> None:
        tool = SessionSearchTool()
        tool._session_service = MagicMock(search=MagicMock(return_value=list(range(50))))
        result = json.loads(tool.execute(query="q"))
        assert len(result["results"]) == 10

    def test_search_raising_is_caught_and_reported(self) -> None:
        tool = SessionSearchTool()
        tool._session_service = MagicMock(search=MagicMock(side_effect=RuntimeError("db down")))
        result = json.loads(tool.execute(query="q"))
        assert result["status"] == "error"
        assert "db down" in result["error"]
