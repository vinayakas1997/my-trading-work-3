"""Tests for THGATE -- Phase 6 (New-talk-agents/new-thinking/
new-restructure/phases/phase-6-thesis-intake/). See
agent/thesis_intake_gate.py.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from vinu_agent.agent.thesis_intake_gate import (
    CANDIDATE_PROPOSED_EVENT_TYPE,
    ThesisIntakeGate,
    jaccard_similarity,
)
from vinu_agent.storage.ticker_ledger import TickerLedgerStore


class FakeHypothesisReader:
    def __init__(self, hypotheses: list[dict] | None = None, *, raises: bool = False) -> None:
        self._hypotheses = hypotheses or []
        self._raises = raises

    def query_by_symbol(self, ticker: str) -> list[dict]:
        if self._raises:
            raise ConnectionError("vinu-research unreachable")
        return self._hypotheses


@pytest.fixture
def ticker_ledger_store():
    path = Path(tempfile.mktemp(suffix=".db"))
    store = TickerLedgerStore(path)
    yield store
    store.close()
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        pass


class TestJaccardSimilarity:
    def test_identical_text_is_1(self) -> None:
        assert jaccard_similarity("AAPL keeps drifting after earnings", "AAPL keeps drifting after earnings") == 1.0

    def test_disjoint_text_is_0(self) -> None:
        assert jaccard_similarity("AAPL momentum theory", "MSFT mean reversion idea") == 0.0

    def test_partial_overlap_computed_correctly(self) -> None:
        # {aapl, drifts, up} vs {aapl, drifts, down} -> intersection={aapl,drifts}=2, union=4
        assert jaccard_similarity("AAPL drifts up", "AAPL drifts down") == pytest.approx(0.5)

    def test_empty_string_is_0(self) -> None:
        assert jaccard_similarity("", "something") == 0.0


class TestThGate:
    def test_thgate_blocks_near_duplicate_theory(self, ticker_ledger_store) -> None:
        reader = FakeHypothesisReader([
            {"hypothesis_id": "hyp_1", "thesis": "AAPL tends to drift after an earnings surprise for a week"},
        ])
        gate = ThesisIntakeGate(reader, ticker_ledger_store)

        result = gate.check("AAPL", "AAPL tends to drift after an earnings surprise for a week or so")

        assert result.allowed is False
        assert "near-duplicate" in result.reason
        assert result.matched_hypothesis_id == "hyp_1"
        assert result.matched_thesis is not None

    def test_thgate_allows_genuinely_distinct_theory(self, ticker_ledger_store) -> None:
        reader = FakeHypothesisReader([
            {"hypothesis_id": "hyp_1", "thesis": "AAPL mean reverts after overbought RSI readings"},
        ])
        gate = ThesisIntakeGate(reader, ticker_ledger_store)

        result = gate.check("AAPL", "MSFT rallies in the week before major product launch events")

        assert result.allowed is True

    def test_shared_kcap_counts_across_both_sources(self, ticker_ledger_store) -> None:
        # K default is 3 -- seed 2 events (K-1), mixed sources.
        ticker_ledger_store.add_event(
            ticker="AAPL", stage="research", event_type=CANDIDATE_PROPOSED_EVENT_TYPE,
            text="idea 1", source="watchlist",
        )
        ticker_ledger_store.add_event(
            ticker="AAPL", stage="thesis_intake", event_type=CANDIDATE_PROPOSED_EVENT_TYPE,
            text="idea 2", source="human",
        )
        reader = FakeHypothesisReader([])
        gate = ThesisIntakeGate(reader, ticker_ledger_store, k_cap=3)

        result = gate.check("AAPL", "a genuinely new theory")
        assert result.allowed is True  # 2 < 3, still under cap

        # One more (from either source) pushes it to cap.
        ticker_ledger_store.add_event(
            ticker="AAPL", stage="thesis_intake", event_type=CANDIDATE_PROPOSED_EVENT_TYPE,
            text="idea 3", source="human",
        )
        result2 = gate.check("AAPL", "yet another distinct theory")
        assert result2.allowed is False
        assert "cap" in result2.reason

    def test_kcap_blocks_correctly_even_when_all_prior_events_from_one_source(self, ticker_ledger_store) -> None:
        for i in range(3):
            ticker_ledger_store.add_event(
                ticker="AAPL", stage="research", event_type=CANDIDATE_PROPOSED_EVENT_TYPE,
                text=f"idea {i}", source="watchlist",
            )
        reader = FakeHypothesisReader([])
        gate = ThesisIntakeGate(reader, ticker_ledger_store, k_cap=3)

        result = gate.check("AAPL", "a human theory arriving after 3 watchlist-only candidates")

        assert result.allowed is False
        assert "cap" in result.reason

    def test_lookup_failure_fails_open_toward_allow(self, ticker_ledger_store) -> None:
        reader = FakeHypothesisReader(raises=True)
        gate = ThesisIntakeGate(reader, ticker_ledger_store)

        result = gate.check("AAPL", "a theory submitted while vinu-research happens to be down")

        assert result.allowed is True

    def test_kcap_query_scoped_to_ticker_not_global(self, ticker_ledger_store) -> None:
        for i in range(3):
            ticker_ledger_store.add_event(
                ticker="MSFT", stage="research", event_type=CANDIDATE_PROPOSED_EVENT_TYPE,
                text=f"idea {i}", source="watchlist",
            )
        reader = FakeHypothesisReader([])
        gate = ThesisIntakeGate(reader, ticker_ledger_store, k_cap=3)

        # AAPL has zero events of its own -- MSFT's cap must not bleed over.
        result = gate.check("AAPL", "a fresh AAPL theory")
        assert result.allowed is True
