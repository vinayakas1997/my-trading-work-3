from __future__ import annotations

import pytest

from vinu_research.models import Goal
from vinu_research.service import _has_violated_goal_constraints
from vinu_research.storage import STATUS_DONE, STATUS_FAILED, STATUS_PENDING


class TestListGetDelete:
    async def test_list_runs_empty(self, service):
        runs = await service.list_runs()
        assert runs == []

    async def test_list_runs_after_insert(self, service, storage, sample_record):
        storage.insert_run(sample_record)
        runs = await service.list_runs()
        assert len(runs) == 1

    async def test_get_run_missing(self, service):
        assert await service.get_run(999) is None

    async def test_delete_run_missing(self, service):
        assert await service.delete_run(999) is False

    async def test_delete_run(self, service, storage, sample_record):
        r = storage.insert_run(sample_record)
        assert await service.delete_run(r.id) is True
        assert await service.get_run(r.id) is not None


class TestApprove:
    async def test_approve_run_missing(self, service):
        assert await service.approve_run(999) is None

    async def test_approve_run(self, service, storage, sample_record):
        sample_record.status = "done"
        r = storage.insert_run(sample_record)
        result = await service.approve_run(r.id)
        assert result is not None
        assert result["approved"] is True
        assert result["status"] == "approved"

    async def test_approve_run_not_done(self, service, storage, sample_record):
        r = storage.insert_run(sample_record)
        result = await service.approve_run(r.id)
        assert result is None

    async def test_approve_run_creates_artifact(self, service, storage, sample_record):
        """Approving a done run must bridge into the strategy_store — this is
        the fix for the previously-disconnected approve/artifact systems."""
        sample_record.status = "done"
        sample_record.best_sharpe = 1.8
        sample_record.best_max_dd = -0.12
        sample_record.strategy_code = "class UserStrategy: pass"
        r = storage.insert_run(sample_record)

        result = await service.approve_run(r.id)
        assert "artifact_id" in result

        from vinu_research.models import ArtifactStatus
        artifacts = service.strategy_store.list_artifacts_for_symbol(
            sample_record.symbol, [ArtifactStatus.ACTIVE],
        )
        assert len(artifacts) == 1
        art = artifacts[0]
        assert art.artifact_id == result["artifact_id"]
        assert art.strategy_code == "class UserStrategy: pass"
        assert art.source_run_id == r.id
        assert art.initial_sharpe == 1.8
        assert art.initial_max_dd == -0.12

        history = service.strategy_store.get_bench_history(art.artifact_id)
        assert len(history) == 1
        assert history[0].sharpe == 1.8


class TestEnsureStrategy:
    async def test_runs_when_no_existing_strategy(self, service, storage, sample_record):
        assert await service.has_active_strategy(sample_record.symbol) is False

    async def test_skips_when_active_strategy_exists(self, service, storage, sample_record):
        sample_record.status = "done"
        sample_record.strategy_code = "class UserStrategy: pass"
        r = storage.insert_run(sample_record)
        await service.approve_run(r.id)

        assert await service.has_active_strategy(sample_record.symbol) is True

        result = await service.ensure_strategy(
            "any idea", sample_record.symbol, sample_record.from_date, sample_record.to_date,
        )
        assert result["skipped"] is True


class TestHealth:
    async def test_health_returns_service_info(self, service):
        info = await service.health()
        assert info["service"] == "vinu-research"
        assert info["version"] == "0.1.0"
        assert "dependencies" in info
        assert "total_runs" in info

    async def test_health_deps_not_reachable(self, service):
        info = await service.health()
        for dep in ("simulator", "features", "correlation"):
            assert not info["dependencies"][dep]["reachable"]


class TestContextManager:
    async def test_async_context_manager(self, storage, tmp_path):
        from vinu_research.config import ResearchConfig
        from vinu_research.service import ResearchService
        cfg = ResearchConfig(data_root=tmp_path)
        async with ResearchService(config=cfg, storage=storage) as svc:
            runs = await svc.list_runs()
            assert runs == []

    async def test_properties(self, service, storage):
        assert service.config is not None
        assert service.storage is storage


class TestGoalCompliance:
    def test_violated_when_llm_calls_exceed_budget(self):
        goal = Goal(goal_id="g1", hypothesis_id="h1", objective="test", llm_calls_budget=5, llm_calls_used=6)
        assert _has_violated_goal_constraints(goal) is True

    def test_not_violated_when_llm_calls_within_budget(self):
        goal = Goal(goal_id="g2", hypothesis_id="h1", objective="test", llm_calls_budget=5, llm_calls_used=3)
        assert _has_violated_goal_constraints(goal) is False

    def test_not_violated_when_no_budget_set(self):
        goal = Goal(goal_id="g3", hypothesis_id="h1", objective="test", llm_calls_budget=0, llm_calls_used=100)
        assert _has_violated_goal_constraints(goal) is False

    def test_violated_when_time_exceeds_budget(self):
        goal = Goal(goal_id="g4", hypothesis_id="h1", objective="test", time_budget_seconds=60.0, time_used_seconds=120.0)
        assert _has_violated_goal_constraints(goal) is True

    def test_not_violated_within_all_budgets(self):
        goal = Goal(goal_id="g5", hypothesis_id="h1", objective="test", llm_calls_budget=10, llm_calls_used=5, time_budget_seconds=100.0, time_used_seconds=50.0)
        assert _has_violated_goal_constraints(goal) is False


class TestRevalidate:
    @pytest.mark.asyncio
    async def test_revalidate_missing_artifact(self, service):
        result = await service.revalidate_artifact("nonexistent")
        assert result["revalidated"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_revalidate_no_strategy_code(self, service, strategy_store):
        from vinu_research.models import Artifact
        a = Artifact.create("strategy", "NoCode", universe=["AAPL"])
        a.strategy_code = ""
        strategy_store.upsert_artifact(a)
        result = await service.revalidate_artifact(a.artifact_id)
        assert result["revalidated"] is False
        assert "No strategy code" in result["error"]
