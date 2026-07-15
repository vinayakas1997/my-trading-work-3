from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, TYPE_CHECKING

from vinu_research.scheduled.cron import next_run
from vinu_research.scheduled.models import ScheduledResearchJob
from vinu_research.scheduled.store import ScheduledResearchJobStore

if TYPE_CHECKING:
    from vinu_research.service import ResearchService

LOG = logging.getLogger(__name__)


class ScheduledResearchExecutor:
    def __init__(
        self,
        store: ScheduledResearchJobStore | None = None,
        poll_interval_sec: float = 60.0,
        service: ResearchService | None = None,
    ) -> None:
        self._store = store or ScheduledResearchJobStore()
        self._poll_interval = poll_interval_sec
        self._service = service
        self._running = False
        self._task: asyncio.Task[Any] | None = None

    @property
    def service(self) -> ResearchService:
        if self._service is None:
            from vinu_research.service import ResearchService
            self._service = ResearchService()
        return self._service

    def recover_stale(self) -> int:
        return self._store.recover_stale_running()

    def tick(self) -> list[ScheduledResearchJob]:
        now = datetime.now(timezone.utc)
        due: list[ScheduledResearchJob] = []
        for job in self._store.list_all():
            if job.status != "PENDING":
                continue
            if not job.next_run_at:
                continue
            try:
                next_dt = datetime.fromisoformat(job.next_run_at)
                if next_dt <= now:
                    due.append(job)
            except ValueError:
                continue
        return due

    async def dispatch(self, job: ScheduledResearchJob) -> dict[str, Any]:
        job.status = "RUNNING"
        self._store.save(job)
        try:
            LOG.info("Dispatching scheduled job: %s", job.id)
            job.run_count += 1
            
            # Setup inputs for research service
            symbol = self.service.config.benchmark_symbol or "SPY"
            from_date = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")
            to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            user_idea = job.prompt
            
            try:
                data = json.loads(job.prompt)
                if isinstance(data, dict):
                    user_idea = data.get("user_idea", job.prompt)
                    symbol = data.get("symbol", symbol)
                    from_date = data.get("from_date", from_date)
                    to_date = data.get("to_date", to_date)
            except Exception:
                pass

            # Run actual research loop
            await self.service.run_research(
                user_idea=user_idea,
                symbol=symbol,
                from_date=from_date,
                to_date=to_date,
            )

            job.status = "PENDING"
            if job.interval_ms > 0:
                next_time = datetime.now(timezone.utc) + timedelta(milliseconds=job.interval_ms)
                job.next_run_at = next_time.isoformat()
            elif job.schedule:
                job.next_run_at = next_run(job.schedule).isoformat()
            job.last_error = ""
            result = {"success": True, "job_id": job.id}
        except Exception as exc:
            LOG.error("Job %s failed: %s", job.id, exc, exc_info=True)
            job.status = "PENDING"
            job.last_error = str(exc)
            result = {"success": False, "job_id": job.id, "error": str(exc)}
            
            # Re-schedule even if failed to prevent blocking next runs
            if job.interval_ms > 0:
                next_time = datetime.now(timezone.utc) + timedelta(milliseconds=job.interval_ms)
                job.next_run_at = next_time.isoformat()
            elif job.schedule:
                job.next_run_at = next_run(job.schedule).isoformat()

        job.updated_at = datetime.now(timezone.utc).isoformat()
        self._store.save(job)
        return result

    async def start(self) -> None:
        self._running = True
        recovered = self.recover_stale()
        if recovered:
            LOG.info("Recovered %d stale RUNNING jobs", recovered)
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self) -> None:
        while self._running:
            try:
                due = self.tick()
                for job in due:
                    await self.dispatch(job)
            except Exception as exc:
                LOG.error("Scheduled executor tick failed: %s", exc)
            await asyncio.sleep(self._poll_interval)

    @property
    def is_running(self) -> bool:
        return self._running
