"""item #16 finding #2: generation-time candidate loss now has a real
persistence surface -- previously nothing recorded which candidates were
drafted and discarded before any backtest ever ran."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from vinu_research.generation_candidate_store import GenerationCandidateStore, code_hash


@dataclass
class _FakeCandidate:
    code: str
    reasoning: str = ""


@dataclass
class _FakeRanked:
    candidate: _FakeCandidate
    score: float
    complexity_score: float


@pytest.fixture
def store():
    return GenerationCandidateStore(":memory:")


def _ranked(n=3):
    return [
        _FakeRanked(_FakeCandidate(f"class S{i}: pass", reasoning=f"reasoning {i}"), score=100.0 - i, complexity_score=90.0 - i)
        for i in range(n)
    ]


class TestCodeHash:
    def test_same_code_hashes_the_same(self) -> None:
        assert code_hash("class X: pass") == code_hash("class X: pass")

    def test_different_code_hashes_differently(self) -> None:
        assert code_hash("class X: pass") != code_hash("class Y: pass")

    def test_empty_code_does_not_crash(self) -> None:
        assert code_hash("") and code_hash(None)  # type: ignore[arg-type]


class TestRecordAndGetRound:
    def test_round_trip_header_fields(self, store) -> None:
        store.record_round("gen-1", symbol="AAPL", iteration=1, mode="generate", ranked=_ranked(3), now=100.0)
        round_ = store.get_round("gen-1")
        assert round_ is not None
        assert round_["symbol"] == "AAPL"
        assert round_["iteration"] == 1
        assert round_["mode"] == "generate"
        assert round_["n_candidates"] == 3
        assert round_["created_at"] == 100.0

    def test_unknown_generation_id_is_none(self, store) -> None:
        assert store.get_round("ghost") is None

    def test_winner_is_flagged_chosen_and_ranked_first(self, store) -> None:
        ranked = _ranked(3)
        store.record_round("gen-1", symbol="AAPL", iteration=1, mode="generate", ranked=ranked)
        candidates = store.get_round("gen-1")["candidates"]
        assert candidates[0]["chosen"] is True
        assert candidates[0]["code_hash"] == code_hash(ranked[0].candidate.code)
        assert all(not c["chosen"] for c in candidates[1:])

    def test_every_candidate_is_recorded_not_just_the_winner(self, store) -> None:
        store.record_round("gen-1", symbol="AAPL", iteration=1, mode="generate", ranked=_ranked(3))
        assert len(store.get_round("gen-1")["candidates"]) == 3

    def test_reasoning_excerpt_is_truncated(self, store) -> None:
        long_reasoning = "x" * 500
        ranked = [_FakeRanked(_FakeCandidate("class S: pass", reasoning=long_reasoning), score=1.0, complexity_score=1.0)]
        store.record_round("gen-1", symbol="AAPL", iteration=1, mode="generate", ranked=ranked)
        assert len(store.get_round("gen-1")["candidates"][0]["reasoning_excerpt"]) <= 200

    def test_refine_mode_is_recorded_distinctly(self, store) -> None:
        store.record_round("gen-1", symbol="AAPL", iteration=2, mode="refine", ranked=_ranked(2))
        assert store.get_round("gen-1")["mode"] == "refine"


class TestListRounds:
    def test_returns_headers_most_recent_first(self, store) -> None:
        store.record_round("g1", symbol="AAPL", iteration=1, mode="generate", ranked=_ranked(2), now=1.0)
        store.record_round("g2", symbol="AAPL", iteration=2, mode="refine", ranked=_ranked(2), now=2.0)
        rounds = store.list_rounds(symbol="AAPL")
        assert [r["generation_id"] for r in rounds] == ["g2", "g1"]

    def test_symbol_filter_is_a_real_query(self, store) -> None:
        store.record_round("g1", symbol="AAPL", iteration=1, mode="generate", ranked=_ranked(2), now=1.0)
        store.record_round("g2", symbol="MSFT", iteration=1, mode="generate", ranked=_ranked(2), now=2.0)
        assert [r["generation_id"] for r in store.list_rounds(symbol="AAPL")] == ["g1"]


class TestFindByCodeHash:
    def test_finds_a_previously_discarded_candidate_by_its_code(self, store) -> None:
        ranked = _ranked(3)
        store.record_round("gen-1", symbol="AAPL", iteration=1, mode="generate", ranked=ranked)
        loser_hash = code_hash(ranked[2].candidate.code)
        hits = store.find_by_code_hash(loser_hash)
        assert len(hits) == 1
        assert hits[0]["chosen"] is False
        assert hits[0]["generation_id"] == "gen-1"

    def test_unknown_hash_returns_empty(self, store) -> None:
        assert store.find_by_code_hash("no-such-hash") == []

    def test_the_same_code_tried_across_multiple_rounds_is_found_in_both(self, store) -> None:
        same_code = "class Repeated: pass"
        r1 = [_FakeRanked(_FakeCandidate(same_code), score=1.0, complexity_score=1.0)]
        r2 = [_FakeRanked(_FakeCandidate(same_code), score=2.0, complexity_score=2.0)]
        store.record_round("g1", symbol="AAPL", iteration=1, mode="generate", ranked=r1, now=1.0)
        store.record_round("g2", symbol="AAPL", iteration=2, mode="generate", ranked=r2, now=2.0)
        hits = store.find_by_code_hash(code_hash(same_code))
        assert len(hits) == 2
        assert {h["generation_id"] for h in hits} == {"g1", "g2"}
