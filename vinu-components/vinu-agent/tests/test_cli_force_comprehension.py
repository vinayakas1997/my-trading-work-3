"""Tests for `vinu-agent force-comprehension <ticker>` -- the manual
override for the angle-coverage gate
(missing-pieces-of-system/angle-comprehension-hierarchy/01-plan.md
Step 8): run angle comprehension for one ticker right now, bypassing
both the run_id-staleness check and the coverage gate, for a human who's
decided waiting isn't worth it.
"""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

from vinu_agent.cli import _cmd_force_comprehension, _parse_args


class TestParseArgs:
    def test_force_comprehension_parses_ticker(self) -> None:
        args = _parse_args(["force-comprehension", "aapl"])
        assert args.command == "force-comprehension"
        assert args.ticker == "aapl"


class TestCmdForceComprehension:
    def test_calls_force_refresh_not_refresh_if_stale(self, capsys) -> None:
        fake_service = MagicMock()
        fake_service.__enter__.return_value = fake_service
        fake_service.__exit__.return_value = False
        fake_summary = MagicMock(angles_with_data=25, angle_count=28)
        fake_service.ticker_summary_store.get_summary.return_value = fake_summary

        with patch("vinu_agent.cli.AgentService", return_value=fake_service), \
             patch("vinu_agent.cli.HttpRunLogReader"), \
             patch("vinu_agent.cli.RunLogTrigger") as MockTrigger, \
             patch("vinu_agent.cli.make_summary_agent_fn") as mock_make_fn:
            from vinu_agent.agent.ticker_gate import RunLogTriggerResult
            MockTrigger.return_value.force_refresh.return_value = RunLogTriggerResult(
                should_refresh=True, new_run_id="run-42",
            )
            _cmd_force_comprehension(argparse.Namespace(ticker="aapl"))

        MockTrigger.return_value.force_refresh.assert_called_once()
        call_args = MockTrigger.return_value.force_refresh.call_args[0]
        assert call_args[0] == "AAPL"  # normalized uppercase
        assert call_args[1] is mock_make_fn.return_value
        MockTrigger.return_value.refresh_if_stale.assert_not_called()

        out = capsys.readouterr().out
        assert "AAPL" in out
        assert "run-42" in out
        assert "25/28" in out
