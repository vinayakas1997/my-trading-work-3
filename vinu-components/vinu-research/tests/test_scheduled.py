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

    @pytest.mark.asyncio
    async def test_dispatch_persists_run_id_and_summary_onto_job(self):
        """Regression test: dispatch() used to call run_research() and throw
        away its entire return value — a scheduled run's report_md/summary
        was unrecoverable without separately guessing which /research/runs
        row it produced."""
        from unittest.mock import AsyncMock
        tmp = Path(tempfile.mkdtemp())
        store = ScheduledResearchJobStore(tmp / "jobs.json")
        job = ScheduledResearchJob.create("Test", "0 9 * * *", interval_ms=3600000)
        store.save(job)
        executor = ScheduledResearchExecutor(store)
        executor._service = AsyncMock()
        executor._service.run_research.return_value = {
            "id": 42, "summary_text": "Tried momentum, Sharpe 1.4, promoted.",
        }
        result = await executor.dispatch(job)
        assert result["run_id"] == 42
        assert result["summary_text"] == "Tried momentum, Sharpe 1.4, promoted."

        loaded = store.get(job.id)
        assert loaded.last_run_id == 42
        assert loaded.last_summary == "Tried momentum, Sharpe 1.4, promoted."

    def test_lazy_service_initialization(self):
        tmp = Path(tempfile.mkdtemp())
        store = ScheduledResearchJobStore(tmp / "jobs.json")
        executor = ScheduledResearchExecutor(store)
        assert executor._service is None
        from vinu_research.service import ResearchService
        assert isinstance(executor.service, ResearchService)
        assert executor._service is not None

    @pytest.mark.asyncio
    async def test_revalidation_scan_disabled_when_interval_zero(self):
        tmp = Path(tempfile.mkdtemp())
        store = ScheduledResearchJobStore(tmp / "jobs.json")
        from unittest.mock import AsyncMock, MagicMock
        executor = ScheduledResearchExecutor(store)
        mock_svc = AsyncMock()
        mock_svc.config.revalidation_interval_days = 0
        executor._service = mock_svc
        count = await executor.revalidation_scan()
        assert count == 0
        mock_svc.strategy_store.list_stale_artifacts.assert_not_called()

    @pytest.mark.asyncio
    async def test_revalidation_scan_handles_exception_gracefully(self):
        tmp = Path(tempfile.mkdtemp())
        store = ScheduledResearchJobStore(tmp / "jobs.json")
        from unittest.mock import AsyncMock, MagicMock
        executor = ScheduledResearchExecutor(store)
        mock_svc = AsyncMock()
        mock_svc.config.revalidation_interval_days = 30
        mock_svc.strategy_store.list_stale_artifacts.side_effect = Exception("DB error")
        executor._service = mock_svc
        count = await executor.revalidation_scan()
        assert count == 0

    @pytest.mark.asyncio
    async def test_regime_recompute_scan_disabled_when_interval_zero(self):
        tmp = Path(tempfile.mkdtemp())
        store = ScheduledResearchJobStore(tmp / "jobs.json")
        from unittest.mock import AsyncMock
        executor = ScheduledResearchExecutor(store)
        mock_svc = AsyncMock()
        mock_svc.config.regime_recompute_interval_days = 0
        executor._service = mock_svc
        count = await executor.regime_recompute_scan()
        assert count == 0
        mock_svc.strategy_store.list_artifacts_by_statuses.assert_not_called()

    @pytest.mark.asyncio
    async def test_regime_recompute_scan_posts_for_each_universe_symbol(self):
        tmp = Path(tempfile.mkdtemp())
        store = ScheduledResearchJobStore(tmp / "jobs.json")
        from unittest.mock import AsyncMock, MagicMock, patch

        art1 = MagicMock(universe=["AAPL", "MSFT"])
        art2 = MagicMock(universe=["MSFT"])

        executor = ScheduledResearchExecutor(store)
        mock_svc = MagicMock()
        mock_svc.config.regime_recompute_interval_days = 1
        mock_svc.config.correlation_api_url = "http://initial-analysis:8083"
        mock_svc.strategy_store.list_artifacts_by_statuses = MagicMock(return_value=[art1, art2])
        executor._service = mock_svc

        ok_resp = MagicMock(status_code=200)

        class _FakeAsyncClient:
            calls: list[tuple[str, dict]] = []

            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, params=None, **kw):
                _FakeAsyncClient.calls.append((url, params or {}))
                return ok_resp

        _FakeAsyncClient.calls = []
        with patch("httpx.AsyncClient", _FakeAsyncClient):
            count = await executor.regime_recompute_scan()

        assert count == 2  # deduped universe: AAPL, MSFT
        urls = sorted(url for url, _ in _FakeAsyncClient.calls)
        assert urls == [
            "http://initial-analysis:8083/analysis/run/AAPL",
            "http://initial-analysis:8083/analysis/run/MSFT",
        ]
        for _, params in _FakeAsyncClient.calls:
            assert params == {"angle_names": "regime_analysis"}

    @pytest.mark.asyncio
    async def test_regime_recompute_scan_handles_exception_gracefully(self):
        tmp = Path(tempfile.mkdtemp())
        store = ScheduledResearchJobStore(tmp / "jobs.json")
        from unittest.mock import MagicMock
        executor = ScheduledResearchExecutor(store)
        mock_svc = MagicMock()
        mock_svc.config.regime_recompute_interval_days = 1
        mock_svc.strategy_store.list_artifacts_by_statuses.side_effect = Exception("DB error")
        executor._service = mock_svc
        count = await executor.regime_recompute_scan()
        assert count == 0

    @pytest.mark.asyncio
    async def test_regime_recompute_scan_counts_only_successful_posts(self):
        tmp = Path(tempfile.mkdtemp())
        store = ScheduledResearchJobStore(tmp / "jobs.json")
        from unittest.mock import MagicMock, patch

        art = MagicMock(universe=["AAPL", "TSLA"])
        executor = ScheduledResearchExecutor(store)
        mock_svc = MagicMock()
        mock_svc.config.regime_recompute_interval_days = 1
        mock_svc.config.correlation_api_url = "http://initial-analysis:8083"
        mock_svc.strategy_store.list_artifacts_by_statuses = MagicMock(return_value=[art])
        executor._service = mock_svc

        class _FlakyAsyncClient:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, params=None, **kw):
                if "AAPL" in url:
                    return MagicMock(status_code=200)
                return MagicMock(status_code=500)

        with patch("httpx.AsyncClient", _FlakyAsyncClient):
            count = await executor.regime_recompute_scan()

        assert count == 1
