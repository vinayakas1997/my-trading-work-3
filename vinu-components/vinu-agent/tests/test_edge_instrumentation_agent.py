"""Phase 3 extension: the runtime edge recorder wired into the vinu-agent consumption points -- the order guard's two
portfolio reads, the live-decision context tool's three reads, the reflection synthesis tool, the planner worker's
signal-evidence sync and evaluation-status context, and the screener client. Each site must record the right status
for each situation (the callers themselves cannot tell a failed read from an empty answer), and recording must never
change what the caller returns.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from vinu_infra import pipeline_edge_recorder as rec
from vinu_agent.broker.mandate import TradingMandate
from vinu_agent.broker.order_guard import OrderGuard
from vinu_agent.broker.daily_limits import DailyLimitStore
from vinu_agent.tools.get_live_decision_context_tool import GetLiveDecisionContextTool
from vinu_agent.tools.reflection_synthesis_tool import GetReflectionSynthesisTool
from vinu_agent.tools.screener_client import fetch_screener_top_tickers


@pytest.fixture(autouse=True)
def _recorder_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VINU_STRATEGY_EVAL_DATA_ROOT", raising=False)
    monkeypatch.setenv("VINU_EDGE_DATA_ROOT", str(tmp_path / "edges"))
    (tmp_path / "edges").mkdir()
    rec.reset_for_tests()
    yield
    rec.reset_for_tests()


def _status(edge_id):
    store = rec.resolve_edge_status_store()
    st = store.get_state(edge_id) if store else None
    return st["status"] if st else None


def _detail(edge_id):
    return rec.resolve_edge_status_store().get_state(edge_id)["last_detail"]


def _resp(body, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body
    if status >= 400:
        r.raise_for_status.side_effect = httpx.HTTPStatusError("err", request=None, response=r)
    else:
        r.raise_for_status.return_value = None
    return r


# ------------------------------------------------------------------ order guard

def _guard():
    mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False)
    return OrderGuard(mandate=mandate, broker=MagicMock(), daily_limit_store=DailyLimitStore(":memory:"))


E_RISK = "portfolio.risk_status->agent.order_guard"
E_STATE = "portfolio.state->agent.order_guard"


@pytest.mark.parametrize("answer,expected", [
    (_resp({"symbols": [{"symbol": "AAPL"}]}), "received"), (_resp({}), "empty"),
])
def test_risk_budget_read_is_recorded(answer, expected):
    with patch("vinu_agent.broker.order_guard.requests.get", return_value=answer):
        assert _guard()._fetch_risk_budget("AAPL") == answer.json.return_value
    assert _status(E_RISK) == expected


def test_a_failed_risk_budget_read_is_recorded_missing_and_still_fails_open():
    with patch("vinu_agent.broker.order_guard.requests.get", side_effect=ConnectionError("portfolio down")):
        assert _guard()._fetch_risk_budget("AAPL") is None
    assert _status(E_RISK) == "missing" and "portfolio down" in _detail(E_RISK)


@pytest.mark.parametrize("body,expected", [({"weights": [{"symbol": "MSFT", "target_weight": 0.1}]}, "received"), ({"weights": []}, "empty")])
def test_portfolio_state_read_in_the_concentration_check_is_recorded(body, expected):
    with patch("vinu_agent.broker.order_guard.requests.get", return_value=_resp(body)):
        result = _guard()._check_portfolio_concentration("AAPL", "buy", 100.0)
    assert result  # passes
    assert _status(E_STATE) == expected


def test_a_failed_portfolio_state_read_is_recorded_missing_and_the_order_is_still_allowed():
    with patch("vinu_agent.broker.order_guard.requests.get", side_effect=ConnectionError("down")):
        result = _guard()._check_portfolio_concentration("AAPL", "buy", 100.0)
    assert result and _status(E_STATE) == "missing"


# ------------------------------------------------------------------ live-decision context tool

E_UNCONF = "research.unconfirmed_moves->agent.live_decision_context"
E_NOTABLE = "reflection.notable_beliefs->agent.live_decision_context"
E_MAT = "maturity.status->agent.live_decision_context"


def test_fetch_json_without_an_edge_records_nothing_and_behaves_as_before():
    with patch("httpx.get", return_value=_resp({"a": 1})):
        assert GetLiveDecisionContextTool._fetch_json("http://x") == {"a": 1}
    with patch("httpx.get", side_effect=ConnectionError("x")):
        assert GetLiveDecisionContextTool._fetch_json("http://x") == {}
    assert rec.resolve_edge_status_store().list_states() == []


@pytest.mark.parametrize("body,key,expected", [
    ({"events": [{"e": 1}]}, "events", "received"), ({"events": []}, "events", "empty"), ({}, "events", "malformed"),
    ({"events": [{"e": 2}], "tier": "mature"}, None, "received"),
])
def test_fetch_json_records_received_or_empty(body, key, expected):
    with patch("httpx.get", return_value=_resp(body)):
        assert GetLiveDecisionContextTool._fetch_json("http://x", edge_id=E_UNCONF, non_empty_key=key) == body
    assert _status(E_UNCONF) == expected


def test_fetch_json_records_a_failed_read_as_missing_and_still_returns_empty_dict():
    with patch("httpx.get", return_value=_resp({}, 503)):
        assert GetLiveDecisionContextTool._fetch_json("http://x", edge_id=E_NOTABLE, non_empty_key="beliefs") == {}
    assert _status(E_NOTABLE) == "missing"
    with patch("httpx.get", side_effect=ConnectionError("reflection down")):
        assert GetLiveDecisionContextTool._fetch_json("http://x", edge_id=E_NOTABLE) == {}
    assert "reflection down" in _detail(E_NOTABLE)


def test_the_whole_tool_records_all_three_context_edges():
    tool = GetLiveDecisionContextTool()
    tool._services_config = {}
    tool._config = MagicMock(live_decision_maturity_scaling_enabled=True)

    def _get(url, **kw):
        if "/unconfirmed-moves" in url:
            return _resp({"events": [{"e": 1}]})
        if "/beliefs/notable" in url:
            return _resp({"beliefs": []})
        if "/maturity/status" in url:
            return _resp({"tier": "paper_only"})
        return _resp({})

    with patch("httpx.get", side_effect=_get), \
         patch("vinu_agent.tools.get_live_decision_context_tool._get_maturity_consultation_store", return_value=MagicMock()), \
         patch("vinu_agent.tools.get_live_decision_context_tool.GetSignalEvidenceTool") as ev:
        ev.return_value.execute.return_value = "{}"
        out = json.loads(tool.execute(ticker="AAPL", strategy_id="s"))
    assert out["status"] == "ok"
    assert (_status(E_UNCONF), _status(E_NOTABLE), _status(E_MAT)) == ("received", "empty", "received")


# ------------------------------------------------------------------ reflection synthesis tool

E_SYN = "reflection.synthesis->agent.idea_generator"


def _syn_tool():
    t = GetReflectionSynthesisTool()
    t._services_config = {"vinu_reflection": "http://r"}
    return t


@pytest.mark.parametrize("body,expected", [({"status": "ok", "synthesis": {"id": "x"}}, "received"), ({"status": "none"}, "received"), ({}, "malformed")])
def test_synthesis_read_is_recorded_and_returned_unchanged(body, expected):
    with patch("httpx.get", return_value=_resp(body)):
        assert json.loads(_syn_tool().execute()) == body
    assert _status(E_SYN) == expected


def test_a_failed_synthesis_read_is_recorded_missing_and_still_reports_the_error():
    with patch("httpx.get", side_effect=ConnectionError("down")):
        out = json.loads(_syn_tool().execute())
    assert out["status"] == "error" and _status(E_SYN) == "missing"


# ------------------------------------------------------------------ screener client

E_SCREEN = "screener.top->agent.planner_worker"


def test_screener_reads_are_recorded(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _resp({"top": [{"symbol": "AAPL"}]}))
    assert fetch_screener_top_tickers("http://s", "r") == ["AAPL"] and _status(E_SCREEN) == "received"
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _resp({"top": []}))
    assert fetch_screener_top_tickers("http://s", "r") == [] and _status(E_SCREEN) == "empty"
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _resp({}, 404))
    assert fetch_screener_top_tickers("http://s", "r") == [] and _status(E_SCREEN) == "empty"
    assert "no snapshot yet" in _detail(E_SCREEN)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: (_ for _ in ()).throw(ConnectionError("screener down")))
    assert fetch_screener_top_tickers("http://s", "r") == [] and _status(E_SCREEN) == "missing"


# ------------------------------------------------------------------ planner worker helpers

def test_signal_evidence_sync_records_missing_when_research_is_not_importable():
    import builtins
    from vinu_agent.agent.scheduler_workers import sync_signal_evidence_for_tickers

    real_import = builtins.__import__

    def fake(name, *a, **k):
        if name.startswith("vinu_research.signal_evidence_bridge"):
            raise ImportError("no vinu_research here")
        return real_import(name, *a, **k)

    with patch("builtins.__import__", side_effect=fake):
        assert sync_signal_evidence_for_tickers(["AAPL"]) is None
    assert _status("signal_evidence->hypothesis_registry") == "missing"
    assert "not importable" in _detail("signal_evidence->hypothesis_registry")


def test_signal_evidence_sync_records_received_and_missing_on_failure():
    from vinu_agent.agent.scheduler_workers import sync_signal_evidence_for_tickers

    with patch("vinu_research.signal_evidence_bridge.sync_signal_evidence_to_hypotheses", return_value={"AAPL": []}), \
         patch("vinu_agent.broker.research_link.get_hypothesis_registry"), patch("vinu_agent.broker.research_link.get_signal_evidence_store"):
        assert sync_signal_evidence_for_tickers(["AAPL"]) == {"AAPL": []}
    assert _status("signal_evidence->hypothesis_registry") == "received"
    with patch("vinu_research.signal_evidence_bridge.sync_signal_evidence_to_hypotheses", side_effect=RuntimeError("boom")), \
         patch("vinu_agent.broker.research_link.get_hypothesis_registry"), patch("vinu_agent.broker.research_link.get_signal_evidence_store"):
        assert sync_signal_evidence_for_tickers(["AAPL"]) is None
    assert _status("signal_evidence->hypothesis_registry") == "missing"


def test_evaluation_context_records_missing_when_the_shared_root_is_unset_and_empty_or_received_otherwise(tmp_path, monkeypatch):
    from vinu_agent.agent.scheduler_workers import _strategy_evaluation_context_for_ticker

    monkeypatch.delenv("VINU_STRATEGY_EVAL_DATA_ROOT", raising=False)
    assert _strategy_evaluation_context_for_ticker("AAPL") == ""
    assert _status("evaluation_status->agent.idea_prompt") == "missing"
    assert "VINU_STRATEGY_EVAL_DATA_ROOT" in _detail("evaluation_status->agent.idea_prompt")

    monkeypatch.setenv("VINU_STRATEGY_EVAL_DATA_ROOT", str(tmp_path / "ev"))
    (tmp_path / "ev").mkdir()
    assert _strategy_evaluation_context_for_ticker("AAPL") == ""
    assert _status("evaluation_status->agent.idea_prompt") == "empty"

    from vinu_infra.strategy_evaluation import StrategyEvaluationStore

    store = StrategyEvaluationStore(tmp_path / "ev" / "strategy_evaluation.db")
    store.write_step_result(artifact_id="art1", ticker="AAPL", step_name="risk_critic", step_order=1, verdict="PASS", reasoning="ok")
    assert store.list_status_for_ticker("AAPL")
    _strategy_evaluation_context_for_ticker("AAPL")
    st = rec.resolve_edge_status_store().get_state("evaluation_status->agent.idea_prompt")
    assert st["status"] == "received" and "1 row" in st["last_detail"]


# ---- layer C: the shape of what arrived is checked against the edge's contract

def test_a_risk_budget_with_a_wrong_shape_is_recorded_malformed_and_still_used():
    bad = {"symbols": "AAPL"}  # should be a list of per-symbol rows
    with patch("vinu_agent.broker.order_guard.requests.get", return_value=_resp(bad)):
        assert _guard()._fetch_risk_budget("AAPL") == bad
    assert _status(E_RISK) == "malformed" and "symbols" in _detail(E_RISK)


def test_a_notable_beliefs_answer_that_lost_its_key_is_recorded_malformed():
    edge = "reflection.notable_beliefs->agent.live_decision_context"
    with patch("httpx.get", return_value=_resp({"items": [1]})):
        assert GetLiveDecisionContextTool._fetch_json("http://x", edge_id=edge, non_empty_key="beliefs") == {"items": [1]}
    assert _status(edge) == "malformed" and "beliefs" in _detail(edge)
