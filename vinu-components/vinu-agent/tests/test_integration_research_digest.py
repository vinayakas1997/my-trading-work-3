"""Integration test: ContextBuilder + ResearchDigestReader — confirms a
found digest actually reaches the injected block, the same acceptance
pattern used for the Facts Registry and the freshness reader."""

from __future__ import annotations

from unittest.mock import MagicMock

from vinu_agent.agent.context import ContextBuilder
from vinu_agent.agent.tools import ToolRegistry


def _fake_reader(findings: list[dict]) -> MagicMock:
    reader = MagicMock()
    reader.check_symbols.return_value = findings
    return reader


class TestResearchDigestIntegration:
    def test_digest_finding_reaches_injected_block(self) -> None:
        reader = _fake_reader([
            {"symbol": "AAPL", "run_id": 7, "summary_text": "Tried momentum, Sharpe 1.4, promoted.", "best_sharpe": 1.4, "status": "done"},
        ])
        builder = ContextBuilder(registry=ToolRegistry(), research_digest_reader=reader)
        messages = builder.build_messages([], "What's happening with AAPL today?")
        digest_msgs = [m for m in messages if ContextBuilder.is_recent_research_msg(m)]
        assert len(digest_msgs) == 1
        assert "Tried momentum, Sharpe 1.4, promoted." in digest_msgs[0]["content"]
        assert builder.last_research_digest_msg is not None

    def test_no_findings_means_no_block(self) -> None:
        reader = _fake_reader([])
        builder = ContextBuilder(registry=ToolRegistry(), research_digest_reader=reader)
        messages = builder.build_messages([], "What's happening with AAPL today?")
        assert not any(ContextBuilder.is_recent_research_msg(m) for m in messages)
        assert builder.last_research_digest_msg is None

    def test_no_reader_means_no_block_and_no_crash(self) -> None:
        builder = ContextBuilder(registry=ToolRegistry())
        messages = builder.build_messages([], "AAPL check")
        assert not any(ContextBuilder.is_recent_research_msg(m) for m in messages)
        assert builder.last_research_digest_msg is None

    def test_no_symbols_in_play_skips_the_check_entirely(self) -> None:
        reader = _fake_reader([{"symbol": "TSLA", "run_id": 1, "summary_text": "x", "best_sharpe": 1.0, "status": "done"}])
        builder = ContextBuilder(registry=ToolRegistry(), research_digest_reader=reader)
        builder.build_messages([], "no tickers mentioned at all")
        reader.check_symbols.assert_not_called()

    def test_held_symbol_triggers_check_even_without_mention(self) -> None:
        reader = _fake_reader([
            {"symbol": "TSLA", "run_id": 3, "summary_text": "Held-symbol digest.", "best_sharpe": 1.1, "status": "done"},
        ])
        builder = ContextBuilder(registry=ToolRegistry(), research_digest_reader=reader, held_symbols=["TSLA"])
        messages = builder.build_messages([], "general check-in")
        digest_msgs = [m for m in messages if ContextBuilder.is_recent_research_msg(m)]
        assert len(digest_msgs) == 1
        reader.check_symbols.assert_called_once_with(["TSLA"])
