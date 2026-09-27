"""Tests for SessionService.run_team_once -- the headless team-run entry
point point 5's trigger wiring needs (reverse-engineering/
06-execution-handoff-and-architecture.md). Mocks build_registry/
TeamManager (their own correctness is covered elsewhere -- test_team.py
for TeamManager, tools discovery tests for build_registry) to verify
THIS method's wiring: does it pass through the SessionService's own
shared stores correctly, does it return TeamManager.run()'s result.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from vinu_agent.session.events import EventBus
from vinu_agent.session.service import SessionService
from vinu_agent.session.store import SessionStore


def _service(tmp_path) -> SessionService:
    return SessionService(
        store=SessionStore(tmp_path / "sessions"),
        event_bus=EventBus(),
        llm=MagicMock(name="llm"),
        skills_loader=MagicMock(name="skills_loader"),
        services_config={"vinu_live": "http://localhost:8091"},
        teams_dir=str(tmp_path / "teams"),
        run_store=MagicMock(name="run_store"),
        llm_call_store=MagicMock(name="llm_call_store"),
        strategy_store=MagicMock(name="strategy_store"),
        ticker_summary_store=MagicMock(name="ticker_summary_store"),
        ticker_ledger_store=MagicMock(name="ticker_ledger_store"),
    )


class TestRunTeamOnce:
    def test_builds_a_fresh_registry_and_runs_the_named_team(self, tmp_path) -> None:
        service = _service(tmp_path)
        fake_registry = MagicMock(name="registry")
        fake_manager = MagicMock(name="manager")
        fake_manager.run.return_value = {"status": "completed", "content": "```json\n{\"decision\": \"EXECUTE\"}\n```"}

        with patch("vinu_agent.tools.build_registry", return_value=fake_registry) as mock_build, \
             patch("vinu_agent.agent.team.TeamManager", return_value=fake_manager) as mock_tm:
            result = service.run_team_once("live_decision", "Ticker: AAPL\nStrategy: sma_cross", tag="AAPL-sma_cross")

        assert result == {"status": "completed", "content": "```json\n{\"decision\": \"EXECUTE\"}\n```"}
        mock_build.assert_called_once()
        mock_tm.assert_called_once()

        # The team dir resolves under this service's own teams_dir.
        team_dir_arg = mock_tm.call_args.args[0]
        assert team_dir_arg == Path(str(tmp_path / "teams")) / "live_decision"

        # Real shared stores threaded through, not fresh/duplicate ones.
        _, tm_kwargs = mock_tm.call_args
        assert tm_kwargs["llm"] is service._llm
        assert tm_kwargs["skills_loader"] is service._skills_loader
        assert tm_kwargs["run_store"] is service._run_store
        assert tm_kwargs["llm_call_store"] is service._llm_call_store
        assert tm_kwargs["strategy_store"] is service._strategy_store
        assert tm_kwargs["ticker_summary_store"] is service._ticker_summary_store
        assert tm_kwargs["ticker_ledger_store"] is service._ticker_ledger_store
        assert tm_kwargs["full_registry"] is fake_registry

        fake_manager.run.assert_called_once_with("Ticker: AAPL\nStrategy: sma_cross")

    def test_tag_is_used_in_the_synthetic_run_id(self, tmp_path) -> None:
        service = _service(tmp_path)
        fake_manager = MagicMock(name="manager")
        fake_manager.run.return_value = {"status": "completed", "content": ""}

        with patch("vinu_agent.tools.build_registry", return_value=MagicMock()) as mock_build, \
             patch("vinu_agent.agent.team.TeamManager", return_value=fake_manager):
            service.run_team_once("live_decision", "task", tag="AAPL-sma_cross")

        _, build_kwargs = mock_build.call_args
        assert "AAPL-sma_cross" in build_kwargs["session_id"]
        assert build_kwargs["session_id"].startswith("headless-")
