from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, TYPE_CHECKING

from vinu_infra.debug import debug_log
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

    async def trade_score_calibration_scan(self) -> int:
        """Self-calibrating TradeScore weights (high-expectations
        follow-up): unlike decay_scan/revalidation_scan, this isn't
        per-artifact -- there is one global TradeScoreThresholds shared by
        every trade plan, so this computes one calibration metric set and
        (depending on mode) one proposal/application, not a loop.

        VINU_RESEARCH_TRADE_SCORE_CALIBRATION_MODE, same off|propose|auto
        convention as VINU_RESEARCH_DECAY_RESPONSE_MODE:
          off     -- (default) doesn't even run. This is a newer, higher-
                     blast-radius mechanism than decay's already-proven
                     state machine (it can change scoring for every future
                     trade at once) -- ships dormant, same posture as the
                     OOD detector and thesis-recheck.
          propose -- computes metrics + a candidate calibration and records
                     it (trade_score_calibration.save_proposal), requiring
                     a human to call trade_score_calibration.approve_proposal
                     (or the /research/trade-score-calibration/approve
                     route) before it takes effect.
          auto    -- applies the new calibration directly
                     (trade_score_calibration.apply_directly).

        Below config.trade_score_calibration_min_sample closed trades (or
        no actionable signal -- see propose_calibrated_thresholds' own
        docstring), this is a no-op regardless of mode: fitting weights
        against too little data, or against a signal that says nothing
        should change, is worse than leaving the current weights alone.
        Returns 1 if a proposal/application happened, else 0.
        """
        import os as _os

        from vinu_research.trade_score_calibration import (
            compute_calibration_metrics, load_active_thresholds, propose_calibrated_thresholds,
            read_history, save_proposal,
        )

        mode = _os.environ.get("VINU_RESEARCH_TRADE_SCORE_CALIBRATION_MODE", "off").lower()
        if mode == "off":
            return 0

        debug_log(f"trade_score_calibration_scan: starting (mode={mode})", level=1)
        try:
            history = await asyncio.to_thread(read_history)
            metrics = compute_calibration_metrics(
                history, min_sample=self.service.config.trade_score_calibration_min_sample,
            )
            if metrics.get("status") != "ok":
                debug_log(f"trade_score_calibration_scan: {metrics.get('status')}", level=1)
                return 0

            current = load_active_thresholds()
            proposal = propose_calibrated_thresholds(
                current, metrics, bound=self.service.config.trade_score_calibration_bound,
            )
            if proposal is None:
                debug_log("trade_score_calibration_scan: no actionable signal", level=1)
                return 0

            if mode == "propose":
                await asyncio.to_thread(save_proposal, proposal, metrics)
                LOG.warning(
                    "TradeScore calibration PROPOSED from %d closed trades (awaiting "
                    "trade_score_calibration.approve_proposal)", metrics["n_entries"],
                )
                return 1

            # auto
            from vinu_research.trade_score_calibration import apply_directly
            await asyncio.to_thread(apply_directly, proposal, metrics)
            LOG.warning(
                "TradeScore calibration applied from %d closed trades", metrics["n_entries"],
            )
            return 1
        except Exception as e:
            LOG.error("TradeScore calibration scan failed: %s", e)
            return 0

    async def decay_scan(self) -> int:
        """High-expectations spec #8: this used to be a second, disconnected
        decay-decision path -- an ad-hoc rolling-Sharpe-ratio/staleness
        check that never called decay.py's real transition_status()/
        evaluate_health() state machine at all (that state machine WAS
        already used, just only by cli.py's manual `decay-scan` command,
        never by this automated hourly one). This now uses the same real
        state machine cli.py's `_run_decay_scan` does, and adds a graduated
        manual/auto knob (VINU_RESEARCH_DECAY_RESPONSE_MODE, matching the
        VINU_LIVE_OOD_DETECTOR=off|alert|halt|flatten convention) over how
        a detected transition gets acted on:
          off     -- detection doesn't even run.
          propose -- detect + record (record_proposed_decay_action), but
                     require a human to call decay.approve_decay_action()
                     before the artifact's status or re-research actually
                     changes.
          auto    -- (default, replicates this method's pre-existing
                     always-on behavior) apply the transition and trigger
                     re-research on DECAYED, same as today.
        Returns the number of artifacts actually acted on (in `propose`
        mode, a recorded-but-unconfirmed proposal doesn't count).
        """
        import os as _os

        from vinu_research.config import DecayThresholds
        from vinu_research.decay import (
            compute_decay_snapshot, compute_strategy_decay_snapshot, transition_status,
        )

        mode = _os.environ.get("VINU_RESEARCH_DECAY_RESPONSE_MODE", "auto").lower()
        if mode == "off":
            return 0

        thresholds = DecayThresholds()
        acted_count = 0
        debug_log(f"decay_scan: starting (mode={mode})", level=1)
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

                history = await asyncio.to_thread(self.service.strategy_store.get_bench_history, art.artifact_id)
                if len(history) < 2:
                    continue

                if art.type == "strategy":
                    snapshot = compute_strategy_decay_snapshot(art.artifact_id, history, thresholds)
                else:
                    snapshot = compute_decay_snapshot(art.artifact_id, history, thresholds)

                # get_snapshots() returns newest-first; transition_status
                # needs oldest-to-newest with the just-computed snapshot
                # last, or _n_consecutive's "last N" check reads the wrong
                # end of the history -- same ordering cli.py's manual
                # decay-scan command already gets right.
                previous_snapshots = await asyncio.to_thread(
                    self.service.strategy_store.get_snapshots, art.artifact_id,
                )
                eval_history = [s.evaluation for s in reversed(previous_snapshots)] + [snapshot.evaluation]
                new_status = transition_status(art.status, eval_history)

                await asyncio.to_thread(self.service.strategy_store.save_snapshot, snapshot)

                if new_status == art.status:
                    continue

                if mode == "propose":
                    await asyncio.to_thread(
                        self.service.strategy_store.record_proposed_decay_action,
                        art.artifact_id, art.status.value, new_status.value,
                    )
                    LOG.warning(
                        "Decay response PROPOSED for %s: %s -> %s (awaiting decay.approve_decay_action)",
                        art.artifact_id, art.status.value, new_status.value,
                    )
                    debug_log(f"decay_scan: proposed {art.artifact_id} -> {new_status.value}", level=1)
                    continue

                # auto
                await asyncio.to_thread(
                    self.service.strategy_store.transition_status, art.artifact_id, new_status,
                )
                LOG.warning(
                    "Decay transition for %s: %s -> %s", art.artifact_id, art.status.value, new_status.value,
                )
                if new_status == ArtifactStatus.DECAYED:
                    result = await self.service.refresh_strategy(art.artifact_id, datetime.now(timezone.utc).strftime("%Y-%m-%d"))
                    if result.get("full_research"):
                        LOG.info("Strategy %s marked as DECAYED, full re-research queued", art.artifact_id)
                    debug_log(f"decay_scan: refresh {art.artifact_id} result={result}", level=1)
                acted_count += 1
        except Exception as e:
            LOG.error("Decay scan failed: %s", e)
        return acted_count

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
            try:
                from vinu_infra.auth import internal_auth_headers
                _headers = internal_auth_headers() or None
            except Exception:
                _headers = None
            async with httpx.AsyncClient(timeout=60.0, headers=_headers) as client:
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
        # TradeScore calibration moves slower still -- it needs a real
        # accumulation of closed trades (min_sample, default 30) to say
        # anything at all, so a daily cadence (like regime recompute) is
        # already far more frequent than the underlying data can justify.
        trade_score_calibration_interval = 86400.0  # once per day
        last_decay_scan = 0.0
        last_revalidation_scan = 0.0
        last_regime_recompute_scan = 0.0
        last_trade_score_calibration_scan = 0.0
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
                last_trade_score_calibration_scan = now
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
            if now - last_trade_score_calibration_scan >= trade_score_calibration_interval:
                n = await self.trade_score_calibration_scan()
                if n:
                    LOG.info("TradeScore calibration scan completed: %d proposal/application(s)", n)
                last_trade_score_calibration_scan = now

    @property
    def is_running(self) -> bool:
        return self._running
