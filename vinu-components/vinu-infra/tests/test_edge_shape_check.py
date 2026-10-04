"""Layer C of routing-find-and-fix/01-plan.md: the edge recorder checks the SHAPE of a received payload against the
edge's contract (edge_contracts.py) and records `malformed` when it does not match.

Pinned here because the recorder sits next to order flow: the check is observe-only (a failure of the check itself
never changes an observation), only a `received` observation is checked, and an edge with no contract or a caller
that passes no payload behaves exactly as before.
"""

from __future__ import annotations

import sqlite3

import pytest

from vinu_infra import edge_contracts
from vinu_infra import pipeline_edge_recorder as rec
from vinu_infra.pipeline_edges import Edge

EDGE = "portfolio.state->live.scheduler"
GOOD = {"status": "ok", "weights": [{"name": "a", "symbol": "AAPL", "target_weight": 1.0}]}


@pytest.fixture
def store():
    s = rec.EdgeStatusStore(":memory:")
    yield s
    s.close()


def _state(store, edge=EDGE):
    return store.get_state(edge)


def test_a_matching_payload_stays_received(store):
    rec.record_edge(EDGE, "received", "ok", store=store, payload=GOOD)
    assert _state(store)["status"] == "received"


def test_a_payload_missing_a_required_field_is_recorded_malformed_with_the_reason(store):
    rec.record_edge(EDGE, "received", store=store, payload={"status": "ok"})
    st = _state(store)
    assert st["status"] == "malformed" and "weights" in st["last_detail"]
    assert st["n_malformed"] == 1 and st["n_received"] == 0 and st["last_ok"] is None


def test_a_wrong_type_is_malformed_and_names_the_path(store):
    rec.record_edge(EDGE, "received", store=store, payload={"weights": [{"target_weight": "lots"}]})
    st = _state(store)
    assert st["status"] == "malformed" and "weights.0.target_weight" in st["last_detail"]


def test_the_callers_own_detail_is_kept_after_the_problems(store):
    rec.record_edge(EDGE, "received", "AAPL", store=store, payload={})
    assert _state(store)["last_detail"].endswith("| AAPL")


def test_many_problems_are_summarised_not_dumped(store):
    bad = {"weights": [{"target_weight": "x"}, {"target_weight": "y"}, {"target_weight": "z"}, {"target_weight": "w"}]}
    rec.record_edge(EDGE, "received", store=store, payload=bad)
    assert "more)" in _state(store)["last_detail"]


def test_an_empty_answer_must_still_have_the_right_shape(store):
    rec.record_edge(EDGE, "empty", store=store, payload={"status": "empty", "weights": []})
    assert _state(store)["status"] == "empty"
    # a renamed key must not hide behind "nothing there"
    rec.record_edge(EDGE, "empty", store=store, payload={"status": "empty", "wights": []})
    assert _state(store)["status"] == "malformed"


def test_missing_and_stale_are_never_checked(store):
    rec.record_edge(EDGE, "missing", "down", store=store, payload=None)
    assert _state(store)["status"] == "missing"
    rec.record_edge(EDGE, "stale", "old", store=store, payload={})
    assert _state(store)["status"] == "stale"


def test_no_payload_means_no_check(store):
    rec.record_edge(EDGE, "received", store=store)
    assert _state(store)["status"] == "received"


def test_an_edge_without_a_contract_is_never_malformed(store):
    rec.record_edge("halt_flag->live.scheduler", "received", store=store, payload={"anything": 1})
    assert _state(store, "halt_flag->live.scheduler")["status"] == "received"


def test_a_failing_check_leaves_the_observation_unchanged(store, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("check exploded")

    monkeypatch.setattr(edge_contracts, "check_payload", boom)
    rec.record_edge(EDGE, "received", "kept", store=store, payload={})
    st = _state(store)
    assert st["status"] == "received" and st["last_detail"] == "kept"


def test_malformed_then_good_is_logged_as_a_status_change(store):
    rec.record_edge(EDGE, "received", store=store, payload={})
    rec.record_edge(EDGE, "received", store=store, payload=GOOD)
    events = store.list_events(EDGE)
    assert [e["to_status"] for e in events] == ["received", "malformed"]  # newest first
    assert _state(store)["last_ok"] is not None


def _edge(id_=EDGE):
    return Edge(
        id=id_, producer_service="a", producer_files=["a.py"], producer_defines=["x"],
        consumer_service="b", consumer_files=["b.py"], consumer_references=["y"],
        empty_ok=True, instrumented=True,
    )


def test_the_flow_report_flags_a_malformed_edge(store):
    rec.record_edge(EDGE, "received", store=store, payload={})
    rows = rec.edges_flow_report([_edge()], store)
    assert rows[0]["state"] == "malformed" and rows[0]["counts"]["malformed"] == 1
    assert rec.not_flowing(rows) == rows


def test_the_flow_report_is_healthy_again_after_a_good_payload(store):
    rec.record_edge(EDGE, "received", store=store, payload={})
    rec.record_edge(EDGE, "received", store=store, payload=GOOD)
    assert rec.edges_flow_report([_edge()], store)[0]["state"] == "flowing"


def test_an_old_database_without_the_counter_is_upgraded_on_open(tmp_path):
    path = tmp_path / "pipeline_edges.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE edge_state (
            edge_id TEXT PRIMARY KEY, status TEXT NOT NULL, first_seen REAL NOT NULL, last_seen REAL NOT NULL,
            last_ok REAL, last_change REAL NOT NULL, n_received INTEGER NOT NULL DEFAULT 0,
            n_empty INTEGER NOT NULL DEFAULT 0, n_stale INTEGER NOT NULL DEFAULT 0,
            n_missing INTEGER NOT NULL DEFAULT 0, last_detail TEXT NOT NULL DEFAULT '');
        INSERT INTO edge_state VALUES ('old->edge', 'received', 1, 2, 2, 1, 5, 0, 0, 0, '');
    """)
    conn.commit()
    conn.close()
    s = rec.EdgeStatusStore(path)
    try:
        assert s.get_state("old->edge")["n_malformed"] == 0 and s.get_state("old->edge")["n_received"] == 5
        rec.record_edge(EDGE, "received", store=s, payload={})
        assert s.get_state(EDGE)["n_malformed"] == 1
    finally:
        s.close()


def test_record_edge_still_never_raises_on_a_hostile_payload(store):
    class Hostile:
        def __getattr__(self, name):
            raise RuntimeError("no")

    rec.record_edge(EDGE, "received", store=store, payload=Hostile())
    assert _state(store)["status"] == "malformed"
