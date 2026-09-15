from __future__ import annotations

import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from vinu_research.models import Artifact, ArtifactStatus, BenchEntry
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

    def test_lazy_service_initialization(self, monkeypatch):
        """`executor.service`'s lazy-init path constructs a real
        `ResearchService()` with zero args, which resolves its data_root via
        `load_config()` -> `VINU_RESEARCH_DATA_ROOT` (config.py) falling back
        to `Path.cwd() / "data"` -- a dataclass default evaluated once at
        import time, so it reflects whatever cwd was when vinu_research.
        config was first imported in this test session, not this test's own
        cwd. Environment-dependent (observed resolving to the
        non-writable "/data" outside a container that mounts it), so the
        env var is pinned here rather than left to ambient cwd state."""
        tmp = Path(tempfile.mkdtemp())
        monkeypatch.setenv("VINU_RESEARCH_DATA_ROOT", str(tmp))
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


class TestDecayScanResponseMode:
    """Phase 6: decay_scan() used to run its own disconnected ratio/
    staleness heuristic that never called decay.py's real transition_status()
    state machine -- cli.py's manual `decay-scan` command was the only
    caller of that state machine. decay_scan() now uses the same real state
    machine, gated by a graduated VINU_RESEARCH_DECAY_RESPONSE_MODE knob
    (off/propose/auto, matching VINU_LIVE_OOD_DETECTOR's convention)."""

    def _executor_with_mock_service(self):
        from unittest.mock import AsyncMock, MagicMock

        tmp = Path(tempfile.mkdtemp())
        store = ScheduledResearchJobStore(tmp / "jobs.json")
        executor = ScheduledResearchExecutor(store)
        mock_svc = MagicMock()
        mock_svc.refresh_strategy = AsyncMock(return_value={})
        executor._service = mock_svc
        return executor, mock_svc

    def _artifact(self, status: ArtifactStatus) -> Artifact:
        art = Artifact.create("strategy", "Test", universe=["AAPL"])
        art.status = status
        art.strategy_code = "class UserStrategy: pass"
        return art

    def _history(self) -> list[BenchEntry]:
        return [
            BenchEntry(artifact_id="x", date="2024-01-01", sharpe=0.2),
            BenchEntry(artifact_id="x", date="2024-01-02", sharpe=0.1),
        ]

    @pytest.mark.asyncio
    async def test_off_mode_never_touches_the_store(self, monkeypatch):
        from unittest.mock import MagicMock

        monkeypatch.setenv("VINU_RESEARCH_DECAY_RESPONSE_MODE", "off")
        executor, mock_svc = self._executor_with_mock_service()
        mock_svc.strategy_store.list_artifacts_by_statuses = MagicMock(return_value=[])

        count = await executor.decay_scan()

        assert count == 0
        mock_svc.strategy_store.list_artifacts_by_statuses.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_mode_applies_transition_and_triggers_refresh_on_decayed(self, monkeypatch):
        from unittest.mock import MagicMock

        import vinu_research.decay as decay_module

        monkeypatch.setenv("VINU_RESEARCH_DECAY_RESPONSE_MODE", "auto")
        monkeypatch.setattr(decay_module, "transition_status", lambda *a, **k: ArtifactStatus.DECAYED)

        executor, mock_svc = self._executor_with_mock_service()
        art = self._artifact(ArtifactStatus.MONITORING)
        mock_svc.strategy_store.list_artifacts_by_statuses = MagicMock(return_value=[art])
        mock_svc.strategy_store.get_bench_history = MagicMock(return_value=self._history())
        mock_svc.strategy_store.get_snapshots = MagicMock(return_value=[])
        mock_svc.strategy_store.save_snapshot = MagicMock()
        mock_svc.strategy_store.transition_status = MagicMock()
        mock_svc.refresh_strategy.return_value = {"full_research": True}

        count = await executor.decay_scan()

        assert count == 1
        mock_svc.strategy_store.transition_status.assert_called_once_with(
            art.artifact_id, ArtifactStatus.DECAYED,
        )
        mock_svc.refresh_strategy.assert_awaited_once()
        mock_svc.strategy_store.record_proposed_decay_action.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_mode_no_op_when_status_unchanged(self, monkeypatch):
        from unittest.mock import MagicMock

        import vinu_research.decay as decay_module

        monkeypatch.setenv("VINU_RESEARCH_DECAY_RESPONSE_MODE", "auto")
        monkeypatch.setattr(decay_module, "transition_status", lambda current, *a, **k: current)

        executor, mock_svc = self._executor_with_mock_service()
        art = self._artifact(ArtifactStatus.ACTIVE)
        mock_svc.strategy_store.list_artifacts_by_statuses = MagicMock(return_value=[art])
        mock_svc.strategy_store.get_bench_history = MagicMock(return_value=self._history())
        mock_svc.strategy_store.get_snapshots = MagicMock(return_value=[])
        mock_svc.strategy_store.save_snapshot = MagicMock()
        mock_svc.strategy_store.transition_status = MagicMock()

        count = await executor.decay_scan()

        assert count == 0
        mock_svc.strategy_store.transition_status.assert_not_called()
        mock_svc.refresh_strategy.assert_not_called()

    @pytest.mark.asyncio
    async def test_propose_mode_records_proposal_without_mutating_status(self, monkeypatch):
        from unittest.mock import MagicMock

        import vinu_research.decay as decay_module

        monkeypatch.setenv("VINU_RESEARCH_DECAY_RESPONSE_MODE", "propose")
        monkeypatch.setattr(decay_module, "transition_status", lambda *a, **k: ArtifactStatus.DECAYED)

        executor, mock_svc = self._executor_with_mock_service()
        art = self._artifact(ArtifactStatus.MONITORING)
        mock_svc.strategy_store.list_artifacts_by_statuses = MagicMock(return_value=[art])
        mock_svc.strategy_store.get_bench_history = MagicMock(return_value=self._history())
        mock_svc.strategy_store.get_snapshots = MagicMock(return_value=[])
        mock_svc.strategy_store.save_snapshot = MagicMock()
        mock_svc.strategy_store.record_proposed_decay_action = MagicMock()
        mock_svc.strategy_store.transition_status = MagicMock()

        count = await executor.decay_scan()

        # A recorded-but-unconfirmed proposal isn't a counted action.
        assert count == 0
        mock_svc.strategy_store.record_proposed_decay_action.assert_called_once_with(
            art.artifact_id, "MONITORING", "DECAYED",
        )
        mock_svc.strategy_store.transition_status.assert_not_called()
        mock_svc.refresh_strategy.assert_not_called()

    @pytest.mark.asyncio
    async def test_default_mode_is_auto(self, monkeypatch):
        from unittest.mock import MagicMock

        import vinu_research.decay as decay_module

        monkeypatch.delenv("VINU_RESEARCH_DECAY_RESPONSE_MODE", raising=False)
        monkeypatch.setattr(decay_module, "transition_status", lambda *a, **k: ArtifactStatus.DECAYED)

        executor, mock_svc = self._executor_with_mock_service()
        art = self._artifact(ArtifactStatus.MONITORING)
        mock_svc.strategy_store.list_artifacts_by_statuses = MagicMock(return_value=[art])
        mock_svc.strategy_store.get_bench_history = MagicMock(return_value=self._history())
        mock_svc.strategy_store.get_snapshots = MagicMock(return_value=[])
        mock_svc.strategy_store.save_snapshot = MagicMock()
        mock_svc.strategy_store.transition_status = MagicMock()

        count = await executor.decay_scan()

        assert count == 1
        mock_svc.strategy_store.transition_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_artifacts_without_enough_bench_history(self, monkeypatch):
        from unittest.mock import MagicMock

        monkeypatch.setenv("VINU_RESEARCH_DECAY_RESPONSE_MODE", "auto")
        executor, mock_svc = self._executor_with_mock_service()
        art = self._artifact(ArtifactStatus.ACTIVE)
        mock_svc.strategy_store.list_artifacts_by_statuses = MagicMock(return_value=[art])
        mock_svc.strategy_store.get_bench_history = MagicMock(return_value=[])
        mock_svc.strategy_store.transition_status = MagicMock()

        count = await executor.decay_scan()

        assert count == 0
        mock_svc.strategy_store.transition_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_exception_is_caught_and_returns_zero(self, monkeypatch):
        from unittest.mock import MagicMock

        monkeypatch.setenv("VINU_RESEARCH_DECAY_RESPONSE_MODE", "auto")
        executor, mock_svc = self._executor_with_mock_service()
        mock_svc.strategy_store.list_artifacts_by_statuses = MagicMock(side_effect=Exception("DB down"))

        count = await executor.decay_scan()

        assert count == 0


class TestTradeScoreCalibrationScanResponseMode:
    """Self-calibrating TradeScore weights follow-up: same off/propose/auto
    convention as decay_scan, but a single global calibration (not
    per-artifact) -- ships dormant (default off) since this is newer and
    higher-blast-radius than decay's already-proven state machine."""

    def _executor_with_mock_service(self, min_sample=30, bound=0.2):
        from unittest.mock import MagicMock

        tmp = Path(tempfile.mkdtemp())
        store = ScheduledResearchJobStore(tmp / "jobs.json")
        executor = ScheduledResearchExecutor(store)
        mock_svc = MagicMock()
        mock_svc.config.trade_score_calibration_min_sample = min_sample
        mock_svc.config.trade_score_calibration_bound = bound
        executor._service = mock_svc
        return executor, mock_svc

    @staticmethod
    def _history_row(confluence, ev, risk, regime_fit, actual_return_pct):
        return {
            "confluence_score": confluence, "ev_score": ev, "risk_score": risk,
            "regime_fit_score": regime_fit, "actual_return_pct": actual_return_pct,
        }

    def _rich_history(self):
        # Strong positive signal on confluence_score, so a real proposal is
        # generated whenever the scan actually runs.
        return [
            self._history_row(i, 30 - i, 10.0, i % 3, i * 0.01) for i in range(30)
        ]

    @pytest.mark.asyncio
    async def test_off_mode_never_reads_history(self, monkeypatch):
        import vinu_research.trade_score_calibration as tsc

        monkeypatch.setenv("VINU_RESEARCH_TRADE_SCORE_CALIBRATION_MODE", "off")
        read_spy = MagicMock(return_value=[])
        monkeypatch.setattr(tsc, "read_history", read_spy)
        executor, _ = self._executor_with_mock_service()

        count = await executor.trade_score_calibration_scan()

        assert count == 0
        read_spy.assert_not_called()

    @pytest.mark.asyncio
    async def test_insufficient_sample_is_a_no_op(self, monkeypatch):
        import vinu_research.trade_score_calibration as tsc

        monkeypatch.setenv("VINU_RESEARCH_TRADE_SCORE_CALIBRATION_MODE", "auto")
        monkeypatch.setattr(tsc, "read_history", MagicMock(return_value=[self._history_row(1, 1, 1, 1, 0.01)]))
        apply_spy = MagicMock()
        monkeypatch.setattr(tsc, "apply_directly", apply_spy)
        executor, _ = self._executor_with_mock_service(min_sample=30)

        count = await executor.trade_score_calibration_scan()

        assert count == 0
        apply_spy.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_actionable_signal_is_a_no_op(self, monkeypatch):
        import vinu_research.trade_score_calibration as tsc

        monkeypatch.setenv("VINU_RESEARCH_TRADE_SCORE_CALIBRATION_MODE", "auto")
        # All identical scores -> zero-variance -> zero correlation -> no signal.
        flat_history = [self._history_row(20, 20, 20, 20, 0.01) for _ in range(30)]
        monkeypatch.setattr(tsc, "read_history", MagicMock(return_value=flat_history))
        apply_spy = MagicMock()
        monkeypatch.setattr(tsc, "apply_directly", apply_spy)
        executor, _ = self._executor_with_mock_service(min_sample=30)

        count = await executor.trade_score_calibration_scan()

        assert count == 0
        apply_spy.assert_not_called()

    @pytest.mark.asyncio
    async def test_propose_mode_records_without_applying(self, monkeypatch):
        import vinu_research.trade_score_calibration as tsc

        monkeypatch.setenv("VINU_RESEARCH_TRADE_SCORE_CALIBRATION_MODE", "propose")
        monkeypatch.setattr(tsc, "read_history", MagicMock(return_value=self._rich_history()))
        save_spy = MagicMock()
        apply_spy = MagicMock()
        monkeypatch.setattr(tsc, "save_proposal", save_spy)
        monkeypatch.setattr(tsc, "apply_directly", apply_spy)
        executor, _ = self._executor_with_mock_service()

        count = await executor.trade_score_calibration_scan()

        assert count == 1
        save_spy.assert_called_once()
        apply_spy.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_mode_applies_directly(self, monkeypatch):
        import vinu_research.trade_score_calibration as tsc

        monkeypatch.setenv("VINU_RESEARCH_TRADE_SCORE_CALIBRATION_MODE", "auto")
        monkeypatch.setattr(tsc, "read_history", MagicMock(return_value=self._rich_history()))
        save_spy = MagicMock()
        apply_spy = MagicMock()
        monkeypatch.setattr(tsc, "save_proposal", save_spy)
        monkeypatch.setattr(tsc, "apply_directly", apply_spy)
        executor, _ = self._executor_with_mock_service()

        count = await executor.trade_score_calibration_scan()

        assert count == 1
        apply_spy.assert_called_once()
        save_spy.assert_not_called()

    @pytest.mark.asyncio
    async def test_exception_is_caught_and_returns_zero(self, monkeypatch):
        import vinu_research.trade_score_calibration as tsc

        monkeypatch.setenv("VINU_RESEARCH_TRADE_SCORE_CALIBRATION_MODE", "auto")
        monkeypatch.setattr(tsc, "read_history", MagicMock(side_effect=Exception("disk error")))
        executor, _ = self._executor_with_mock_service()

        count = await executor.trade_score_calibration_scan()

        assert count == 0
