"""Integration test: ContextBuilder + FreshnessChecker.

Confirms a stale finding actually reaches the injected block — not just
that FreshnessChecker.check_symbols() returns a finding in isolation. Same
failure mode as the Facts Registry's own acceptance test: a finding that
never reaches the model is functionally identical to it not existing.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from vinu_agent.agent.context import ContextBuilder
from vinu_agent.agent.tools import ToolRegistry


def _fake_checker(findings: list[dict]) -> MagicMock:
    checker = MagicMock()
    checker.check_symbols.return_value = findings
    return checker


class TestFreshnessIntegration:
    def test_stale_finding_reaches_injected_block(self) -> None:
        checker = _fake_checker([
            {"symbol": "JNJ", "angle": "regime_analysis", "analysis_at": "2026-07-01T00:00:00+00:00", "age_days": 5.0},
        ])
        builder = ContextBuilder(registry=ToolRegistry(), freshness_checker=checker)
        messages = builder.build_messages([], "What's happening with JNJ today?")
        warnings = [m for m in messages if ContextBuilder.is_freshness_warnings_msg(m)]
        assert len(warnings) == 1
        assert "JNJ" in warnings[0]["content"]
        assert "5.0 days ago" in warnings[0]["content"]
        assert builder.last_freshness_msg is not None

    def test_no_findings_means_no_block(self) -> None:
        checker = _fake_checker([])
        builder = ContextBuilder(registry=ToolRegistry(), freshness_checker=checker)
        messages = builder.build_messages([], "What's happening with JNJ today?")
        assert not any(ContextBuilder.is_freshness_warnings_msg(m) for m in messages)
        assert builder.last_freshness_msg is None

    def test_no_checker_means_no_block_and_no_crash(self) -> None:
        builder = ContextBuilder(registry=ToolRegistry())
        messages = builder.build_messages([], "JNJ check")
        assert not any(ContextBuilder.is_freshness_warnings_msg(m) for m in messages)
        assert builder.last_freshness_msg is None

    def test_no_symbols_in_play_skips_the_check_entirely(self) -> None:
        checker = _fake_checker([{"symbol": "AAPL", "angle": "regime_analysis", "analysis_at": "x", "age_days": 5.0}])
        builder = ContextBuilder(registry=ToolRegistry(), freshness_checker=checker)
        builder.build_messages([], "no tickers mentioned at all")
        checker.check_symbols.assert_not_called()

    def test_held_symbol_triggers_check_even_without_mention(self) -> None:
        checker = _fake_checker([
            {"symbol": "TSLA", "angle": "regime_analysis", "analysis_at": "x", "age_days": 3.0},
        ])
        builder = ContextBuilder(registry=ToolRegistry(), freshness_checker=checker, held_symbols=["TSLA"])
        messages = builder.build_messages([], "general check-in")
        warnings = [m for m in messages if ContextBuilder.is_freshness_warnings_msg(m)]
        assert len(warnings) == 1
        checker.check_symbols.assert_called_once_with(["TSLA"])
