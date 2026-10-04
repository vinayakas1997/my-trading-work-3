"""The trade journal and loss causes for the live-decision loop (features-logic-checking): the whole story of a
closed trade in one record, worked by hand."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from vinu_live.config import LiveConfig
from vinu_live.live_decision.journal import build_journal, classify_live_exit, track_record
from vinu_live.live_decision.schema import LiveDecisionRecord
from vinu_live.live_decision.storage import (
    LiveDecisionBackend, close_position, open_position, record_live_decision, set_entry_price_if_missing,
)
from vinu_live.server.app import create_app


# ---------------------------------------------------------------- loss causes

@pytest.mark.parametrize("reason,ret,cause", [
    ("anything", 0.03, "expected_outcome"),
    ("rule_exit:stop_loss -- long stop", -0.05, "risk_error"),
    ("rule_exit:max_hold -- held 20 bars", -0.01, "time_decay"),
    ("rule_exit:max_hold -- held 20 bars", 0.02, "expected_outcome"),       # a win needs no cause, whatever closed it
    ("thesis no longer supported by the snapshot", -0.04, "prediction_error"),
    ("rule_exit:stop_loss -- long stop", None, "unknown_return"),           # return never recorded: not a loss
    ("x", float("nan"), "unknown_return"),
])
def test_loss_cause(reason, ret, cause):
    assert classify_live_exit(reason, ret) == cause


# --------------------------------------------------------------------- journal

@pytest.fixture
def backend(tmp_path):
    b = LiveDecisionBackend(str(tmp_path / "live_decision.db"))
    yield b
    b.close()


def _trade(backend, *, ticker="AAPL", strategy="s", trigger="trig", entry=100.0, exit_price=None, reason="x",
           entry_reasoning="evidence cited", opened=1000, closed=1000 + 36000):
    record_live_decision(backend, LiveDecisionRecord(
        ticker=ticker, strategy_id=strategy, trigger_id=trigger, bar_ts=opened, decision="EXECUTE",
        precondition_held=True, reasoning=entry_reasoning, raw_content=""))
    pos = open_position(backend, ticker=ticker, strategy_id=strategy, position_size=0.05, opened_bar_ts=opened,
                        trigger_id=trigger)
    set_entry_price_if_missing(backend, pos.id, entry)
    close_position(backend, pos.id, reason=reason, bar_ts=closed, exit_price=exit_price)
    return pos


def test_one_record_tells_why_it_was_opened_what_happened_and_why_it_closed(backend):
    pos = _trade(backend, trigger="t1", entry=100.0, exit_price=94.0, reason="thesis broke")
    record_live_decision(backend, LiveDecisionRecord(
        ticker="AAPL", strategy_id="s", trigger_id=f"pos_{pos.id}", bar_ts=20000, decision="HOLD",
        precondition_held=None, reasoning="still intact", raw_content=""))
    j = build_journal(backend)
    e = j["entries"][0]
    assert e["entry"]["reasoning"] == "evidence cited" and e["entry"]["precondition_held"] is True
    assert e["entry"]["entry_price"] == 100.0
    assert [r["decision"] for r in e["reviews"]] == ["HOLD"] and e["reviews"][0]["reasoning"] == "still intact"
    assert e["exit"]["exit_price"] == 94.0 and e["exit"]["return_pct"] == pytest.approx(-0.06)   # (94 - 100) / 100
    assert e["exit"]["held_seconds"] == 36000
    assert e["outcome_cause"] == "prediction_error"


def test_track_record_is_plain_counts_over_recorded_returns(backend):
    _trade(backend, trigger="a", exit_price=94.0, reason="agent exit")                          # -6%
    _trade(backend, trigger="b", exit_price=103.0, reason="agent exit")                         # +3%
    _trade(backend, trigger="c", exit_price=95.0, reason="rule_exit:stop_loss -- stop")         # -5%
    _trade(backend, trigger="d", exit_price=None, reason="agent exit")                          # return not recorded
    t = build_journal(backend)["track_record"]
    assert (t["n_closed"], t["n_with_return"], t["n_positive"], t["n_negative"]) == (4, 3, 1, 2)
    assert t["mean_return_pct"] == pytest.approx((-0.06 + 0.03 - 0.05) / 3, abs=1e-6)   # stored to 6 places
    assert t["worst_return_pct"] == pytest.approx(-0.06)
    assert t["by_cause"] == {"prediction_error": 1, "expected_outcome": 1, "risk_error": 1, "unknown_return": 1}


def test_open_positions_are_not_in_the_journal_and_filters_work(backend):
    _trade(backend, ticker="AAPL", trigger="a", exit_price=94.0)
    _trade(backend, ticker="MSFT", trigger="b", exit_price=94.0)
    open_position(backend, ticker="AAPL", strategy_id="s", position_size=0.05, opened_bar_ts=5, trigger_id="c")
    assert build_journal(backend)["count"] == 2
    assert [e["ticker"] for e in build_journal(backend, ticker="MSFT")["entries"]] == ["MSFT"]


def test_empty_track_record_has_no_invented_numbers():
    t = track_record([])
    assert t["n_closed"] == 0 and t["mean_return_pct"] is None and t["worst_return_pct"] is None


# ----------------------------------------------------------------------- route

def test_journal_route_and_decisions_route_carry_it(tmp_path):
    config = LiveConfig(data_root=tmp_path)
    b = LiveDecisionBackend(str(tmp_path / "live_decision.db"))
    _trade(b, trigger="a", exit_price=94.0, reason="agent exit")
    b.close()
    with patch("vinu_live.server.app.load_config", return_value=config):
        client = TestClient(create_app())
        j = client.get("/live/journal").json()
        assert j["count"] == 1 and j["entries"][0]["outcome_cause"] == "prediction_error"
        d = client.get("/live/decisions/AAPL/s").json()
        assert d["track_record"]["n_closed"] == 1 and d["track_record"]["n_negative"] == 1
