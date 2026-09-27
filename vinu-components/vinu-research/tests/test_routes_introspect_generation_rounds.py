"""item #16 finding #2: the read side of generation_candidate_store.py --
this file previously had zero dedicated route-level tests at all (a real,
separate gap, not fixed wholesale here -- these two routes are new, so
they get their own coverage; the rest of routes_introspect.py's existing
routes remain untested exactly as they were)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vinu_research.config import ResearchConfig
from vinu_research.server.app import create_app
from vinu_research.service import ResearchService


@pytest.fixture
def client(storage, tmp_path):
    service = ResearchService(config=ResearchConfig(data_root=tmp_path), storage=storage)
    app = create_app(service)
    with TestClient(app) as test_client:
        yield test_client, service


def test_list_generation_rounds_empty_by_default(client) -> None:
    test_client, _ = client
    resp = test_client.get("/research/generation-rounds")
    assert resp.status_code == 200
    assert resp.json() == {"rounds": []}


def test_get_unknown_generation_round_is_404(client) -> None:
    test_client, _ = client
    assert test_client.get("/research/generation-rounds/ghost-id").status_code == 404


def test_list_and_get_round_after_recording_one(client) -> None:
    from dataclasses import dataclass

    test_client, service = client

    @dataclass
    class _FakeCandidate:
        code: str
        reasoning: str = ""

    @dataclass
    class _FakeRanked:
        candidate: _FakeCandidate
        score: float
        complexity_score: float

    service.generation_candidate_store.record_round(
        "gen-1", symbol="AAPL", iteration=1, mode="generate",
        ranked=[
            _FakeRanked(_FakeCandidate("class Winner: pass", "best"), score=90.0, complexity_score=90.0),
            _FakeRanked(_FakeCandidate("class Loser: pass", "worse"), score=50.0, complexity_score=50.0),
        ],
    )

    list_resp = test_client.get("/research/generation-rounds", params={"symbol": "AAPL"})
    assert list_resp.status_code == 200
    rounds = list_resp.json()["rounds"]
    assert len(rounds) == 1
    assert rounds[0]["generation_id"] == "gen-1"

    get_resp = test_client.get("/research/generation-rounds/gen-1")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["symbol"] == "AAPL"
    assert len(body["candidates"]) == 2
    assert body["candidates"][0]["chosen"] is True
