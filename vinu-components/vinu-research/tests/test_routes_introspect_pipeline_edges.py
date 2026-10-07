"""Phase 3 of the-inconsistencies-v2 plan: GET /research/pipeline-edges, the
"which declared connections are actually flowing" view (edge manifest joined
with what the instrumented consumers recorded). Read-only, same idiom as the
other routes in routes_introspect.py."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vinu_infra import pipeline_edge_recorder as rec
from vinu_infra import pipeline_edges
from vinu_research.server.app import create_app


@pytest.fixture
def client(service, tmp_path, monkeypatch):
    monkeypatch.delenv("VINU_STRATEGY_EVAL_DATA_ROOT", raising=False)
    monkeypatch.setenv("VINU_EDGE_DATA_ROOT", str(tmp_path))
    rec.reset_for_tests()
    app = create_app(service)
    with TestClient(app) as test_client:
        yield test_client
    rec.reset_for_tests()


def _by_id(body):
    return {e["edge_id"]: e for e in body["edges"]}


def test_every_manifest_edge_is_reported_with_a_state(client) -> None:
    body = client.get("/research/pipeline-edges").json()
    manifest = pipeline_edges.load_edges()
    assert body["recording_enabled"] is True and body["count"] == len(manifest) == len(body["edges"])
    assert {e["edge_id"] for e in body["edges"]} == {e.id for e in manifest}


def test_known_gaps_and_uninstrumented_edges_are_not_called_broken(client) -> None:
    by_id = _by_id(client.get("/research/pipeline-edges").json())
    # the last declared gap (book.writes->live.scheduler) was wired on 2026-10-07: it is instrumented and nothing has recorded yet
    assert by_id["book.writes->live.scheduler"]["state"] == "never_seen"
    assert not [e for e in by_id.values() if e["state"] == "known_gap"]
    # every wired edge in the manifest is now instrumented, so none can report `not_instrumented` any more
    # (that state itself is covered against synthetic edges in vinu-infra's test_pipeline_edge_recorder.py)
    assert not [e for e in by_id.values() if e["state"] == "not_instrumented"]
    assert by_id["screener.top->agent.planner_worker"]["state"] == "never_seen"


def test_an_instrumented_edge_nothing_ever_recorded_is_never_seen(client) -> None:
    by_id = _by_id(client.get("/research/pipeline-edges").json())
    assert by_id["portfolio.state->live.scheduler"]["state"] == "never_seen"


def test_a_recorded_edge_reports_flowing_then_missing_with_details(client, tmp_path) -> None:
    rec.record_edge("portfolio.state->live.scheduler", "received")
    assert _by_id(client.get("/research/pipeline-edges").json())["portfolio.state->live.scheduler"]["state"] == "flowing"

    rec.record_edge("portfolio.state->live.scheduler", "missing", "GET /portfolio/state failed: boom")
    edge = _by_id(client.get("/research/pipeline-edges").json())["portfolio.state->live.scheduler"]
    assert edge["state"] == "missing" and "boom" in edge["last_detail"]
    assert edge["counts"]["received"] == 1 and edge["counts"]["missing"] == 1


def test_only_problems_returns_just_what_needs_attention(client) -> None:
    rec.record_edge("research.active_trade_plans->live.orchestrator", "missing", "HTTP 500")
    rec.record_edge("halt_flag->live.scheduler", "received")
    body = client.get("/research/pipeline-edges?only_problems=true").json()
    states = {e["edge_id"]: e["state"] for e in body["edges"]}
    assert states["research.active_trade_plans->live.orchestrator"] == "missing"
    assert "halt_flag->live.scheduler" not in states  # healthy
    assert body["not_flowing"] == len(body["edges"])


def test_without_a_shared_root_it_says_recording_is_off_instead_of_inventing_state(service, monkeypatch) -> None:
    monkeypatch.delenv("VINU_EDGE_DATA_ROOT", raising=False)
    monkeypatch.delenv("VINU_STRATEGY_EVAL_DATA_ROOT", raising=False)
    rec.reset_for_tests()
    with TestClient(create_app(service)) as c:
        body = c.get("/research/pipeline-edges").json()
    assert body["recording_enabled"] is False
    assert _by_id(body)["portfolio.state->live.scheduler"]["state"] == "recording_disabled"
    assert body["not_flowing"] == 0  # recording being off is not an edge fault


def test_an_unreadable_manifest_does_not_500_the_route(client, monkeypatch) -> None:
    def _boom(*a, **k):
        raise FileNotFoundError("pipeline_edges.yaml not found")

    monkeypatch.setattr(pipeline_edges, "load_edges", _boom)
    rec.record_edge("halt_flag->live.scheduler", "received")
    body = client.get("/research/pipeline-edges").json()
    assert body["manifest"] == "unavailable" and "not found" in body["error"]
    assert [s["edge_id"] for s in body["states"]] == ["halt_flag->live.scheduler"]
