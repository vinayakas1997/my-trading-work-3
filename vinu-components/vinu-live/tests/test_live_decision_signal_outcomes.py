"""features-logic-checking F4: a live-fired signal trigger gets its outcome once its horizon has elapsed.

Worked example (horizon 20 closed bars): a trigger fires on bar 5 whose close is 100.0. The next 20 closes are 100.0
except one 108.0 (best), one 97.0 (worst) and the last one 103.0. Expected outcome, by hand:

    max_favorable_excursion = (108 - 100) / 100 =  0.08
    max_adverse_excursion   = ( 97 - 100) / 100 = -0.03
    return_at_horizon       = (103 - 100) / 100 =  0.03

These are the formulas the signal_evidence angle uses for its historical triggers.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from vinu_infra import pipeline_edge_recorder as rec
from vinu_live.config import LiveConfig
from vinu_live.live_decision.poller import CandleClosePoller
from vinu_live.live_decision.storage import LiveDecisionBackend

TF = 900
START = 1_700_000_000
TRIGGER_IDX = 5


@pytest.fixture(autouse=True)
def _edges(tmp_path, monkeypatch):
    monkeypatch.delenv("VINU_STRATEGY_EVAL_DATA_ROOT", raising=False)
    monkeypatch.setenv("VINU_EDGE_DATA_ROOT", str(tmp_path / "edges"))
    (tmp_path / "edges").mkdir()
    rec.reset_for_tests()
    yield
    rec.reset_for_tests()


@pytest.fixture
def poller():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    b = LiveDecisionBackend(path)
    p = CandleClosePoller(LiveConfig(), backend=b)
    p._http = MagicMock()
    yield p
    b.close()
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(path + suffix):
            os.unlink(path + suffix)


def _bars(n=30, *, best=108.0, worst=97.0, last=103.0) -> pd.DataFrame:
    closes = [100.0] * n
    closes[TRIGGER_IDX] = 100.0
    closes[TRIGGER_IDX + 3] = best
    closes[TRIGGER_IDX + 7] = worst
    if TRIGGER_IDX + 20 < n:
        closes[TRIGGER_IDX + 20] = last
    return pd.DataFrame({"bar_ts": [START + i * TF for i in range(n)], "close": closes})


def _trigger_time(idx=TRIGGER_IDX) -> str:
    return datetime.fromtimestamp(START + idx * TF, tz=timezone.utc).isoformat()


def _trigger(trigger_id="t1", idx=TRIGGER_IDX, granularity="15m", outcome=None) -> dict:
    return {
        "trigger_id": trigger_id, "symbol": "AAPL", "trigger_time": _trigger_time(idx),
        "granularity": granularity, "outcome_recorded_at": outcome,
    }


def _wire(poller, triggers, *, get_raises=None):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"triggers": triggers, "count": len(triggers)}
    if get_raises:
        poller._http.get = AsyncMock(side_effect=get_raises)
    else:
        poller._http.get = AsyncMock(return_value=resp)
    ok = MagicMock()
    ok.raise_for_status = MagicMock()
    poller._http.post = AsyncMock(return_value=ok)


def _resolve(poller, bars=None, timeframe="15m"):
    return asyncio.run(poller._resolve_signal_outcomes("AAPL", timeframe, _bars() if bars is None else bars))


def _posted(poller):
    return [(c.args[0], c.kwargs["json"]) for c in poller._http.post.call_args_list]


def test_the_outcome_is_computed_by_hand_and_posted(poller):
    _wire(poller, [_trigger()])
    assert _resolve(poller) == 1
    [(url, body)] = _posted(poller)
    assert url.endswith("/research/signal-evidence/t1/outcome")
    assert body["max_favorable_excursion"] == pytest.approx(0.08)
    assert body["max_adverse_excursion"] == pytest.approx(-0.03)
    assert body["return_at_horizon"] == pytest.approx(0.03)


def test_a_horizon_that_is_not_complete_yet_is_left_for_a_later_cycle(poller):
    _wire(poller, [_trigger()])
    # trigger on bar 5 needs bars 6..25 -> at least 26 bars; 25 bars is one short
    assert _resolve(poller, _bars(25)) == 0 and _posted(poller) == []
    assert _resolve(poller, _bars(26)) == 1


def test_an_already_resolved_trigger_is_not_posted_again(poller):
    _wire(poller, [_trigger(outcome="2026-10-04T15:00:00+00:00")])
    assert _resolve(poller) == 0 and _posted(poller) == []


def test_a_trigger_of_another_timeframe_is_left_alone(poller):
    _wire(poller, [_trigger(granularity="1d")])
    assert _resolve(poller, timeframe="15m") == 0 and _posted(poller) == []


def test_a_trigger_older_than_the_fetched_window_is_left_alone(poller):
    old = dict(_trigger(), trigger_time=datetime.fromtimestamp(START - 100 * TF, tz=timezone.utc).isoformat())
    _wire(poller, [old])
    assert _resolve(poller) == 0 and _posted(poller) == []


def test_several_triggers_are_resolved_independently(poller):
    _wire(poller, [_trigger("a", 5), _trigger("b", 3), _trigger("late", 20)])  # "late": only 9 bars of future
    assert _resolve(poller) == 2
    assert sorted(url.rsplit("/", 2)[-2] for url, _ in _posted(poller)) == ["a", "b"]


def test_a_malformed_trigger_row_is_skipped_not_fatal(poller):
    bad = {"trigger_id": "x", "trigger_time": "not a time", "granularity": "15m", "outcome_recorded_at": None}
    _wire(poller, [bad, _trigger("ok")])
    assert _resolve(poller) == 1


def test_disabled_makes_no_calls(poller):
    poller._config.live_decision_signal_outcomes_enabled = False
    _wire(poller, [_trigger()])
    assert _resolve(poller) == 0
    poller._http.get.assert_not_called()


def test_bad_or_missing_bars_are_a_noop(poller):
    _wire(poller, [_trigger()])
    assert asyncio.run(poller._resolve_signal_outcomes("AAPL", "15m", None)) == 0
    assert asyncio.run(poller._resolve_signal_outcomes("AAPL", "15m", pd.DataFrame())) == 0
    assert asyncio.run(poller._resolve_signal_outcomes("AAPL", "15m", pd.DataFrame({"close": [1.0]}))) == 0
    poller._http.get.assert_not_called()


def test_a_failed_read_never_raises_and_is_recorded_missing(poller):
    _wire(poller, [], get_raises=ConnectionError("research down"))
    assert _resolve(poller) == 0
    st = rec.resolve_edge_status_store().get_state("research.unresolved_triggers->live.poller")
    assert st["status"] == "missing" and "research down" in st["last_detail"]


def test_a_failed_post_never_raises_and_is_recorded_missing(poller):
    _wire(poller, [_trigger()])
    bad = MagicMock()
    bad.raise_for_status.side_effect = RuntimeError("HTTP 500")
    poller._http.post = AsyncMock(return_value=bad)
    assert _resolve(poller) == 0
    assert rec.resolve_edge_status_store().get_state("research.unresolved_triggers->live.poller")["status"] == "missing"


def test_a_good_read_is_recorded_received_and_a_wrong_shape_is_recorded_malformed(poller):
    _wire(poller, [_trigger()])
    _resolve(poller)
    edge = "research.unresolved_triggers->live.poller"
    assert rec.resolve_edge_status_store().get_state(edge)["status"] == "received"
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"rows": []}  # `triggers` renamed by the producer
    poller._http.get = AsyncMock(return_value=resp)
    _resolve(poller)
    st = rec.resolve_edge_status_store().get_state(edge)
    assert st["status"] == "malformed" and "triggers" in st["last_detail"]


def test_a_trigger_is_recorded_with_its_timeframe_as_granularity(poller):
    ok = MagicMock()
    ok.raise_for_status = MagicMock()
    poller._http.post = AsyncMock(return_value=ok)
    snapshot = {"close": 100.0}
    cond = [{"source": "live_indicators", "key": "adx_14", "operator": "gt", "value": 20}]
    asyncio.run(poller._record_signal_evidence_trigger("AAPL", cond, "trg1", START, snapshot, timeframe="1d"))
    assert poller._http.post.call_args.kwargs["json"]["granularity"] == "1d"
    asyncio.run(poller._record_signal_evidence_trigger("AAPL", cond, "trg2", START, snapshot))
    assert "granularity" not in poller._http.post.call_args.kwargs["json"]
