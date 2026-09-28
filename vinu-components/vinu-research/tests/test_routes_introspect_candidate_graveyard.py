"""item #16 finding #3: the HTTP read side of candidate_graveyard.py --
GET /research/candidate-graveyard/{symbol}. Same real-app-wiring pattern
test_routes_introspect_generation_rounds.py already uses, not a
standalone router (the route needs both routes_introspect's own
_service and routes_sweep's already-wired sweep store, so create_app()
is exercised for real, not mocked)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

import vinu_research.hypothesis_registry as hr
from vinu_research.config import ResearchConfig
from vinu_research.hypothesis_registry import HypothesisRegistry
from vinu_research.models import Hypothesis
from vinu_research.server.app import create_app
from vinu_research.service import ResearchService


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
def client(storage, tmp_path):
    service = ResearchService(config=ResearchConfig(data_root=tmp_path), storage=storage)
    app = create_app(service)
    with TestClient(app) as test_client:
        yield test_client, service


def test_empty_graveyard_by_default(client) -> None:
    test_client, _service = client
    resp = test_client.get("/research/candidate-graveyard/AAPL")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "AAPL"
    assert body["count"] == 0
    assert body["entries"] == []


def test_symbol_is_uppercased(client) -> None:
    test_client, _service = client
    resp = test_client.get("/research/candidate-graveyard/aapl")
    assert resp.status_code == 200
    assert resp.json()["symbol"] == "AAPL"


def test_generation_discard_is_visible_over_http(client) -> None:
    test_client, service = client
    service.generation_candidate_store.record_round(
        "gen-1", symbol="AAPL", iteration=1, mode="generate",
        ranked=[
            _FakeRanked(_FakeCandidate("class Winner: pass"), score=90.0, complexity_score=90.0),
            _FakeRanked(_FakeCandidate("class Loser: pass", "too complex"), score=50.0, complexity_score=50.0),
        ],
    )

    resp = test_client.get("/research/candidate-graveyard/AAPL")

    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["entries"][0]["source"] == "generation"
    assert body["entries"][0]["reason"] == "too complex"


def test_rejected_hypothesis_is_visible_over_http(client, tmp_path, monkeypatch) -> None:
    test_client, _service = client
    # The route constructs its own HypothesisRegistry() at the default
    # path -- same convention list_hypotheses/pool_indicator_evidence
    # already use, so redirect that default path the same way
    # test_routes_introspect_indicator_pool.py already does, rather than
    # writing to the real on-disk hypotheses.json.
    monkeypatch.setattr(hr, "HYPOTHESES_PATH", tmp_path / "hyp.json")
    reg = HypothesisRegistry()
    h = Hypothesis.create("Idea", "thesis", universe=["AAPL"])
    reg.create(h)
    reg.reject_with_reason(h.hypothesis_id, "no evidence supported it")

    resp = test_client.get("/research/candidate-graveyard/AAPL")

    assert resp.status_code == 200
    body = resp.json()
    assert any(e["source"] == "hypothesis" and e["reason"] == "no evidence supported it" for e in body["entries"])
