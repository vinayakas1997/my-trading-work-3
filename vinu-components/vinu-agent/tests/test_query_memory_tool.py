"""query_memory_tool.py had zero test coverage before this file, despite
being the recall path that shapes what the agent "knows" before acting
on a symbol."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from vinu_agent.tools.query_memory_tool import QueryMemoryTool


def _tool(unified_memory) -> QueryMemoryTool:
    tool = QueryMemoryTool()
    tool._unified_memory = unified_memory
    return tool


class TestQueryMemoryTool:
    def test_no_unified_memory_returns_error(self) -> None:
        tool = QueryMemoryTool()
        result = json.loads(tool.execute(query="AAPL momentum"))
        assert result["status"] == "error"

    def test_successful_search_returns_serialized_results(self) -> None:
        entry = MagicMock()
        entry.to_dict.return_value = {"id": "agent-x", "content": "fades after 3 days"}
        memory = MagicMock()
        memory.search.return_value = [entry]
        tool = _tool(memory)
        result = json.loads(tool.execute(query="AAPL momentum", symbol="AAPL"))
        assert result["status"] == "ok"
        assert result["count"] == 1
        assert result["results"][0]["content"] == "fades after 3 days"

    def test_filters_and_limit_are_forwarded(self) -> None:
        memory = MagicMock()
        memory.search.return_value = []
        tool = _tool(memory)
        tool.execute(query="q", symbol="AAPL", source="news", memory_type="finding", limit=5)
        _, kwargs = memory.search.call_args
        assert kwargs["query"] == "q"
        assert kwargs["symbol"] == "AAPL"
        assert kwargs["source"] == "news"
        assert kwargs["memory_type"] == "finding"
        assert kwargs["limit"] == 5

    def test_limit_is_capped_at_50(self) -> None:
        memory = MagicMock()
        memory.search.return_value = []
        tool = _tool(memory)
        tool.execute(query="q", limit=500)
        _, kwargs = memory.search.call_args
        assert kwargs["limit"] == 50

    def test_default_limit_is_15(self) -> None:
        memory = MagicMock()
        memory.search.return_value = []
        tool = _tool(memory)
        tool.execute(query="q")
        _, kwargs = memory.search.call_args
        assert kwargs["limit"] == 15

    def test_empty_source_string_is_treated_as_no_filter(self) -> None:
        memory = MagicMock()
        memory.search.return_value = []
        tool = _tool(memory)
        tool.execute(query="q", source="")
        _, kwargs = memory.search.call_args
        assert kwargs["source"] is None

    def test_exception_from_search_returns_error(self) -> None:
        memory = MagicMock()
        memory.search.side_effect = RuntimeError("index corrupt")
        tool = _tool(memory)
        result = json.loads(tool.execute(query="q"))
        assert result["status"] == "error"
        assert "index corrupt" in result["error"]
