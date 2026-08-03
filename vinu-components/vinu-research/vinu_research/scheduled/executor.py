from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, TYPE_CHECKING

from vinu_lib.debug import debug_log
from vinu_research.models import ArtifactStatus
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
            run_response = await self.service.run_research(
                user_idea=user_idea,
                symbol=symbol,
                from_date=from_date,
                to_date=to_date,
            )
            job.last_run_id = run_response.get("id")
            job.last_summary = run_response.get("summary_text", "")

            job.status = "PENDING"
            if job.interval_ms > 0:
                next_time = datetime.now(timezone.utc) + timedelta(milliseconds=job.interval_ms)
                job.next_run_at = next_time.isoformat()
            elif job.schedule:
                job.next_run_at = next_run(job.schedule).isoformat()
            job.last_error = ""
            result = {"success": True, "job_id": job.id, "run_id": job.last_run_id, "summary_text": job.last_summary}
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

    async def decay_scan(self) -> int:
        decayed_count = 0
        debug_log("decay_scan: starting", level=1)
        try:
            artifacts = await asyncio.to_thread(
                self.service.strategy_store.list_artifacts_by_statuses,
                [ArtifactStatus.ACTIVE, ArtifactStatus.MONITORING],
            )
            debug_log(f"decay_scan: found {len(artifacts)} ACTIVE/MONITORING artifacts", level=1)
            for art in artifacts:
                if not art.universe or not art.strategy_code:
                    continue
                LOG.info("Decay scan: checking %s (%s)", art.artifact_id, art.status.value)
                snapshot = await asyncio.to_thread(self.service.strategy_store.get_latest_snapshot, art.artifact_id)
                if snapshot is not None and art.initial_sharpe > 0:
                    ratio = snapshot.rolling_sharpe / art.initial_sharpe if art.initial_sharpe else 0
                    if ratio < 0.5:
                        LOG.warning("Decay detected for %s: sharpe=%.2f vs initial=%.2f", art.artifact_id, snapshot.rolling_sharpe, art.initial_sharpe)
                        debug_log(f"decay_scan: decayed {art.artifact_id} ratio={ratio:.2f}", level=1)
                        result = await self.service.refresh_strategy(art.artifact_id, datetime.now(timezone.utc).strftime("%Y-%m-%d"))
                        if result.get("full_research"):
                            LOG.info("Strategy %s marked as DECAYED, full re-research queued", art.artifact_id)
                        debug_log(f"decay_scan: refresh {art.artifact_id} result={result}", level=1)
                        decayed_count += 1
        except Exception as e:
            LOG.error("Decay scan failed: %s", e)
        return decayed_count

    async def revalidation_scan(self) -> int:
        """Re-validate ACTIVE/MONITORING artifacts whose `last_validated_ts` is
        older than the configured interval. Returns count of re-validated artifacts."""
        revalidated_count = 0
        debug_log("revalidation_scan: starting", level=1)
        try:
            interval_days = self.service.config.revalidation_interval_days
            if interval_days <= 0:
                return 0
            artifacts = await asyncio.to_thread(
                self.service.strategy_store.list_stale_artifacts,
                days=interval_days,
            )
            debug_log(f"revalidation_scan: found {len(artifacts)} stale artifacts", level=1)
            for art in artifacts:
                if not art.strategy_code:
                    continue
                try:
                    result = await self.service.revalidate_artifact(art.artifact_id)
                    if result.get("revalidated"):
                        revalidated_count += 1
                        status = "passed" if result.get("validation_passed") else "failed"
                        LOG.info(
                            "Re-validation %s for %s (%s): sharpe=%.2f",
                            status, art.artifact_id, art.name, result.get("sharpe", 0),
                        )
                except Exception as e:
                    LOG.error("Re-validation failed for %s: %s", art.artifact_id, e)
        except Exception as e:
            LOG.error("Revalidation scan failed: %s", e)
        return revalidated_count

    async def regime_recompute_scan(self) -> int:
        """Freshness Contract's recompute trigger for the regime/correlation
        angle (04-agentic-still-refinement's either/or with
        vinu-initial-analysis — hosted here since it's the cheaper option:
        no new executor, just one more scan on this loop's existing
        cadence). For each symbol with an ACTIVE/MONITORING strategy artifact
        (same universe-discovery pattern as decay_scan/revalidation_scan),
        POSTs to vinu-initial-analysis's own recompute route — a
        cross-service HTTP call, not a local import, since these are
        separate services in this stack. Returns count of symbols recomputed."""
        recomputed_count = 0
        debug_log("regime_recompute_scan: starting", level=1)
        try:
            if self.service.config.regime_recompute_interval_days <= 0:
                return 0
            artifacts = await asyncio.to_thread(
                self.service.strategy_store.list_artifacts_by_statuses,
                [ArtifactStatus.ACTIVE, ArtifactStatus.MONITORING],
            )
            symbols = sorted({s for art in artifacts for s in (art.universe or [])})
            debug_log(f"regime_recompute_scan: {len(symbols)} symbols from ACTIVE/MONITORING artifacts", level=1)

            import httpx

            base_url = self.service.config.correlation_api_url
            async with httpx.AsyncClient(timeout=60.0) as client:
                for symbol in symbols:
                    try:
                        resp = await client.post(
                            f"{base_url}/analysis/run/{symbol}",
                            params={"angle_names": "regime_analysis"},
                        )
                        if resp.status_code == 200:
                            recomputed_count += 1
                        else:
                            LOG.warning(
                                "regime_recompute_scan: %s returned %s", symbol, resp.status_code,
                            )
                    except Exception as e:
                        LOG.warning("regime_recompute_scan: failed for %s: %s", symbol, e)
        except Exception as e:
            LOG.error("Regime recompute scan failed: %s", e)
        return recomputed_count

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
        decay_interval = 3600.0  # once per hour
        revalidation_interval = 3600.0  # once per hour
        regime_recompute_interval = 86400.0  # once per day — regime moves slower than Sharpe
        last_decay_scan = 0.0
        last_revalidation_scan = 0.0
        last_regime_recompute_scan = 0.0
        startup = True
        while self._running:
            try:
                due = self.tick()
                for job in due:
                    await self.dispatch(job)
            except Exception as exc:
                LOG.error("Scheduled executor tick failed: %s", exc)
            if startup:
                now = asyncio.get_event_loop().time()
                last_decay_scan = now
                last_revalidation_scan = now
                last_regime_recompute_scan = now
                startup = False
            await asyncio.sleep(self._poll_interval)
            now = asyncio.get_event_loop().time()
            if now - last_decay_scan >= decay_interval:
                n = await self.decay_scan()
                if n:
                    LOG.info("Decay scan completed: %d strategies decayed", n)
                last_decay_scan = now
            if now - last_revalidation_scan >= revalidation_interval:
                n = await self.revalidation_scan()
                if n:
                    LOG.info("Revalidation scan completed: %d artifacts re-validated", n)
                last_revalidation_scan = now
            if now - last_regime_recompute_scan >= regime_recompute_interval:
                n = await self.regime_recompute_scan()
                if n:
                    LOG.info("Regime recompute scan completed: %d symbols recomputed", n)
                last_regime_recompute_scan = now

    @property
    def is_running(self) -> bool:
        return self._running
