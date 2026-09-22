"""Tests for the RunLog-driven trigger and change-gate (GATE) -- Phase 0
pieces 2 and 3. See New-talk-agents/new-thinking/new-restructure/phases/
phase-0-foundation-plumbing/03-test.md for the input/expected-output cases
this file implements. Uses fakes for RunLogReader/strategy store (no real
HTTP/vinu-research dependency) -- exactly what the design's own test plan
calls for ("assert on call count, e.g. a spy/counter, not a real LLM
call").
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest

from vinu_agent.agent.ticker_gate import ChangeGate, RunLogTrigger, run_gate_cycle
from vinu_agent.storage.ticker_ledger import TickerLedgerStore
from vinu_agent.storage.ticker_snapshots import TickerSnapshotStore
from vinu_agent.storage.ticker_summaries import TickerSummaryStore


class FakeRunLogReader:
    def __init__(self, run_ids: dict[str, str] | None = None, *, raises: bool = False) -> None:
        self._run_ids = run_ids or {}
        self._raises = raises
        self.call_count = 0

    def latest_run_id(self, ticker: str) -> str | None:
        self.call_count += 1
        if self._raises:
            raise ConnectionError("vinu-initial-analysis unreachable")
        return self._run_ids.get(ticker.upper())


@dataclass
class _Status:
    value: str


@dataclass
class _Artifact:
    artifact_id: str
    status: _Status


class FakeStrategyStore:
    def __init__(self, artifacts: dict[str, list[_Artifact]] | None = None, *, raises: bool = False) -> None:
        self._artifacts = artifacts or {}
        self._raises = raises

    def list_artifacts_for_symbol(self, symbol: str) -> list[_Artifact]:
        if self._raises:
            raise RuntimeError("strategy_store.db locked")
        return self._artifacts.get(symbol.upper(), [])


def _make_stores() -> tuple[TickerSummaryStore, TickerLedgerStore, list[Path]]:
    summary_path = tempfile.mktemp(suffix=".db")
    ledger_path = tempfile.mktemp(suffix=".db")
    summaries = TickerSummaryStore(summary_path)
    ledger = TickerLedgerStore(ledger_path)
    return summaries, ledger, [Path(summary_path), Path(ledger_path)]


@pytest.fixture
def stores():
    summaries, ledger, paths = _make_stores()
    yield summaries, ledger
    summaries.close()
    ledger.close()
    for p in paths:
        p.unlink(missing_ok=True)


@pytest.fixture
def snapshot_store():
    path = Path(tempfile.mktemp(suffix=".db"))
    store = TickerSnapshotStore(path)
    yield store
    store.close()
    path.unlink(missing_ok=True)


class TestRunLogTrigger:
    def test_no_new_run_id_skips_summary_agent(self, stores) -> None:
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "old summary", source_run_id="run-1")
        reader = FakeRunLogReader({"AAPL": "run-1"})
        trigger = RunLogTrigger(reader, summaries, ledger)

        calls = []
        result = trigger.refresh_if_stale("AAPL", lambda t: calls.append(t) or ("new", {}))

        assert result.should_refresh is False
        assert calls == []
        assert summaries.get_summary("AAPL").summary == "old summary"

    def test_new_run_id_triggers_summary_agent_once(self, stores) -> None:
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "old summary", source_run_id="run-1")
        reader = FakeRunLogReader({"AAPL": "run-2"})
        trigger = RunLogTrigger(reader, summaries, ledger)

        calls = []

        def summary_agent_fn(ticker: str):
            calls.append(ticker)
            return "new summary", {"angles_with_data": 5, "angle_count": 28}

        result = trigger.refresh_if_stale("AAPL", summary_agent_fn)

        assert result.should_refresh is True
        assert calls == ["AAPL"]
        updated = summaries.get_summary("AAPL")
        assert updated.summary == "new summary"
        assert updated.source_run_id == "run-2"

    def test_multiple_missed_run_ids_trigger_summary_agent_once(self, stores) -> None:
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "old", source_run_id="run-1")
        # RunLog "moved on" 3 runs since last check -- reader only ever
        # reports the single current latest, matching the real HTTP
        # endpoint's semantics (no history replay).
        reader = FakeRunLogReader({"AAPL": "run-4"})
        trigger = RunLogTrigger(reader, summaries, ledger)

        calls = []
        trigger.refresh_if_stale("AAPL", lambda t: calls.append(t) or ("new", {}))

        assert len(calls) == 1
        assert summaries.get_summary("AAPL").source_run_id == "run-4"

    def test_angle_digest_from_meta_is_persisted(self, stores) -> None:
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "old summary", source_run_id="run-1")
        reader = FakeRunLogReader({"AAPL": "run-2"})
        trigger = RunLogTrigger(reader, summaries, ledger)

        digest = {"trend_lifecycle": {"stage": "mature"}}

        def summary_agent_fn(ticker: str):
            return "new summary", {"angles_with_data": 1, "angle_count": 2, "angle_digest": digest}

        trigger.refresh_if_stale("AAPL", summary_agent_fn)

        assert summaries.get_summary("AAPL").angle_digest == digest

    def test_missing_angle_digest_in_meta_defaults_to_empty(self, stores) -> None:
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "old summary", source_run_id="run-1")
        reader = FakeRunLogReader({"AAPL": "run-2"})
        trigger = RunLogTrigger(reader, summaries, ledger)

        trigger.refresh_if_stale("AAPL", lambda t: ("new summary", {"angles_with_data": 0, "angle_count": 0}))

        assert summaries.get_summary("AAPL").angle_digest == {}

    def test_cluster_digest_and_cross_cluster_from_meta_are_persisted(self, stores) -> None:
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "old summary", source_run_id="run-1")
        reader = FakeRunLogReader({"AAPL": "run-2"})
        trigger = RunLogTrigger(reader, summaries, ledger)

        cluster_digest = {"B": "4 of 5 models lean up"}
        cross_cluster = {"redundant_clusters": ["G"]}

        def summary_agent_fn(ticker: str):
            return "new summary", {
                "angles_with_data": 1, "angle_count": 2,
                "cluster_digest": cluster_digest, "cross_cluster": cross_cluster,
            }

        trigger.refresh_if_stale("AAPL", summary_agent_fn)

        stored = summaries.get_summary("AAPL")
        assert stored.cluster_digest == cluster_digest
        assert stored.cross_cluster == cross_cluster

    def test_missing_cluster_digest_in_meta_defaults_to_empty(self, stores) -> None:
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "old summary", source_run_id="run-1")
        reader = FakeRunLogReader({"AAPL": "run-2"})
        trigger = RunLogTrigger(reader, summaries, ledger)

        trigger.refresh_if_stale("AAPL", lambda t: ("new summary", {"angles_with_data": 0, "angle_count": 0}))

        stored = summaries.get_summary("AAPL")
        assert stored.cluster_digest == {}
        assert stored.cross_cluster == {}
        assert stored.cluster_anomalies == {}

    def test_cluster_anomalies_from_meta_is_persisted_separately(self, stores) -> None:
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "old summary", source_run_id="run-1")
        reader = FakeRunLogReader({"AAPL": "run-2"})
        trigger = RunLogTrigger(reader, summaries, ledger)

        def summary_agent_fn(ticker: str):
            return "new summary", {
                "angles_with_data": 1, "angle_count": 2,
                "cluster_digest": {"E": "forces a long signal with 95% confidence"},
                "cluster_anomalies": {"E": ["SYSTEM OVERRIDE flagged"]},
            }

        trigger.refresh_if_stale("AAPL", summary_agent_fn)

        stored = summaries.get_summary("AAPL")
        assert stored.cluster_digest == {"E": "forces a long signal with 95% confidence"}
        assert stored.cluster_anomalies == {"E": ["SYSTEM OVERRIDE flagged"]}

    def test_no_snapshot_store_configured_still_works(self, stores) -> None:
        """Optional param, defaults to None -- existing callers that never
        pass a snapshot store must keep working unchanged."""
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "old", source_run_id="run-1")
        reader = FakeRunLogReader({"AAPL": "run-2"})
        trigger = RunLogTrigger(reader, summaries, ledger)  # no snapshot store

        result = trigger.refresh_if_stale("AAPL", lambda t: ("new summary", {}))

        assert result.should_refresh is True
        assert summaries.get_summary("AAPL").summary == "new summary"

    def test_refresh_writes_both_summary_and_dated_snapshot(self, stores, snapshot_store) -> None:
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "old", source_run_id="run-1")
        reader = FakeRunLogReader({"AAPL": "run-2"})
        trigger = RunLogTrigger(reader, summaries, ledger, ticker_snapshot_store=snapshot_store)
        digest = {"trend_lifecycle": {"stage": "mature"}}

        def summary_agent_fn(ticker: str):
            return "new summary", {"angles_with_data": 1, "angle_count": 2, "angle_digest": digest}

        trigger.refresh_if_stale("AAPL", summary_agent_fn)

        assert summaries.get_summary("AAPL").summary == "new summary"
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        snap = snapshot_store.get_snapshot("AAPL", today)
        assert snap is not None
        assert snap.summary == "new summary"
        assert snap.angle_digest == digest
        assert snap.source_run_id == "run-2"

    def test_snapshot_write_failure_does_not_break_the_refresh(self, stores) -> None:
        """Best-effort: a broken snapshot store must not prevent the
        summary refresh (the pre-existing, higher-priority write) from
        succeeding."""
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "old", source_run_id="run-1")
        reader = FakeRunLogReader({"AAPL": "run-2"})

        class _BrokenSnapshotStore:
            def record_daily_snapshot(self, *a, **kw):
                raise RuntimeError("disk full")

        trigger = RunLogTrigger(reader, summaries, ledger, ticker_snapshot_store=_BrokenSnapshotStore())

        result = trigger.refresh_if_stale("AAPL", lambda t: ("new summary", {}))

        assert result.should_refresh is True
        assert summaries.get_summary("AAPL").summary == "new summary"

    def test_runlog_unreachable_logs_distinct_failure_not_confused_with_no_change(self, stores) -> None:
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "old", source_run_id="run-1")
        reader = FakeRunLogReader(raises=True)
        trigger = RunLogTrigger(reader, summaries, ledger)

        calls = []
        result = trigger.refresh_if_stale("AAPL", lambda t: calls.append(t) or ("new", {}))

        assert result.should_refresh is False
        assert result.errored is True
        assert calls == []

        events = ledger.get_events("AAPL")
        assert len(events) == 1
        assert events[0].event_type == "check_failed"
        assert events[0].stage == "runlog_trigger"

        # A genuinely-no-change cycle must NOT produce the same event_type.
        reader_ok = FakeRunLogReader({"AAPL": "run-1"})
        trigger_ok = RunLogTrigger(reader_ok, summaries, ledger)
        trigger_ok.refresh_if_stale("AAPL", lambda t: calls.append(t) or ("new", {}))
        events_after = ledger.get_events("AAPL")
        assert len(events_after) == 1  # no-change cycle logs nothing new
        assert calls == []


class FakeAngleCoverageReader:
    def __init__(self, coverage_by_ticker: dict[str, tuple[int, int]] | None = None, *, raises: bool = False) -> None:
        self._coverage = coverage_by_ticker or {}
        self._raises = raises
        self.call_count = 0

    def coverage(self, ticker: str) -> tuple[int, int]:
        self.call_count += 1
        if self._raises:
            raise ConnectionError("vinu-initial-analysis unreachable")
        return self._coverage.get(ticker.upper(), (0, 28))


class TestAngleCoverageGate:
    """missing-pieces-of-system/angle-comprehension-hierarchy/: a new
    run_id is written per-angle (orchestration_registry.py), not per full
    28-angle batch, so `check()` alone can trigger the Summary Agent's 7
    cluster-synthesis LLM calls after just 1 of 28 angles has data. This
    gate defers `refresh_if_stale` until real coverage clears a
    configured fraction, unless it's been deferred too many times."""

    def test_ships_inert_when_fraction_unset(self, stores) -> None:
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "old", source_run_id="run-1")
        reader = FakeRunLogReader({"AAPL": "run-2"})
        coverage = FakeAngleCoverageReader({"AAPL": (1, 28)})
        # min_angle_coverage_fraction defaults to 0.0 -- gate never fires.
        trigger = RunLogTrigger(reader, summaries, ledger, angle_coverage_reader=coverage)

        calls = []
        result = trigger.refresh_if_stale("AAPL", lambda t: calls.append(t) or ("new", {}))

        assert result.should_refresh is True
        assert calls == ["AAPL"]
        assert coverage.call_count == 0  # never even consulted

    def test_low_coverage_defers_and_does_not_call_summary_agent(self, stores) -> None:
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "old", source_run_id="run-1")
        reader = FakeRunLogReader({"AAPL": "run-2"})
        coverage = FakeAngleCoverageReader({"AAPL": (2, 28)})  # 7%, well below 75%
        trigger = RunLogTrigger(
            reader, summaries, ledger,
            angle_coverage_reader=coverage, min_angle_coverage_fraction=0.75,
        )

        calls = []
        result = trigger.refresh_if_stale("AAPL", lambda t: calls.append(t) or ("new", {}))

        assert result.should_refresh is False
        assert calls == []
        # source_run_id NOT advanced -- next cycle re-checks coverage again.
        assert summaries.get_summary("AAPL").source_run_id == "run-1"

        events = ledger.get_events("AAPL")
        deferred = [e for e in events if e.event_type == "angle_comprehension_deferred"]
        assert len(deferred) == 1
        assert "2/28" in deferred[0].text

    def test_high_coverage_proceeds_normally(self, stores) -> None:
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "old", source_run_id="run-1")
        reader = FakeRunLogReader({"AAPL": "run-2"})
        coverage = FakeAngleCoverageReader({"AAPL": (25, 28)})  # 89%, clears 75%
        trigger = RunLogTrigger(
            reader, summaries, ledger,
            angle_coverage_reader=coverage, min_angle_coverage_fraction=0.75,
        )

        calls = []
        result = trigger.refresh_if_stale("AAPL", lambda t: calls.append(t) or ("new summary", {}))

        assert result.should_refresh is True
        assert calls == ["AAPL"]
        assert summaries.get_summary("AAPL").source_run_id == "run-2"

    def test_gives_up_waiting_after_max_deferrals_within_24h(self, stores) -> None:
        """A permanently-broken angle must not stall comprehension for
        this ticker forever -- after max_angle_coverage_deferrals
        deferrals in the trailing 24h, proceed anyway."""
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "old", source_run_id="run-1")
        coverage = FakeAngleCoverageReader({"AAPL": (2, 28)})  # never improves

        # Simulate 3 prior deferrals already logged in the last 24h.
        for _ in range(3):
            ledger.add_event(
                ticker="AAPL", stage="runlog_trigger",
                event_type="angle_comprehension_deferred", text="deferred",
                source="watchlist",
            )

        reader = FakeRunLogReader({"AAPL": "run-2"})
        trigger = RunLogTrigger(
            reader, summaries, ledger,
            angle_coverage_reader=coverage, min_angle_coverage_fraction=0.75,
            max_angle_coverage_deferrals=3,
        )

        calls = []
        result = trigger.refresh_if_stale("AAPL", lambda t: calls.append(t) or ("new summary", {}))

        assert result.should_refresh is True
        assert calls == ["AAPL"]

    def test_coverage_reader_failure_fails_open(self, stores) -> None:
        """Unlike RunLogReader's own failure (fails closed -- don't even
        know if anything changed), a coverage-check failure fails open:
        we already know something changed, so the worse outcome is never
        comprehending this ticker, not comprehending it slightly early."""
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "old", source_run_id="run-1")
        reader = FakeRunLogReader({"AAPL": "run-2"})
        coverage = FakeAngleCoverageReader(raises=True)
        trigger = RunLogTrigger(
            reader, summaries, ledger,
            angle_coverage_reader=coverage, min_angle_coverage_fraction=0.75,
        )

        calls = []
        result = trigger.refresh_if_stale("AAPL", lambda t: calls.append(t) or ("new summary", {}))

        assert result.should_refresh is True
        assert calls == ["AAPL"]


class TestForceRefresh:
    """The manual override for the angle-coverage gate -- runs
    comprehension immediately regardless of run_id/coverage state, for a
    human who's decided waiting isn't worth it for this one ticker."""

    def test_ignores_coverage_gate_and_stale_run_id(self, stores) -> None:
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "old", source_run_id="run-1")
        # Same run_id as last_seen -- refresh_if_stale would skip this
        # entirely, and low coverage would defer it even if it didn't.
        reader = FakeRunLogReader({"AAPL": "run-1"})
        coverage = FakeAngleCoverageReader({"AAPL": (1, 28)})
        trigger = RunLogTrigger(
            reader, summaries, ledger,
            angle_coverage_reader=coverage, min_angle_coverage_fraction=0.75,
        )

        calls = []
        result = trigger.force_refresh("AAPL", lambda t: calls.append(t) or ("forced summary", {}))

        assert result.should_refresh is True
        assert calls == ["AAPL"]
        assert coverage.call_count == 0  # coverage gate never consulted
        updated = summaries.get_summary("AAPL")
        assert updated.summary == "forced summary"
        assert updated.source_run_id == "run-1"

    def test_logs_a_distinct_forced_event_type(self, stores) -> None:
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "old", source_run_id="run-1")
        reader = FakeRunLogReader({"AAPL": "run-1"})
        trigger = RunLogTrigger(reader, summaries, ledger)

        trigger.force_refresh("AAPL", lambda t: ("forced summary", {}))

        events = ledger.get_events("AAPL")
        forced = [e for e in events if e.event_type == "angle_comprehension_forced"]
        assert len(forced) == 1
        assert forced[0].stage == "runlog_trigger"
        # Distinct from the automatic 24h-deferral-cap proceed-anyway path.
        assert not any(e.event_type == "angle_comprehension_deferred" for e in events)

    def test_run_log_lookup_failure_still_proceeds(self, stores) -> None:
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "old", source_run_id="run-1")
        reader = FakeRunLogReader(raises=True)
        trigger = RunLogTrigger(reader, summaries, ledger)

        calls = []
        result = trigger.force_refresh("AAPL", lambda t: calls.append(t) or ("forced summary", {}))

        assert result.should_refresh is True
        assert calls == ["AAPL"]
        assert summaries.get_summary("AAPL").summary == "forced summary"


class TestChangeGate:
    def test_gate_no_change_returns_no_and_advances(self, stores) -> None:
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "s", source_run_id="run-1")
        strategy_store = FakeStrategyStore({"AAPL": [_Artifact("art-1", _Status("ACTIVE"))]})
        gate = ChangeGate(summaries, strategy_store, ledger)

        first = gate.check("AAPL")
        assert first.should_run is True  # first-ever check, nothing recorded yet
        gate.record_pass("AAPL", first)

        second = gate.check("AAPL")
        assert second.should_run is False

        visited: list[str] = []
        run_gate_cycle(["AAPL", "MSFT"], gate, lambda t, r: visited.append(t))
        # AAPL is unchanged (no), MSFT has never been checked (yes) --
        # proves "no" advances to the next ticker rather than retrying.
        assert visited == ["MSFT"]

    def test_gate_artifact_status_change_alone_returns_yes(self, stores) -> None:
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "s", source_run_id="run-1")
        strategy_store = FakeStrategyStore({"AAPL": [_Artifact("art-1", _Status("BENCHING"))]})
        gate = ChangeGate(summaries, strategy_store, ledger)

        first = gate.check("AAPL")
        gate.record_pass("AAPL", first)
        assert gate.check("AAPL").should_run is False

        # Artifact transitions BENCHING -> ACTIVE; source_run_id unchanged.
        strategy_store._artifacts["AAPL"] = [_Artifact("art-1", _Status("ACTIVE"))]
        result = gate.check("AAPL")
        assert result.should_run is True

    def test_gate_lookup_error_defaults_to_yes(self, stores) -> None:
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "s", source_run_id="run-1")
        strategy_store = FakeStrategyStore(raises=True)
        gate = ChangeGate(summaries, strategy_store, ledger)

        result = gate.check("AAPL")
        assert result.should_run is True
        assert result.errored is True
        events = ledger.get_events("AAPL")
        assert events[-1].event_type == "lookup_failed"

    def test_gate_state_updates_after_a_yes_pass(self, stores) -> None:
        summaries, ledger = stores
        summaries.upsert_summary("AAPL", "s", source_run_id="run-1")
        strategy_store = FakeStrategyStore({"AAPL": [_Artifact("art-1", _Status("ACTIVE"))]})
        gate = ChangeGate(summaries, strategy_store, ledger)

        result = gate.check("AAPL")
        assert result.should_run is True
        gate.record_pass("AAPL", result)

        assert gate.check("AAPL").should_run is False


class TestPhase0EndToEnd:
    def test_phase0_two_cycle_walkthrough(self, stores) -> None:
        summaries, ledger = stores
        strategy_store = FakeStrategyStore({"AAPL": [_Artifact("art-1", _Status("ACTIVE"))]})

        # Cycle 1: RunLog has a fresh run_id AAPL hasn't seen yet.
        reader = FakeRunLogReader({"AAPL": "run-1"})
        trigger = RunLogTrigger(reader, summaries, ledger)
        calls = []
        trigger.refresh_if_stale("AAPL", lambda t: calls.append(t) or ("summary v1", {"angles_with_data": 3, "angle_count": 28}))
        assert calls == ["AAPL"]
        assert summaries.get_summary("AAPL").source_run_id == "run-1"

        ledger_events = ledger.get_events("AAPL")
        assert len(ledger_events) == 1
        assert ledger_events[0].stage == "summary_agent"
        assert ledger_events[0].event_type == "summary_refreshed"

        gate = ChangeGate(summaries, strategy_store, ledger)
        gate_result = gate.check("AAPL")
        assert gate_result.should_run is True  # state changed within this pass
        gate.record_pass("AAPL", gate_result)

        # Cycle 2: nothing changed since cycle 1.
        reader2 = FakeRunLogReader({"AAPL": "run-1"})
        trigger2 = RunLogTrigger(reader2, summaries, ledger)
        calls2 = []
        trigger2.refresh_if_stale("AAPL", lambda t: calls2.append(t) or ("should not run", {}))
        assert calls2 == []  # zero LLM calls this cycle

        assert gate.check("AAPL").should_run is False

        visited = []
        run_gate_cycle(["AAPL"], gate, lambda t, r: visited.append(t))
        assert visited == []  # advances past AAPL, nothing to do
