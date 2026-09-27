"""remember_tool.py had zero test coverage before this file, despite
writing to persistent cross-session memory that later informs decisions.
A real, previously-untested risk found while writing these:
`id=f"agent-{name}"` means re-remembering under the same name silently
overwrote the prior entry, including resetting `created_at` to "now" --
losing when this was first remembered, with no signal to the caller that
anything was overwritten at all. Fixed alongside these tests: an
overwrite now preserves the original `created_at` and the response flags
`overwritten: true`."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from vinu_agent.tools.remember_tool import RememberTool


def _tool(unified_memory) -> RememberTool:
    tool = RememberTool()
    tool._unified_memory = unified_memory
    return tool


class TestRememberToolBasics:
    def test_no_unified_memory_returns_error(self) -> None:
        tool = RememberTool()
        result = json.loads(tool.execute(name="aapl-momentum-decay", content="fades after 3 days"))
        assert result["status"] == "error"

    def test_new_memory_saves_with_expected_id_and_fields(self) -> None:
        unified = MagicMock()
        unified.get_entry.return_value = None
        tool = _tool(unified)
        result = json.loads(tool.execute(
            name="aapl-momentum-decay", content="fades after 3 days", symbol="AAPL", memory_type="finding",
        ))
        assert result["status"] == "ok"
        assert result["name"] == "aapl-momentum-decay"
        assert "overwritten" not in result
        entry = unified.add_entry.call_args[0][0]
        assert entry.id == "agent-aapl-momentum-decay"
        assert entry.symbol == "AAPL"
        assert entry.content == "fades after 3 days"
        assert entry.summary == "fades after 3 days"

    def test_content_over_200_chars_is_truncated_in_summary_only(self) -> None:
        unified = MagicMock()
        unified.get_entry.return_value = None
        tool = _tool(unified)
        long_content = "x" * 300
        tool.execute(name="n", content=long_content)
        entry = unified.add_entry.call_args[0][0]
        assert entry.content == long_content
        assert len(entry.summary) == 200

    def test_exception_from_add_entry_returns_error(self) -> None:
        unified = MagicMock()
        unified.get_entry.return_value = None
        unified.add_entry.side_effect = RuntimeError("disk full")
        tool = _tool(unified)
        result = json.loads(tool.execute(name="n", content="c"))
        assert result["status"] == "error"
        assert "disk full" in result["error"]


class TestRememberToolOverwrite:
    def test_re_remembering_the_same_name_flags_overwritten(self) -> None:
        unified = MagicMock()
        existing = MagicMock()
        existing.created_at = "2024-01-01T00:00:00Z"
        unified.get_entry.return_value = existing
        tool = _tool(unified)
        result = json.loads(tool.execute(name="aapl-momentum-decay", content="updated finding"))
        assert result["overwritten"] is True

    def test_overwrite_preserves_the_original_created_at(self) -> None:
        unified = MagicMock()
        existing = MagicMock()
        existing.created_at = "2024-01-01T00:00:00Z"
        unified.get_entry.return_value = existing
        tool = _tool(unified)
        tool.execute(name="aapl-momentum-decay", content="updated finding")
        entry = unified.add_entry.call_args[0][0]
        assert entry.created_at == "2024-01-01T00:00:00Z"

    def test_overwrite_still_replaces_the_content(self) -> None:
        unified = MagicMock()
        existing = MagicMock()
        existing.created_at = "2024-01-01T00:00:00Z"
        unified.get_entry.return_value = existing
        tool = _tool(unified)
        tool.execute(name="aapl-momentum-decay", content="brand new content")
        entry = unified.add_entry.call_args[0][0]
        assert entry.content == "brand new content"
