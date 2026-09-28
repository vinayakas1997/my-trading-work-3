"""item #16 finding #3 (missing-pieces-of-system/new-theory-of-trading/
system-wide-audit-and-design/02-open-questions-strategy-and-simulation.md):
"has something like this already failed, and why" across all three real
death points for a research idea -- generation-time, sweep-time, and
hypothesis-level rejection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from vinu_research.candidate_graveyard import query_candidate_graveyard
from vinu_research.generation_candidate_store import GenerationCandidateStore
from vinu_research.hypothesis_registry import HypothesisRegistry
from vinu_research.models import Hypothesis, HypothesisStatus
from vinu_research.sweep_store import SweepGridStore


@dataclass
class _FakeCandidate:
    code: str
    reasoning: str = ""


@dataclass
class _FakeRanked:
    candidate: _FakeCandidate
    score: float
    complexity_score: float


@dataclass
class _FakeSweepResult:
    run_id: str


@dataclass
class _FakeSweepRanked:
    score: float
    risk_score: float
    complexity_score: float
    params: dict
    sweep_result: _FakeSweepResult


@dataclass
class _FakeOutcome:
    params: dict
    succeeded: bool
    error: str = ""


@dataclass
class _FakeGridResult:
    requested: int
    succeeded: int
    completeness: float
    ranked: list
    pbo: dict | None
    outcomes: list
    walk_forward: dict | None = None


@pytest.fixture
def generation_store():
    return GenerationCandidateStore(":memory:")


@pytest.fixture
def sweep_store():
    return SweepGridStore(":memory:")


@pytest.fixture
def hypothesis_registry(tmp_path):
    return HypothesisRegistry(tmp_path / "hypotheses.json")


def test_empty_graveyard_when_nothing_recorded(generation_store, sweep_store) -> None:
    entries = query_candidate_graveyard(
        "AAPL", generation_store=generation_store, sweep_store=sweep_store,
    )
    assert entries == []


def test_generation_discards_appear_but_not_the_winner(generation_store, sweep_store) -> None:
    generation_store.record_round(
        "gen-1", symbol="AAPL", iteration=1, mode="generate",
        ranked=[
            _FakeRanked(_FakeCandidate("class Winner: pass", "best idea"), score=90.0, complexity_score=90.0),
            _FakeRanked(_FakeCandidate("class Loser: pass", "too complex"), score=50.0, complexity_score=50.0),
        ],
        now=1_700_000_000.0,
    )
    entries = query_candidate_graveyard(
        "AAPL", generation_store=generation_store, sweep_store=sweep_store,
    )
    assert len(entries) == 1
    assert entries[0]["source"] == "generation"
    assert entries[0]["reason"] == "too complex"
    assert entries[0]["generation_id"] == "gen-1"
    # ISO-normalized, not the raw epoch float the store itself uses.
    assert entries[0]["created_at"] == datetime.fromtimestamp(1_700_000_000.0, tz=timezone.utc).isoformat()


def test_sweep_failures_appear_but_not_succeeded_points(generation_store, sweep_store) -> None:
    sweep_store.record_sweep(
        "sweep-1", symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
        result=_FakeGridResult(
            requested=2, succeeded=1, completeness=0.5, pbo=None, walk_forward=None,
            ranked=[_FakeSweepRanked(1.2, 0.1, 0.1, {"period": 9}, _FakeSweepResult("run-a"))],
            outcomes=[
                _FakeOutcome({"period": 9}, True),
                _FakeOutcome({"period": 999}, False, "ParameterNotFoundError"),
            ],
        ),
        now=1_700_000_100.0,
    )
    entries = query_candidate_graveyard(
        "AAPL", generation_store=generation_store, sweep_store=sweep_store,
    )
    assert len(entries) == 1
    assert entries[0]["source"] == "sweep"
    assert entries[0]["reason"] == "ParameterNotFoundError"
    assert entries[0]["sweep_id"] == "sweep-1"
    assert entries[0]["params"] == {"period": 999}


def test_rejected_hypotheses_appear_when_registry_is_passed(
    generation_store, sweep_store, hypothesis_registry,
) -> None:
    h = Hypothesis.create("Momentum idea", "thesis text", universe=["AAPL"])
    hypothesis_registry.create(h)
    hypothesis_registry.reject_with_reason(h.hypothesis_id, "no evidence supported it")

    entries = query_candidate_graveyard(
        "AAPL", generation_store=generation_store, sweep_store=sweep_store,
        hypothesis_registry=hypothesis_registry,
    )
    assert len(entries) == 1
    assert entries[0]["source"] == "hypothesis"
    assert entries[0]["reason"] == "no evidence supported it"
    assert entries[0]["hypothesis_id"] == h.hypothesis_id


def test_hypothesis_registry_omitted_means_that_source_is_simply_skipped(
    generation_store, sweep_store,
) -> None:
    """No hypothesis_registry passed at all -- must not crash or invent a
    default-path instance, just return the other two sources' entries."""
    generation_store.record_round(
        "gen-1", symbol="AAPL", iteration=1, mode="generate",
        ranked=[
            _FakeRanked(_FakeCandidate("class Winner: pass"), score=90.0, complexity_score=90.0),
            _FakeRanked(_FakeCandidate("class Loser: pass", "reason"), score=50.0, complexity_score=50.0),
        ],
        now=1_700_000_000.0,
    )
    entries = query_candidate_graveyard(
        "AAPL", generation_store=generation_store, sweep_store=sweep_store,
    )
    assert len(entries) == 1
    assert entries[0]["source"] == "generation"


def test_entries_from_all_three_sources_are_combined_and_sorted_most_recent_first(
    generation_store, sweep_store, hypothesis_registry,
) -> None:
    generation_store.record_round(
        "gen-1", symbol="AAPL", iteration=1, mode="generate",
        ranked=[
            _FakeRanked(_FakeCandidate("class W: pass"), score=90.0, complexity_score=90.0),
            _FakeRanked(_FakeCandidate("class L: pass", "gen reason"), score=50.0, complexity_score=50.0),
        ],
        now=1_700_000_000.0,  # oldest
    )
    sweep_store.record_sweep(
        "sweep-1", symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
        result=_FakeGridResult(
            requested=1, succeeded=0, completeness=0.0, pbo=None, walk_forward=None,
            ranked=[],
            outcomes=[_FakeOutcome({"period": 9}, False, "sweep reason")],
        ),
        now=1_700_000_300.0,  # newest
    )
    h = Hypothesis.create("Idea", "thesis", universe=["AAPL"])
    hypothesis_registry.create(h)
    hypothesis_registry.reject_with_reason(h.hypothesis_id, "hyp reason")
    # updated_at is set to "now" (real wall-clock) by reject_with_reason --
    # force it between the other two fixed timestamps via the public
    # update() method, so ordering is unambiguous rather than depending on
    # wall-clock timing during the test run.
    rejected = hypothesis_registry.get(h.hypothesis_id)
    rejected.updated_at = datetime.fromtimestamp(1_700_000_150.0, tz=timezone.utc).isoformat()
    hypothesis_registry.update(rejected)

    entries = query_candidate_graveyard(
        "AAPL", generation_store=generation_store, sweep_store=sweep_store,
        hypothesis_registry=hypothesis_registry,
    )
    assert [e["source"] for e in entries] == ["sweep", "hypothesis", "generation"]


def test_other_symbols_are_not_returned(generation_store, sweep_store) -> None:
    generation_store.record_round(
        "gen-1", symbol="MSFT", iteration=1, mode="generate",
        ranked=[
            _FakeRanked(_FakeCandidate("class W: pass"), score=90.0, complexity_score=90.0),
            _FakeRanked(_FakeCandidate("class L: pass", "reason"), score=50.0, complexity_score=50.0),
        ],
    )
    entries = query_candidate_graveyard(
        "AAPL", generation_store=generation_store, sweep_store=sweep_store,
    )
    assert entries == []


def test_limit_caps_the_combined_result(generation_store, sweep_store) -> None:
    for i in range(5):
        generation_store.record_round(
            f"gen-{i}", symbol="AAPL", iteration=1, mode="generate",
            ranked=[
                _FakeRanked(_FakeCandidate("class W: pass"), score=90.0, complexity_score=90.0),
                _FakeRanked(_FakeCandidate("class L: pass", f"reason-{i}"), score=50.0, complexity_score=50.0),
            ],
            now=1_700_000_000.0 + i,
        )
    entries = query_candidate_graveyard(
        "AAPL", generation_store=generation_store, sweep_store=sweep_store, limit=2,
    )
    assert len(entries) == 2
