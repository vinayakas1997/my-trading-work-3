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
