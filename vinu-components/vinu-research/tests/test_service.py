from __future__ import annotations

import pytest

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
    async def test_async_context_manager(self, storage):
        from vinu_research.config import ResearchConfig
        from vinu_research.service import ResearchService
        cfg = ResearchConfig()
        async with ResearchService(config=cfg, storage=storage) as svc:
            runs = await svc.list_runs()
            assert runs == []

    async def test_properties(self, service, storage):
        assert service.config is not None
        assert service.storage is storage
