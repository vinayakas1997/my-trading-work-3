from __future__ import annotations

from vinu_agent.swarm.models import RunStatus, SwarmRun
from vinu_agent.swarm.store import SwarmStore


class TestFindLatestRun:
    def test_returns_none_when_no_matching_run(self, tmp_path) -> None:
        store = SwarmStore(tmp_path)
        assert store.find_latest_run("investment_committee", "AAPL") is None

    def test_finds_matching_completed_run(self, tmp_path) -> None:
        store = SwarmStore(tmp_path)
        run = SwarmRun(
            preset_name="investment_committee", user_vars={"symbol": "AAPL"},
            status=RunStatus.COMPLETED, final_report="Bullish overall.",
        )
        store.save(run)

        found = store.find_latest_run("investment_committee", "AAPL")

        assert found is not None
        assert found.run_id == run.run_id

    def test_symbol_match_is_case_insensitive(self, tmp_path) -> None:
        store = SwarmStore(tmp_path)
        run = SwarmRun(
            preset_name="investment_committee", user_vars={"symbol": "aapl"},
            status=RunStatus.COMPLETED,
        )
        store.save(run)

        assert store.find_latest_run("investment_committee", "AAPL") is not None

    def test_ignores_runs_for_a_different_preset(self, tmp_path) -> None:
        store = SwarmStore(tmp_path)
        run = SwarmRun(
            preset_name="other_preset", user_vars={"symbol": "AAPL"}, status=RunStatus.COMPLETED,
        )
        store.save(run)

        assert store.find_latest_run("investment_committee", "AAPL") is None

    def test_ignores_runs_for_a_different_symbol(self, tmp_path) -> None:
        store = SwarmStore(tmp_path)
        run = SwarmRun(
            preset_name="investment_committee", user_vars={"symbol": "MSFT"}, status=RunStatus.COMPLETED,
        )
        store.save(run)

        assert store.find_latest_run("investment_committee", "AAPL") is None

    def test_ignores_non_completed_runs_by_default(self, tmp_path) -> None:
        store = SwarmStore(tmp_path)
        run = SwarmRun(
            preset_name="investment_committee", user_vars={"symbol": "AAPL"}, status=RunStatus.RUNNING,
        )
        store.save(run)

        assert store.find_latest_run("investment_committee", "AAPL") is None

    def test_returns_the_most_recently_created_matching_run(self, tmp_path) -> None:
        store = SwarmStore(tmp_path)
        older = SwarmRun(
            preset_name="investment_committee", user_vars={"symbol": "AAPL"},
            status=RunStatus.COMPLETED, created_at="2024-01-01T00:00:00Z",
            final_report="stale",
        )
        newer = SwarmRun(
            preset_name="investment_committee", user_vars={"symbol": "AAPL"},
            status=RunStatus.COMPLETED, created_at="2024-06-01T00:00:00Z",
            final_report="fresh",
        )
        store.save(older)
        store.save(newer)

        found = store.find_latest_run("investment_committee", "AAPL")

        assert found.run_id == newer.run_id
