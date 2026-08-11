"""Tests for the skill-audit-worker CLI command -- Phase 9
scheduler-wiring (New-talk-agents/new-thinking/new-restructure/phases/
phase-9-scheduler-wiring/). check_skill_edits() (agent/skill_audit.py)
was correct and tested since Phase 6 but had no scheduled caller; this
worker gives it one, mirroring vinu-live's `while True: cycle(); sleep()`
pattern (vinu_live/cli.py).
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vinu_agent.cli import (
    _parse_args,
    planner_worker_main,
    resolve_worker_interval,
    significance_worker_main,
    skill_audit_worker_main,
)
from vinu_agent.config import AgentConfig


@pytest.fixture
def skills_root(tmp_path: Path) -> Path:
    risk_dir = tmp_path / "thesis-intake-risk-rules"
    risk_dir.mkdir()
    (risk_dir / "SKILL.md").write_text("---\nname: x\n---\n\nline1\n", encoding="utf-8")
    return tmp_path


def _config(skills_root: Path, memory_dir: Path, interval: int = 1) -> AgentConfig:
    return AgentConfig(
        skills_dir=str(skills_root),
        memory_dir=str(memory_dir),
        skill_audit_worker_interval_sec=interval,
    )


class TestResolveWorkerInterval:
    def test_explicit_args_interval_wins(self) -> None:
        config = AgentConfig(skill_audit_worker_interval_sec=3600)
        args = argparse.Namespace(interval_sec=120)
        assert resolve_worker_interval(args, config) == 120

    def test_falls_back_to_config_when_args_interval_unset(self) -> None:
        config = AgentConfig(skill_audit_worker_interval_sec=3600)
        args = argparse.Namespace(interval_sec=None)
        assert resolve_worker_interval(args, config) == 3600



class TestParseArgs:
    def test_skill_audit_worker_subcommand_interval_flag(self) -> None:
        args = _parse_args(["skill-audit-worker", "--interval", "45"])
        assert args.interval_sec == 45
        assert args.command == "skill-audit-worker"

    def test_planner_worker_subcommand_interval_flag(self) -> None:
        args = _parse_args(["planner-worker", "--interval", "60"])
        assert args.interval_sec == 60
        assert args.command == "planner-worker"

    def test_significance_worker_subcommand_interval_flag(self) -> None:
        args = _parse_args(["significance-worker", "--interval", "30"])
        assert args.interval_sec == 30
        assert args.command == "significance-worker"


class TestSkillAuditWorkerMain:
    def test_calls_check_skill_edits_and_stops_on_keyboard_interrupt(self, skills_root: Path, tmp_path: Path) -> None:
        memory_dir = tmp_path / "data" / "memory"
        memory_dir.parent.mkdir(parents=True, exist_ok=True)
        config = _config(skills_root, memory_dir)

        with patch("vinu_agent.cli.load_config", return_value=config), \
             patch("vinu_agent.cli.time.sleep", side_effect=KeyboardInterrupt):
            skill_audit_worker_main(argparse.Namespace(interval_sec=None))

        # A real SkillAuditStore was written under data_root (memory_dir's
        # parent) -- proves the worker actually ran check_skill_edits()
        # against the real skills_root, not a mock standing in for it.
        db_path = tmp_path / "data" / "skill_audit.db"
        assert db_path.exists()

    def test_explicit_interval_arg_overrides_config(self, skills_root: Path, tmp_path: Path) -> None:
        memory_dir = tmp_path / "data" / "memory"
        memory_dir.parent.mkdir(parents=True, exist_ok=True)
        config = _config(skills_root, memory_dir, interval=3600)

        with patch("vinu_agent.cli.load_config", return_value=config), \
             patch("vinu_agent.cli.time.sleep", side_effect=KeyboardInterrupt) as mock_sleep:
            skill_audit_worker_main(argparse.Namespace(interval_sec=7))

        mock_sleep.assert_called_once_with(7)


class TestPlannerWorkerMain:
    """planner-worker (Phase 9 scheduler-wiring): watchlist =
    TickerSummaryStore.list_summaries() (the decided source), RunLogTrigger
    refreshes each ticker's Summary Agent read, then ChangeGate + Planner
    triage (Phase 0's own run_gate_cycle, unmodified) decide whether to
    hand off to the research team. Every heavy dependency (AgentService,
    the real HTTP/LLM-calling pieces) is mocked here -- this proves the
    WIRING is correct, not the underlying mechanisms (each already has its
    own tests: ticker_gate.py, planner_triage_hook.py, scheduler_workers.py).
    """

    def test_wires_watchlist_through_runlog_trigger_and_gate_cycle(self) -> None:
        config = AgentConfig(planner_worker_interval_sec=1)
        fake_summary = MagicMock(ticker="AAPL")
        fake_service = MagicMock()
        fake_service.ticker_summary_store.list_summaries.return_value = [fake_summary]
        fake_service.__enter__.return_value = fake_service
        fake_service.__exit__.return_value = False

        with patch("vinu_agent.cli.load_config", return_value=config), \
             patch("vinu_agent.cli.AgentService", return_value=fake_service), \
             patch("vinu_agent.cli.HttpRunLogReader"), \
             patch("vinu_agent.cli.RunLogTrigger") as MockTrigger, \
             patch("vinu_agent.cli.ChangeGate") as MockGate, \
             patch("vinu_agent.cli.PlannerTriage"), \
             patch("vinu_agent.cli.hypothesis_reader_for"), \
             patch("vinu_agent.cli.make_summary_agent_fn"), \
             patch("vinu_agent.cli.make_planner_on_yes"), \
             patch("vinu_agent.cli.run_gate_cycle") as mock_run_gate_cycle, \
             patch("vinu_agent.cli.time.sleep", side_effect=KeyboardInterrupt):
            planner_worker_main(argparse.Namespace(interval_sec=None))

        MockTrigger.return_value.refresh_if_stale.assert_called_once()
        assert MockTrigger.return_value.refresh_if_stale.call_args[0][0] == "AAPL"
        mock_run_gate_cycle.assert_called_once()
        assert mock_run_gate_cycle.call_args[0][0] == ["AAPL"]
        assert mock_run_gate_cycle.call_args[0][1] is MockGate.return_value

    def test_summary_refresh_failure_does_not_abort_the_cycle(self) -> None:
        """One ticker's refresh failing must not stop the gate cycle from
        running for the rest of the watchlist."""
        config = AgentConfig(planner_worker_interval_sec=1)
        fake_service = MagicMock()
        fake_service.ticker_summary_store.list_summaries.return_value = [
            MagicMock(ticker="AAPL"), MagicMock(ticker="MSFT"),
        ]
        fake_service.__enter__.return_value = fake_service
        fake_service.__exit__.return_value = False

        with patch("vinu_agent.cli.load_config", return_value=config), \
             patch("vinu_agent.cli.AgentService", return_value=fake_service), \
             patch("vinu_agent.cli.HttpRunLogReader"), \
             patch("vinu_agent.cli.RunLogTrigger") as MockTrigger, \
             patch("vinu_agent.cli.ChangeGate"), \
             patch("vinu_agent.cli.PlannerTriage"), \
             patch("vinu_agent.cli.hypothesis_reader_for"), \
             patch("vinu_agent.cli.make_summary_agent_fn"), \
             patch("vinu_agent.cli.make_planner_on_yes"), \
             patch("vinu_agent.cli.run_gate_cycle") as mock_run_gate_cycle, \
             patch("vinu_agent.cli.time.sleep", side_effect=KeyboardInterrupt):
            MockTrigger.return_value.refresh_if_stale.side_effect = [RuntimeError("boom"), None]
            planner_worker_main(argparse.Namespace(interval_sec=None))

        assert MockTrigger.return_value.refresh_if_stale.call_count == 2
        mock_run_gate_cycle.assert_called_once()

    def test_no_seed_tickers_configured_skips_bootstrap(self) -> None:
        config = AgentConfig(planner_worker_interval_sec=1)  # watchlist_seed_tickers=[] by default
        fake_service = MagicMock()
        fake_service.ticker_summary_store.list_summaries.return_value = []
        fake_service.__enter__.return_value = fake_service
        fake_service.__exit__.return_value = False

        with patch("vinu_agent.cli.load_config", return_value=config), \
             patch("vinu_agent.cli.AgentService", return_value=fake_service), \
             patch("vinu_agent.cli.HttpRunLogReader"), \
             patch("vinu_agent.cli.RunLogTrigger"), \
             patch("vinu_agent.cli.ChangeGate"), \
             patch("vinu_agent.cli.PlannerTriage"), \
             patch("vinu_agent.cli.hypothesis_reader_for"), \
             patch("vinu_agent.cli.make_summary_agent_fn"), \
             patch("vinu_agent.cli.make_planner_on_yes"), \
             patch("vinu_agent.cli.run_gate_cycle"), \
             patch("vinu_agent.cli.bootstrap_new_tickers") as mock_bootstrap, \
             patch("vinu_agent.cli.time.sleep", side_effect=KeyboardInterrupt):
            planner_worker_main(argparse.Namespace(interval_sec=None))

        mock_bootstrap.assert_not_called()

    def test_seed_tickers_configured_triggers_bootstrap_before_the_cycle(self) -> None:
        config = AgentConfig(planner_worker_interval_sec=1, watchlist_seed_tickers=["NVDA"])
        fake_service = MagicMock()
        fake_service.ticker_summary_store.list_summaries.return_value = []
        fake_service.__enter__.return_value = fake_service
        fake_service.__exit__.return_value = False

        with patch("vinu_agent.cli.load_config", return_value=config), \
             patch("vinu_agent.cli.AgentService", return_value=fake_service), \
             patch("vinu_agent.cli.HttpRunLogReader"), \
             patch("vinu_agent.cli.RunLogTrigger"), \
             patch("vinu_agent.cli.ChangeGate"), \
             patch("vinu_agent.cli.PlannerTriage"), \
             patch("vinu_agent.cli.hypothesis_reader_for"), \
             patch("vinu_agent.cli.make_summary_agent_fn"), \
             patch("vinu_agent.cli.make_planner_on_yes"), \
             patch("vinu_agent.cli.run_gate_cycle"), \
             patch("vinu_agent.cli.bootstrap_new_tickers", return_value=["NVDA"]) as mock_bootstrap, \
             patch("vinu_agent.cli.time.sleep", side_effect=KeyboardInterrupt):
            planner_worker_main(argparse.Namespace(interval_sec=None))

        mock_bootstrap.assert_called_once_with(fake_service, ["NVDA"])


class TestSignificanceWorkerMain:
    def test_wires_watchlist_through_significance_cycle(self, tmp_path: Path) -> None:
        memory_dir = tmp_path / "data" / "memory"
        memory_dir.parent.mkdir(parents=True, exist_ok=True)
        config = AgentConfig(memory_dir=str(memory_dir), significance_worker_interval_sec=1)

        fake_summary = MagicMock(ticker="AAPL")
        fake_service = MagicMock()
        fake_service.ticker_summary_store.list_summaries.return_value = [fake_summary]
        fake_service.__enter__.return_value = fake_service
        fake_service.__exit__.return_value = False

        with patch("vinu_agent.cli.load_config", return_value=config), \
             patch("vinu_agent.cli.AgentService", return_value=fake_service), \
             patch("vinu_agent.cli.SignificanceFlagStore") as MockFlagStore, \
             patch("vinu_agent.cli.build_channel_targets", return_value=[]) as mock_targets, \
             patch("vinu_agent.cli.run_significance_cycle", new=AsyncMock(return_value=[])) as mock_cycle, \
             patch("vinu_agent.cli.time.sleep", side_effect=KeyboardInterrupt):
            significance_worker_main(argparse.Namespace(interval_sec=None))

        mock_targets.assert_called_once_with(config)
        mock_cycle.assert_called_once()
        assert mock_cycle.call_args[0][0] == ["AAPL"]
        # funding_threshold is wired from TradingMandate.load().max_order_value
        # (no mandate.yaml in this test env -> the dataclass default, 50000.0),
        # never a number invented in cli.py itself.
        assert mock_cycle.call_args[1]["funding_threshold"] == 50000.0
        MockFlagStore.return_value.close.assert_called_once()
