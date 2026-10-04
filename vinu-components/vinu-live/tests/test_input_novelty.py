"""v2 B1: input-novelty check -- the pure ratio, and the poller wiring (opt-in, observe-only, passed to the agent when high)."""

from __future__ import annotations

import asyncio
import random

import pytest

from vinu_infra import pipeline_edge_recorder as rec
from vinu_live.config import LiveConfig
from vinu_live.live_decision.novelty import novelty_ratio
from vinu_live.live_decision.poller import CandleClosePoller
from vinu_live.live_decision.storage import LiveDecisionBackend, list_snapshots, record_live_snapshot

EDGE = "live_decision.input_novelty->live.poller"


def _ref(n=60, seed=1):
    rnd = random.Random(seed)
    return [{"a": rnd.gauss(0, 1), "b": rnd.gauss(10, 2), "c": rnd.gauss(-1, 0.5)} for _ in range(n)]


def test_a_typical_vector_has_a_ratio_near_one_and_is_not_flagged():
    r = novelty_ratio({"a": 0.1, "b": 10.2, "c": -1.0}, _ref())
    assert r["status"] == "ok" and r["ratio"] < 1.5 and not r["novelty_high"] and r["n_features"] == 3


def test_an_unusual_vector_is_flagged_high():
    r = novelty_ratio({"a": 8.0, "b": 40.0, "c": 6.0}, _ref())
    assert r["status"] == "ok" and r["ratio"] > 2.0 and r["novelty_high"]


def test_the_threshold_is_respected():
    cur = {"a": 3.0, "b": 10.0, "c": -1.0}
    low = novelty_ratio(cur, _ref(), ratio_threshold=100.0)
    assert low["ratio"] == pytest.approx(novelty_ratio(cur, _ref(), ratio_threshold=0.1)["ratio"]) and not low["novelty_high"]
    assert novelty_ratio(cur, _ref(), ratio_threshold=0.1)["novelty_high"]


def test_too_little_history_is_unknown_not_novel():
    r = novelty_ratio({"a": 99.0, "b": 99.0, "c": 99.0}, _ref(10))
    assert r["status"] == "insufficient_reference" and r["ratio"] is None and r["novelty_high"] is False


def test_constant_or_sparse_features_are_dropped_and_none_values_do_not_crash():
    ref = [{"a": i * 0.37 % 5.1, "const": 1.0, "sparse": (1.0 if i == 0 else None), "s": "x"} for i in range(50)]
    r = novelty_ratio({"a": 3.0, "const": 1.0, "sparse": 1.0, "s": "x", "bad": float("nan")}, ref)
    assert r["status"] == "ok" and r["n_features"] == 1
    assert novelty_ratio({"const": 1.0}, ref)["status"] == "insufficient_reference"


# ------------------------------------------------------------------ poller wiring

@pytest.fixture(autouse=True)
def _edges(tmp_path, monkeypatch):
    monkeypatch.delenv("VINU_STRATEGY_EVAL_DATA_ROOT", raising=False)
    monkeypatch.setenv("VINU_EDGE_DATA_ROOT", str(tmp_path / "edges"))
    (tmp_path / "edges").mkdir()
    rec.reset_for_tests()
    yield
    rec.reset_for_tests()


def _poller(tmp_path, **cfg):
    config = LiveConfig(data_root=tmp_path, live_decision_novelty_min_reference=30, **cfg)
    return CandleClosePoller(config=config, backend=LiveDecisionBackend(str(tmp_path / "ld.db")))


def _seed(poller, n=60):
    for row in _ref(n):
        record_live_snapshot(poller._backend, symbol="AAPL", angle_name="live_indicators", granularity="1d", snapshot_data=row)


def _state():
    s = rec.resolve_edge_status_store()
    return s.get_state(EDGE) if s else None


def test_disabled_by_default_does_nothing(tmp_path):
    p = _poller(tmp_path)
    _seed(p)
    p._check_novelty("AAPL", "1d", {"a": 50.0, "b": 99.0, "c": 9.0})
    assert p._novelty == {} and _state() is None
    assert list_snapshots(p._backend, "AAPL", "live_novelty") == []


def test_enabled_records_the_result_and_the_edge_and_remembers_high_novelty(tmp_path):
    p = _poller(tmp_path, live_decision_novelty_enabled=True)
    _seed(p)
    p._check_novelty("AAPL", "1d", {"a": 50.0, "b": 99.0, "c": 9.0})
    assert p._novelty["AAPL"]["novelty_high"] is True
    assert _state()["status"] == "received"
    assert list_snapshots(p._backend, "AAPL", "live_novelty")[0].snapshot_data["novelty_high"] is True


def test_thin_history_records_the_edge_as_empty(tmp_path):
    p = _poller(tmp_path, live_decision_novelty_enabled=True)
    p._check_novelty("AAPL", "1d", {"a": 1.0})
    assert _state()["status"] == "empty" and p._novelty["AAPL"]["novelty_high"] is False


def test_a_failing_check_never_raises_and_is_recorded_missing(tmp_path, monkeypatch):
    p = _poller(tmp_path, live_decision_novelty_enabled=True)
    monkeypatch.setattr("vinu_live.live_decision.poller.list_snapshots", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db gone")))
    p._check_novelty("AAPL", "1d", {"a": 1.0})
    assert _state()["status"] == "missing" and "db gone" in _state()["last_detail"]


class _Resp:
    def raise_for_status(self): pass
    def json(self): return {"decision": "SKIP", "reasoning": "r", "precondition_held": None, "content": ""}


def _trigger(p):
    sent = []

    async def post(url, json=None, **k):
        sent.append(json)
        return _Resp()

    p._http.post = post
    asyncio.run(p._trigger_live_decision("AAPL", "s1", 1, "t1"))
    return sent[0]


def test_high_novelty_is_passed_to_the_agent_and_normal_novelty_is_not(tmp_path):
    p = _poller(tmp_path, live_decision_novelty_enabled=True)
    assert "novelty" not in _trigger(p)
    p._novelty["AAPL"] = {"status": "ok", "ratio": 3.1, "novelty_high": False}
    assert "novelty" not in _trigger(p)
    p._novelty["AAPL"] = {"status": "ok", "ratio": 3.1, "novelty_high": True}
    assert _trigger(p)["novelty"]["ratio"] == 3.1


def test_novelty_answers_match_the_edge_contract():
    """Layer B (producer side): both the normal and the not-enough-history answer validate against the contract."""
    from vinu_infra.edge_contracts import check_payload

    assert check_payload(EDGE, novelty_ratio({"a": 0.1, "b": 10.2, "c": -1.0}, _ref())) == []
    assert check_payload(EDGE, novelty_ratio({"a": 0.1}, _ref(n=3))) == []
