"""Tests for the Planner triage hook -- Phase 9 scheduler-wiring
(New-talk-agents/new-thinking/new-restructure/phases/
phase-9-scheduler-wiring/). See agent/planner_triage_hook.py.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from vinu_agent.agent.planner_triage_hook import (
    CANDIDATE_PROPOSED_EVENT_TYPE,
    PlannerTriage,
    PlannerTriageResult,
)


class FakeArtifact:
    def __init__(self, status: str) -> None:
        self.status = MagicMock(value=status)


class FakeStrategyStore:
    def __init__(self, artifacts: list[FakeArtifact] | None = None, *, raises: bool = False) -> None:
        self._artifacts = artifacts or []
        self._raises = raises

    def list_artifacts_for_symbol(self, symbol: str, statuses=None) -> list[FakeArtifact]:
        if self._raises:
            raise RuntimeError("db down")
        return self._artifacts


class FakeHypothesisReader:
    def __init__(self, hyps: list[dict[str, Any]] | None = None, *, raises: bool = False) -> None:
        self._hyps = hyps or []
        self._raises = raises

    def query_by_symbol(self, ticker: str) -> list[dict[str, Any]]:
        if self._raises:
            raise RuntimeError("db down")
        return self._hyps


class FakeTickerLedger:
    def __init__(self, count: int = 0, *, count_raises: bool = False) -> None:
        self._count = count
        self._count_raises = count_raises
        self.events: list[dict[str, Any]] = []

    def count_events(self, ticker: str, *, event_type: str | None = None, since: str | None = None) -> int:
        if self._count_raises:
            raise RuntimeError("db down")
        return self._count

    def add_event(self, ticker, stage, event_type, text, *, ref_id="", source="watchlist"):
        self.events.append({
            "ticker": ticker, "stage": stage, "event_type": event_type,
            "text": text, "ref_id": ref_id, "source": source,
        })


def _triage(strategy_store=None, hypothesis_reader=None, ticker_ledger=None, **kwargs) -> PlannerTriage:
    return PlannerTriage(
        strategy_store or FakeStrategyStore(),
        hypothesis_reader or FakeHypothesisReader(),
        ticker_ledger or FakeTickerLedger(),
        recipes=kwargs.pop("recipes", ["macd_cross", "rsi_reversion", "breakout"]),
        **kwargs,
    )


class TestKCap:
    """Real fix, 2026-09-21 (missing-pieces-of-system/startegy-enhancer/
    02-implementation.md): the K-cap now counts real, currently
    non-terminal artifacts for the ticker (the same
    `list_artifacts_for_symbol(NON_TERMINAL_STATUSES)` lookup this
    function already ran for recipe rotation) -- not a rolling time
    window over ticker_ledger events (the earlier, honestly-scoped-as-
    imprecise interim fix; see this file's git history for those tests).
    A slot frees the instant a candidate actually resolves (ACTIVE, or
    DISABLED on a genuine promotion-bar rejection), not after a fixed
    number of days regardless of what happened."""

    def test_under_cap_proceeds(self) -> None:
        triage = _triage(strategy_store=FakeStrategyStore([FakeArtifact("BENCHING")]), k_cap=3)
        result = triage.check("AAPL")
        assert result.should_propose is True

    def test_at_cap_skips(self) -> None:
        triage = _triage(
            strategy_store=FakeStrategyStore(
                [FakeArtifact("ACTIVE"), FakeArtifact("BENCHING"), FakeArtifact("PEND")],
            ),
            k_cap=3,
        )
        result = triage.check("AAPL")
        assert result.should_propose is False
        assert "cap" in result.reason

    def test_decayed_and_disabled_artifacts_do_not_count(self, tmp_path) -> None:
        """Real regression: a ticker whose 3 lifetime candidates all
        genuinely resolved (2 DISABLED after a real promotion-bar
        rejection, 1 DECAYED after real underperformance) must not be
        locked out -- confirms the fix actually reads live status, not
        just a raw count, using the real SqliteStrategyStore, not the
        fake (the fake doesn't simulate status filtering)."""
        from vinu_research.models import Artifact, ArtifactStatus
        from vinu_research.storage.strategy_store import SqliteStrategyStore

        store = SqliteStrategyStore(tmp_path / "strategy_store.db")
        for status in (ArtifactStatus.DISABLED, ArtifactStatus.DISABLED, ArtifactStatus.DECAYED):
            art = Artifact.create("strategy", "old", universe=["AAPL"])
            art.status = status
            store.upsert_artifact(art)

        triage = _triage(strategy_store=store, k_cap=3)
        result = triage.check("AAPL")
        assert result.should_propose is True, result.reason

    def test_non_terminal_artifacts_still_count_regardless_of_age(self, tmp_path) -> None:
        from vinu_research.models import Artifact, ArtifactStatus
        from vinu_research.storage.strategy_store import SqliteStrategyStore

        store = SqliteStrategyStore(tmp_path / "strategy_store.db")
        for _ in range(3):
            art = Artifact.create("strategy", "still-open", universe=["AAPL"])
            art.status = ArtifactStatus.BENCHING
            store.upsert_artifact(art)

        triage = _triage(strategy_store=store, k_cap=3)
        result = triage.check("AAPL")
        assert result.should_propose is False
        assert "cap" in result.reason


class TestArtifactDedup:
    def test_artifact_lookup_failure_defaults_to_skip(self) -> None:
        triage = _triage(strategy_store=FakeStrategyStore(raises=True))
        result = triage.check("AAPL")
        assert result.should_propose is False
        assert "artifact lookup failed" in result.reason

    def test_recipe_rotates_by_existing_artifact_count(self) -> None:
        recipes = ["macd_cross", "rsi_reversion", "breakout"]
        no_artifacts = _triage(strategy_store=FakeStrategyStore([]), recipes=recipes)
        one_artifact = _triage(strategy_store=FakeStrategyStore([FakeArtifact("ACTIVE")]), recipes=recipes)
        two_artifacts = _triage(
            strategy_store=FakeStrategyStore([FakeArtifact("ACTIVE"), FakeArtifact("BENCHING")]), recipes=recipes,
        )
        assert no_artifacts.check("AAPL").recipe_name == "macd_cross"
        assert one_artifact.check("AAPL").recipe_name == "rsi_reversion"
        assert two_artifacts.check("AAPL").recipe_name == "breakout"

    def test_no_recipes_available_skips(self) -> None:
        triage = _triage(recipes=[])
        result = triage.check("AAPL")
        assert result.should_propose is False
        assert "no sweep recipes" in result.reason


class TestHypothesisConsult:
    def test_prior_rejections_surfaced_in_result(self) -> None:
        hyps = [
            {"status": "rejected", "invalidation_reason": "correlation too high with existing book", "thesis": "x"},
            {"status": "validated", "invalidation_reason": None, "thesis": "y"},
        ]
        triage = _triage(hypothesis_reader=FakeHypothesisReader(hyps))
        result = triage.check("AAPL")
        assert result.should_propose is True
        assert result.prior_rejections == ["correlation too high with existing book"]

    def test_hypothesis_lookup_failure_proceeds_without_it(self) -> None:
        """Not a fail-closed gate -- HypothesisRegistry is context, not a
        budget/safety check, so a lookup failure shouldn't block a
        proposal that's otherwise fine."""
        triage = _triage(hypothesis_reader=FakeHypothesisReader(raises=True))
        result = triage.check("AAPL")
        assert result.should_propose is True
        assert result.prior_rejections == []


class TestOnPropose:
    def test_writes_candidate_proposed_event(self) -> None:
        ledger = FakeTickerLedger()
        triage = _triage(ticker_ledger=ledger)
        result = PlannerTriageResult("AAPL", True, "reason", recipe_name="macd_cross")
        triage.on_propose("aapl", result, ref_id="run_123")

        assert len(ledger.events) == 1
        event = ledger.events[0]
        assert event["ticker"] == "AAPL"
        assert event["event_type"] == CANDIDATE_PROPOSED_EVENT_TYPE
        assert event["ref_id"] == "run_123"
        assert event["source"] == "watchlist"
        assert "macd_cross" in event["text"]

    def test_debate_run_id_appended_to_note_when_present(self) -> None:
        ledger = FakeTickerLedger()
        triage = _triage(ticker_ledger=ledger)
        result = PlannerTriageResult("AAPL", True, "reason", recipe_name="macd_cross")
        triage.on_propose("AAPL", result, ref_id="run_123", debate_run_id="debate_99")

        event = ledger.events[0]
        assert event["ref_id"] == "run_123"  # unchanged meaning: the research run
        assert "debate_run_id=debate_99" in event["text"]

    def test_no_debate_run_id_omits_it_from_note(self) -> None:
        ledger = FakeTickerLedger()
        triage = _triage(ticker_ledger=ledger)
        result = PlannerTriageResult("AAPL", True, "reason", recipe_name="macd_cross")
        triage.on_propose("AAPL", result, ref_id="run_123")

        assert "debate_run_id" not in ledger.events[0]["text"]

    def test_write_failure_does_not_raise(self) -> None:
        class RaisingLedger(FakeTickerLedger):
            def add_event(self, *a, **kw):
                raise RuntimeError("db down")

        triage = _triage(ticker_ledger=RaisingLedger())
        result = PlannerTriageResult("AAPL", True, "reason", recipe_name="macd_cross")
        triage.on_propose("AAPL", result)  # must not raise
