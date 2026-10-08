"""Tests for capital_allocator's scheduled caller (implementation-plan task
01, shortcoming #1). See agent/scheduler_workers.py's
run_capital_allocator_cycle and vinu_agent/cli.py's
capital_allocator_worker_main.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vinu_agent.agent.scheduler_workers import run_capital_allocator_cycle
from vinu_agent.config import AgentConfig


def _fake_service() -> MagicMock:
    service = MagicMock()
    service.config.services = {"vinu_initial_analysis": "http://x"}
    service.config.teams_dir = "/teams"
    return service


def _fake_pend_artifact(artifact_id: str = "art_123") -> MagicMock:
    artifact = MagicMock()
    artifact.artifact_id = artifact_id
    return artifact


class TestRunCapitalAllocatorCycle:
    def test_no_pend_artifacts_skips_team_run(self) -> None:
        service = _fake_service()
        service._strategy_store.list_artifacts_by_statuses.return_value = []

        with patch("vinu_agent.agent.scheduler_workers.run_team_for_ticker") as mock_run:
            result = run_capital_allocator_cycle(service, budget=100000.0, cycle=1)

        assert result["status"] == "skipped"
        assert result["pend_candidates"] == 0
        mock_run.assert_not_called()

    def test_pend_batch_handed_to_capital_allocator_team_with_budget(self) -> None:
        service = _fake_service()
        service._strategy_store.list_artifacts_by_statuses.return_value = [
            _fake_pend_artifact("art_1"), _fake_pend_artifact("art_2"),
        ]

        with patch(
            "vinu_agent.agent.scheduler_workers.run_team_for_ticker",
            return_value={"status": "completed", "content": "ok", "run_id": "run_7",
                          "artifact_id": "art_1,art_2"},
        ) as mock_run:
            result = run_capital_allocator_cycle(service, budget=100000.0, cycle=3)

        assert result["status"] == "ok"
        assert result["run_id"] == "run_7"
        assert result["pend_candidates"] == 2
        assert result["funded"] == ["art_1", "art_2"]

        assert mock_run.call_count == 1
        call_args = mock_run.call_args
        assert call_args[0][1] == "capital_allocator"
        task_text = call_args[0][2]
        assert "art_1, art_2" in task_text
        assert "100000.00" in task_text
        assert call_args.kwargs["session_id"] == "capital-allocator-3"

    def test_queries_only_pend_status(self) -> None:
        from vinu_research.models import ArtifactStatus

        service = _fake_service()
        service._strategy_store.list_artifacts_by_statuses.return_value = []

        with patch("vinu_agent.agent.scheduler_workers.run_team_for_ticker"):
            run_capital_allocator_cycle(service, budget=50000.0, cycle=1)

        service._strategy_store.list_artifacts_by_statuses.assert_called_once_with([ArtifactStatus.PEND])


class TestCapitalAllocatorWorkerConfig:
    def test_default_cadence_is_documented_900s(self) -> None:
        assert AgentConfig().capital_allocator_worker_interval_sec == 900

    def test_default_budget_is_100000(self) -> None:
        assert AgentConfig().capital_allocator_budget == 100000.0

class TestBudgetFromTheRealMoneyLedger:
    def _service(self):
        service = _fake_service()
        service._strategy_store.list_artifacts_by_statuses.return_value = [_fake_pend_artifact("art_1")]
        return service

    def test_with_a_capital_base_the_budget_is_the_ledgers_free_cash_not_the_configured_figure(self, monkeypatch) -> None:
        monkeypatch.setenv("VINU_ACCOUNT_MODE", "real")
        monkeypatch.setenv("VINU_REAL_CAPITAL", "20")
        ledger = {"status": "ok", "capped": True, "free_cash": 10.24}
        with patch("vinu_agent.broker.capital_ledger_client.fetch_capital_ledger", return_value=ledger), patch(
            "vinu_agent.agent.scheduler_workers.run_team_for_ticker", return_value={"run_id": "r", "artifact_id": ""},
        ) as mock_run:
            run_capital_allocator_cycle(self._service(), budget=100000.0, cycle=1)
        task_text = mock_run.call_args[0][2]
        assert "$10.24" in task_text and "100000" not in task_text

    def test_an_unreadable_ledger_funds_nothing(self, monkeypatch) -> None:
        monkeypatch.setenv("VINU_ACCOUNT_MODE", "real")
        monkeypatch.setenv("VINU_REAL_CAPITAL", "20")
        with patch("vinu_agent.broker.capital_ledger_client.fetch_capital_ledger", return_value=None), patch(
            "vinu_agent.agent.scheduler_workers.run_team_for_ticker",
        ) as mock_run:
            result = run_capital_allocator_cycle(self._service(), budget=100000.0, cycle=1)
        assert result["status"] == "skipped" and "ledger" in result["reason"]
        mock_run.assert_not_called()

    def test_no_free_cash_funds_nothing(self, monkeypatch) -> None:
        monkeypatch.setenv("VINU_ACCOUNT_MODE", "real")
        monkeypatch.setenv("VINU_REAL_CAPITAL", "20")
        with patch("vinu_agent.broker.capital_ledger_client.fetch_capital_ledger", return_value={"capped": True, "free_cash": 0.0}), patch(
            "vinu_agent.agent.scheduler_workers.run_team_for_ticker",
        ) as mock_run:
            result = run_capital_allocator_cycle(self._service(), budget=100000.0, cycle=1)
        assert result["status"] == "skipped"
        mock_run.assert_not_called()
