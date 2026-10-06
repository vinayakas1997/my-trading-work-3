import json
import time

import pytest

from vinu_llm_gateway.store import QueueStore


def _row(priority=3, caller="t", purpose="research", key=None, **kw):
    return {"provider": "openai", "base_url": "http://x/v1", "model": "m", "max_tokens": 10, "request_json": "{}",
            "priority": priority, "caller": caller, "purpose": purpose, "deadline_at": time.time() + 100,
            "timeout_sec": 30, "max_attempts": 3, "dedupe_key": key, **kw}


@pytest.fixture
def store(tmp_path):
    s = QueueStore(tmp_path / "q.db")
    yield s
    s.close()


def _claim(store, now, worker="w"):
    return store.claim_next(worker, age_step_sec=1e9, now=now)


def test_most_urgent_first_then_first_in(store):
    low = store.enqueue(_row(5), now=100)[0]
    a = store.enqueue(_row(3), now=101)[0]
    b = store.enqueue(_row(3), now=102)[0]
    c = store.enqueue(_row(1), now=103)[0]
    assert [_claim(store, 110)["id"] for _ in range(4)] == [c, a, b, low]


def test_waiting_raises_priority_so_nothing_starves(store):
    old5 = store.enqueue(_row(5), now=0)[0]          # waited 4 steps => effective priority 1, and it is older
    store.enqueue(_row(1), now=1000)
    assert store.claim_next("w", age_step_sec=250, now=1001)["id"] == old5


def test_claim_marks_running_and_two_workers_never_share_a_row(store):
    store.enqueue(_row(), now=1)
    assert _claim(store, 2, "w1") is not None
    assert _claim(store, 2, "w2") is None


def test_retry_waits_for_its_time(store):
    rid = store.enqueue(_row(), now=1)[0]
    _claim(store, 2)
    store.retry_later(rid, "boom", 10, now=3)
    assert _claim(store, 5) is None
    assert _claim(store, 14)["attempts"] == 2


def test_identical_request_is_shared_while_in_flight(store):
    a, shared_a = store.enqueue(_row(key="k"))
    b, shared_b = store.enqueue(_row(key="k"))
    assert a == b and not shared_a and shared_b


def test_archive_moves_the_row_atomically(store):
    rid = store.enqueue(_row())[0]
    _claim(store, time.time())
    store.finish_ok(rid, json.dumps({"ok": 1}), 5, 7)
    assert store.archive(rid, "delivered")
    assert store.get(rid) is None
    h = store.history()
    assert len(h) == 1 and h[0]["archive_reason"] == "delivered" and h[0]["completion_tokens"] == 7
    assert not store.archive(rid, "delivered")      # second time: nothing to move, nothing duplicated
    assert len(store.history()) == 1


def test_sweep_expires_queued_rows_past_their_deadline(store):
    late = store.enqueue(_row(deadline_at=50), now=1)[0]
    moved = store.sweep(now=60)
    assert moved["expired"] == [late]
    assert store.get(late) is None
    assert store.history()[0]["archive_reason"] == "expired" and store.history()[0]["status"] == "expired"


def test_sweep_archives_an_answer_nobody_collected(store):
    rid = store.enqueue(_row(), now=1)[0]
    _claim(store, 2)
    store.finish_ok(rid, "{}", 1, 1, now=20)
    assert store.sweep(now=25, undelivered_after_sec=10)["undelivered"] == []      # not old enough yet
    assert store.sweep(now=40, undelivered_after_sec=10)["undelivered"] == [rid]
    assert store.history()[0]["archive_reason"] == "undelivered"


def test_a_lost_worker_gets_its_row_requeued(store):
    rid = store.enqueue(_row(), now=1)[0]
    _claim(store, 2)                                  # timeout_sec=30, grace 60
    assert store.sweep(now=2 + 30 + 61)["requeued"] == [rid]
    assert store.get(rid)["status"] == "queued"


def test_trim_keeps_the_numbers_drops_the_json(store):
    rid = store.enqueue(_row(request_json=json.dumps({"messages": ["secret prompt"]})))[0]
    _claim(store, time.time())
    store.finish_ok(rid, "{}", 1, 2)
    store.archive(rid, "delivered", now=0)
    assert store.trim_history(7, now=8 * 86400) == 1
    assert store.history()[0]["completion_tokens"] == 2
    assert store._conn.execute("select request_json from llm_history").fetchone()[0] == ""


def test_stats_show_who_waits(store):
    store.enqueue(_row(2, caller="live", purpose="risk_gate"), now=0)
    s = store.stats(now=30)
    assert s["queue"] == {"queued": 1} and s["waiting"][0]["caller"] == "live" and s["longest_wait_sec"] == 30
