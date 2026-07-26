"""Integration test: research_catalog exhaustion + loop early-exit.

Verifies that:
1. update_catalog_after_run tracks validation failures correctly
2. Auto-exhaustion at 5 consecutive failures
3. is_symbol_exhausted detects both exhausted flag and high-trial-low-sharpe condition
4. StrategyResearchLoop.run() returns early for exhausted symbols
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import tempfile

from vinu_research.loop import StrategyResearchLoop
from vinu_research.models import ResearchResult
from vinu_research.storage.sqlite_backend import ResearchStorage


@pytest.fixture
def storage() -> ResearchStorage:
    p = Path(tempfile.mktemp(suffix=".db"))
    s = ResearchStorage(p)
    yield s
    s.close()
    p.unlink(missing_ok=True)


class TestCatalogExhaustion:
    def test_validation_failure_increments_counter(self, storage: ResearchStorage) -> None:
        storage.update_catalog_after_run("AAPL", run_id=1, trial_count=5, sharpe=0.5, validated=False)
        entry = storage.get_catalog_entry("AAPL")
        assert entry is not None
        assert entry["consecutive_validation_failures"] == 1
        assert entry["total_validated_count"] == 0
        assert entry["exhausted"] == 0

    def test_validation_pass_resets_counter(self, storage: ResearchStorage) -> None:
        storage.update_catalog_after_run("AAPL", run_id=1, trial_count=5, sharpe=0.5, validated=False)
        storage.update_catalog_after_run("AAPL", run_id=2, trial_count=10, sharpe=0.8, validated=True)
        entry = storage.get_catalog_entry("AAPL")
        assert entry["consecutive_validation_failures"] == 0
        assert entry["total_validated_count"] == 1
        assert entry["last_validation_verdict"] == 1

    def test_auto_exhaust_after_five_failures(self, storage: ResearchStorage) -> None:
        for i in range(5):
            storage.update_catalog_after_run("AAPL", run_id=i + 1, trial_count=i * 5, sharpe=0.5, validated=False)
        entry = storage.get_catalog_entry("AAPL")
        assert entry["exhausted"] == 1
        assert storage.is_symbol_exhausted("AAPL") is True

    def test_high_trial_low_sharpe_exhaustion(self, storage: ResearchStorage) -> None:
        storage.update_catalog_after_run("AAPL", run_id=1, trial_count=25, sharpe=0.2, validated=False)
        assert storage.is_symbol_exhausted("AAPL") is True

    def test_inexhausted_symbol_returns_false(self, storage: ResearchStorage) -> None:
        storage.update_catalog_after_run("AAPL", run_id=1, trial_count=3, sharpe=1.2, validated=True)
        assert storage.is_symbol_exhausted("AAPL") is False

    def test_exhaust_and_clear(self, storage: ResearchStorage) -> None:
        storage.update_catalog_after_run("AAPL", run_id=1, trial_count=5, sharpe=0.5, validated=False)
        storage.update_catalog_after_run("AAPL", run_id=2, trial_count=5, sharpe=0.5, validated=False)
        storage.update_catalog_after_run("AAPL", run_id=3, trial_count=5, sharpe=0.5, validated=False)
        storage.update_catalog_after_run("AAPL", run_id=4, trial_count=5, sharpe=0.5, validated=False)
        storage.update_catalog_after_run("AAPL", run_id=5, trial_count=5, sharpe=0.5, validated=False)
        assert storage.is_symbol_exhausted("AAPL") is True
        storage.clear_exhaustion("AAPL")
        assert storage.is_symbol_exhausted("AAPL") is False

    def test_exhaust_symbol_manually(self, storage: ResearchStorage) -> None:
        storage.update_catalog_after_run("AAPL", run_id=1, trial_count=3, sharpe=1.2, validated=True)
        assert storage.is_symbol_exhausted("AAPL") is False
        storage.exhaust_symbol("AAPL")
        assert storage.is_symbol_exhausted("AAPL") is True


class TestLoopExhaustion:
    @pytest.mark.asyncio
    async def test_loop_returns_early_when_exhausted(self, storage: ResearchStorage) -> None:
        storage.update_catalog_after_run("AAPL", run_id=1, trial_count=25, sharpe=0.2, validated=False)

        loop = StrategyResearchLoop(storage=storage)
        result = await loop.run(
            user_idea="test", symbol="AAPL",
            from_date="2024-01-01", to_date="2024-06-01",
        )
        assert isinstance(result, ResearchResult)
        assert result.total_iterations == 0
        assert result.best_result is None
        assert "exhausted" in result.report_md.lower()

    @pytest.mark.skip(reason="Needs a running simulator at http://127.0.0.1:8085")
    @pytest.mark.asyncio
    async def test_loop_runs_normally_when_not_exhausted(self, storage: ResearchStorage) -> None:
        storage.update_catalog_after_run("AAPL", run_id=1, trial_count=3, sharpe=1.2, validated=True)

        loop = StrategyResearchLoop(storage=storage)
        result = await loop.run(
            user_idea="test", symbol="AAPL",
            from_date="2024-01-01", to_date="2024-06-01",
        )
        assert isinstance(result, ResearchResult)
        assert "exhausted" not in result.report_md.lower()
