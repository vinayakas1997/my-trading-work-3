from __future__ import annotations

import tempfile
import pytest
from pathlib import Path

from vinu_research.scheduled.cron import next_run, parse_cron
from vinu_research.scheduled.executor import ScheduledResearchExecutor
from vinu_research.scheduled.models import ScheduledResearchJob
from vinu_research.scheduled.store import ScheduledResearchJobStore


class TestCronParser:
    def test_parse_star(self):
        result = parse_cron("* * * * *")
        assert result["minute"] == list(range(0, 60))
        assert result["hour"] == list(range(0, 24))

    def test_parse_step(self):
        result = parse_cron("*/15 * * * *")
        assert result["minute"] == [0, 15, 30, 45]

    def test_parse_range(self):
        result = parse_cron("0 9-17 * * *")
        assert result["hour"] == list(range(9, 18))

    def test_parse_range_step(self):
        result = parse_cron("1-5/2 * * * *")
        assert result["minute"] == [1, 3, 5]

    def test_parse_specific(self):
        result = parse_cron("0 9 * * 1-5")
        assert result["minute"] == [0]
        assert result["hour"] == [9]
        assert result["day_of_week"] == [1, 2, 3, 4, 5]

    def test_parse_invalid(self):
        import pytest
        with pytest.raises(ValueError, match="5 fields"):
            parse_cron("* * *")


class TestNextRun:
    def test_next_run_within_minute(self):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        nxt = next_run("* * * * *", after=now)
        assert (nxt - now).total_seconds() < 60

    def test_next_run_on_minute_boundary(self):
        from datetime import datetime, timezone
        nxt = next_run("30 * * * *")
        assert nxt.minute == 30


class TestScheduledJobModel:
    def test_create_job(self):
        job = ScheduledResearchJob.create("Test prompt", "0 9 * * 1-5")
        assert job.id.startswith("job_")
        assert job.prompt == "Test prompt"
        assert job.status == "PENDING"

    def test_roundtrip(self):
        job = ScheduledResearchJob.create("Test", "* * * * *")
        d = job.to_dict()
        restored = ScheduledResearchJob.from_dict(d)
        assert restored.id == job.id
        assert restored.prompt == "Test"


class TestScheduledJobStore:
    def test_save_and_get(self):
        tmp = Path(tempfile.mkdtemp())
        store = ScheduledResearchJobStore(tmp / "jobs.json")
        job = ScheduledResearchJob.create("Test", "0 * * * *")
        store.save(job)
        loaded = store.get(job.id)
        assert loaded is not None
        assert loaded.prompt == "Test"

    def test_list_all(self):
        tmp = Path(tempfile.mkdtemp())
        store = ScheduledResearchJobStore(tmp / "jobs.json")
        store.save(ScheduledResearchJob.create("A", "* * * * *"))
        store.save(ScheduledResearchJob.create("B", "* * * * *"))
        assert store.count() == 2

    def test_delete(self):
        tmp = Path(tempfile.mkdtemp())
        store = ScheduledResearchJobStore(tmp / "jobs.json")
        job = ScheduledResearchJob.create("Test", "* * * * *")
        store.save(job)
        assert store.delete(job.id) is True
        assert store.delete("nonexistent") is False

    def test_recover_stale(self):
        tmp = Path(tempfile.mkdtemp())
        store = ScheduledResearchJobStore(tmp / "jobs.json")
        job = ScheduledResearchJob.create("Test", "* * * * *")
        job.status = "RUNNING"
        store.save(job)
        assert store.recover_stale_running() == 1
        loaded = store.get(job.id)
        assert loaded is not None
        assert loaded.status == "PENDING"


class TestScheduledExecutor:
    def test_recover_stale(self):
        tmp = Path(tempfile.mkdtemp())
        store = ScheduledResearchJobStore(tmp / "jobs.json")
        job = ScheduledResearchJob.create("Test", "* * * * *")
        job.status = "RUNNING"
        store.save(job)
        executor = ScheduledResearchExecutor(store)
        assert executor.recover_stale() == 1

    def test_tick_finds_due_jobs(self):
        tmp = Path(tempfile.mkdtemp())
        store = ScheduledResearchJobStore(tmp / "jobs.json")
        from datetime import datetime, timezone
        past = datetime.now(timezone.utc).isoformat()
        job = ScheduledResearchJob.create("Test", "* * * * *")
        job.next_run_at = past
        store.save(job)
        executor = ScheduledResearchExecutor(store)
        due = executor.tick()
        assert len(due) == 1
        assert due[0].id == job.id

    @pytest.mark.asyncio
    async def test_dispatch_runs_job(self):
        from unittest.mock import AsyncMock
        tmp = Path(tempfile.mkdtemp())
        store = ScheduledResearchJobStore(tmp / "jobs.json")
        job = ScheduledResearchJob.create("Test", "0 9 * * *", interval_ms=3600000)
        store.save(job)
        executor = ScheduledResearchExecutor(store)
        executor._service = AsyncMock()
        result = await executor.dispatch(job)
        assert result["success"] is True
        executor._service.run_research.assert_called_once()
        loaded = store.get(job.id)
        assert loaded is not None
        assert loaded.run_count == 1

    def test_lazy_service_initialization(self):
        tmp = Path(tempfile.mkdtemp())
        store = ScheduledResearchJobStore(tmp / "jobs.json")
        executor = ScheduledResearchExecutor(store)
        assert executor._service is None
        from vinu_research.service import ResearchService
        assert isinstance(executor.service, ResearchService)
        assert executor._service is not None
