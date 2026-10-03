"""Phase 3 of the-inconsistencies-v2 plan: the runtime edge recorder and the
"what is not flowing" report (pipeline_edge_recorder.py).

Properties pinned here, because this module sits next to order flow:
record_edge never raises and is a silent no-op without a configured root; a
healthy edge costs a counter bump and no log row; only status CHANGES are
logged; the report distinguishes "not wired" / "not instrumented" /
"never seen" from "stopped flowing".
"""

from __future__ import annotations

import pytest

from vinu_infra import pipeline_edge_recorder as rec
from vinu_infra.pipeline_edges import Edge


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for var in ("VINU_EDGE_DATA_ROOT", "VINU_STRATEGY_EVAL_DATA_ROOT"):
        monkeypatch.delenv(var, raising=False)
    rec.reset_for_tests()
    yield
    rec.reset_for_tests()


@pytest.fixture
def store():
    return rec.EdgeStatusStore(":memory:")


def _edge(id_="a->b", *, status="wired", empty_ok=True, instrumented=True, stale_after_sec=None, gap_ref="") -> Edge:
    return Edge(
        id=id_, producer_service="a", producer_files=["a.py"], producer_defines=["x"],
        consumer_service="b", consumer_files=["b.py"], consumer_references=["y"],
        empty_ok=empty_ok, status=status, gap_ref=gap_ref,
        instrumented=instrumented, stale_after_sec=stale_after_sec,
    )


# ------------------------------------------------------------------ the store

def test_first_observation_creates_state_and_one_event(store):
    store.record("e", "received", "ok", now=100.0)
    s = store.get_state("e")
    assert (s["status"], s["n_received"], s["first_seen"], s["last_seen"], s["last_ok"]) == ("received", 1, 100.0, 100.0, 100.0)
    ev = store.list_events("e")
    assert len(ev) == 1 and ev[0]["from_status"] is None and ev[0]["to_status"] == "received"


def test_a_healthy_edge_bumps_counters_but_writes_no_new_log_rows(store):
    for t in (100.0, 200.0, 300.0):
        store.record("e", "received", now=t)
    s = store.get_state("e")
    assert s["n_received"] == 3 and s["last_seen"] == 300.0 and s["last_change"] == 100.0
    assert len(store.list_events("e")) == 1


def test_only_status_changes_are_logged_and_last_change_moves(store):
    store.record("e", "received", now=100.0)
    store.record("e", "missing", "HTTP 500", now=200.0)
    store.record("e", "missing", "HTTP 500", now=300.0)
    store.record("e", "received", now=400.0)
    ev = list(reversed(store.list_events("e")))
    assert [(x["from_status"], x["to_status"]) for x in ev] == [(None, "received"), ("received", "missing"), ("missing", "received")]
    s = store.get_state("e")
    assert s["n_missing"] == 2 and s["n_received"] == 2 and s["last_change"] == 400.0


def test_last_ok_only_advances_on_received(store):
    store.record("e", "received", now=100.0)
    store.record("e", "missing", now=200.0)
    store.record("e", "empty", now=300.0)
    store.record("e", "stale", now=400.0)
    s = store.get_state("e")
    assert s["last_ok"] == 100.0 and s["last_seen"] == 400.0
    assert (s["n_received"], s["n_missing"], s["n_empty"], s["n_stale"]) == (1, 1, 1, 1)


def test_an_edge_that_never_succeeded_has_no_last_ok(store):
    store.record("e", "missing", now=100.0)
    assert store.get_state("e")["last_ok"] is None


def test_unknown_status_is_rejected_by_the_store(store):
    with pytest.raises(ValueError):
        store.record("e", "fine")


def test_detail_is_truncated(store):
    store.record("e", "missing", "x" * 5000, now=1.0)
    assert len(store.get_state("e")["last_detail"]) == 500


def test_event_log_is_capped_per_edge(store, monkeypatch):
    monkeypatch.setattr(rec, "_MAX_EVENTS_PER_EDGE", 5)
    for i in range(20):
        store.record("e", "received" if i % 2 == 0 else "missing", now=float(i))
    assert len(store.list_events("e", limit=100)) == 5
    store.record("other", "received", now=1.0)
    assert len(store.list_events("other")) == 1  # the cap is per edge


# ------------------------------------------------------------------ record_edge never raises

def test_record_edge_is_a_silent_noop_without_a_configured_root():
    rec.record_edge("e", "received")  # must not raise, must not create anything
    assert rec.resolve_edge_status_store() is None


def test_record_edge_writes_to_the_shared_eval_root(monkeypatch, tmp_path):
    monkeypatch.setenv("VINU_STRATEGY_EVAL_DATA_ROOT", str(tmp_path))
    rec.record_edge("e", "received", "hello")
    assert (tmp_path / "pipeline_edges.db").exists()
    assert rec.resolve_edge_status_store().get_state("e")["last_detail"] == "hello"


def test_edge_root_takes_precedence_over_the_eval_root(monkeypatch, tmp_path):
    (tmp_path / "eval").mkdir()
    (tmp_path / "edge").mkdir()
    monkeypatch.setenv("VINU_STRATEGY_EVAL_DATA_ROOT", str(tmp_path / "eval"))
    monkeypatch.setenv("VINU_EDGE_DATA_ROOT", str(tmp_path / "edge"))
    rec.record_edge("e", "received")
    assert (tmp_path / "edge" / "pipeline_edges.db").exists()
    assert not (tmp_path / "eval" / "pipeline_edges.db").exists()


def test_fallback_root_is_used_only_when_no_env_root_is_set(tmp_path, monkeypatch):
    fallback = tmp_path / "fallback"
    fallback.mkdir()
    rec.resolve_edge_status_store(fallback).record("e", "received", now=1.0)
    assert (fallback / "pipeline_edges.db").exists()

    env_root = tmp_path / "env"
    env_root.mkdir()
    monkeypatch.setenv("VINU_EDGE_DATA_ROOT", str(env_root))
    rec.resolve_edge_status_store(fallback).record("e2", "received", now=1.0)  # env wins over the fallback
    assert (env_root / "pipeline_edges.db").exists()
    assert rec.resolve_edge_status_store(fallback).get_state("e") is None  # and it is a different database


def test_record_edge_swallows_an_invalid_status(store):
    rec.record_edge("e", "banana", store=store)  # must not raise
    assert store.get_state("e") is None


def test_record_edge_swallows_a_storage_failure():
    class _Broken:
        def record(self, *a, **k):
            raise RuntimeError("disk full")

    rec.record_edge("e", "received", store=_Broken())  # must not raise


# ------------------------------------------------------------------ the report

NOW = 10_000.0


def _report(edges, store):
    return {r["edge_id"]: r for r in rec.edges_flow_report(edges, store, now=NOW)}


def test_a_known_gap_is_reported_as_such_not_as_broken(store):
    r = _report([_edge("g", status="gap", gap_ref="audit A1", instrumented=False)], store)["g"]
    assert r["state"] == "known_gap" and r["gap_ref"] == "audit A1"


def test_uninstrumented_silence_is_not_called_broken(store):
    assert _report([_edge("u", instrumented=False)], store)["u"]["state"] == "not_instrumented"


def test_instrumented_but_never_recorded_is_never_seen(store):
    assert _report([_edge("n")], store)["n"]["state"] == "never_seen"


def test_a_fresh_received_edge_is_flowing(store):
    store.record("a->b", "received", now=NOW - 5)
    r = _report([_edge()], store)["a->b"]
    assert r["state"] == "flowing" and r["last_seen_age_sec"] == 5.0 and r["counts"]["received"] == 1


def test_an_old_observation_is_stale_only_when_the_edge_declares_a_limit(store):
    store.record("a->b", "received", now=NOW - 7200)
    assert _report([_edge(stale_after_sec=3600)], store)["a->b"]["state"] == "stale"
    assert _report([_edge(stale_after_sec=None)], store)["a->b"]["state"] == "flowing"
    assert _report([_edge(stale_after_sec=86400)], store)["a->b"]["state"] == "flowing"


def test_a_recorded_failure_is_missing_and_shows_since_when(store):
    store.record("a->b", "received", now=NOW - 900)
    store.record("a->b", "missing", "HTTP 500", now=NOW - 300)
    r = _report([_edge()], store)["a->b"]
    assert r["state"] == "missing" and r["last_detail"] == "HTTP 500"
    assert r["since_age_sec"] == 300.0 and r["last_ok_age_sec"] == 900.0


def test_empty_is_healthy_only_where_the_edge_allows_empty(store):
    store.record("a->b", "empty", now=NOW - 5)
    assert _report([_edge(empty_ok=True)], store)["a->b"]["state"] == "flowing"
    assert _report([_edge(empty_ok=False)], store)["a->b"]["state"] == "empty"


def test_a_consumer_reported_stale_is_stale(store):
    store.record("a->b", "stale", "price 200h old", now=NOW - 5)
    assert _report([_edge()], store)["a->b"]["state"] == "stale"


def test_not_flowing_lists_only_what_needs_attention(store):
    store.record("ok", "received", now=NOW - 1)
    store.record("bad", "missing", now=NOW - 1)
    edges = [_edge("ok"), _edge("bad"), _edge("g", status="gap", gap_ref="x", instrumented=False),
             _edge("u", instrumented=False), _edge("n")]
    flagged = {r["edge_id"]: r["state"] for r in rec.not_flowing(rec.edges_flow_report(edges, store, now=NOW))}
    assert flagged == {"bad": "missing", "n": "never_seen"}


def test_report_works_with_no_store_at_all():
    rows = rec.edges_flow_report([_edge("n"), _edge("u", instrumented=False)], None, now=NOW)
    assert {r["edge_id"]: r["state"] for r in rows} == {"n": "recording_disabled", "u": "not_instrumented"}
    assert rec.not_flowing(rows) == []  # nothing is recorded, so nothing can be called broken
