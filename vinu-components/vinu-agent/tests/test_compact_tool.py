"""item #11 finding #2: compact_tool.py had zero test coverage."""

from __future__ import annotations

import json

from vinu_agent.tools.compact_tool import CompactTool


class TestCompactTool:
    def test_execute_signals_compaction(self) -> None:
        result = json.loads(CompactTool().execute())
        assert result["status"] == "ok"
        assert result["__compact"] is True

    def test_execute_ignores_any_kwargs(self) -> None:
        result = json.loads(CompactTool().execute(irrelevant="value"))
        assert result["status"] == "ok"
