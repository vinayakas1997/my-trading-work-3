"""POST /agent/live-decision/run -- point 5's trigger route
(reverse-engineering/06-execution-handoff-and-architecture.md). Same
standalone-FastAPI + fake-service pattern test_routes_trace.py already
uses, not a full AgentService.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import vinu_agent.server.routes_live_decision as routes_live_decision


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes_live_decision.router, prefix="/agent")
    return TestClient(app), app


def _fake_service(run_team_once_return: dict):
    session_service = MagicMock()
    session_service.run_team_once.return_value = run_team_once_return
    return SimpleNamespace(session_service=session_service), session_service


class TestRunLiveDecisionRoute:
    def test_returns_503_when_service_unavailable(self, client) -> None:
        test_client, _app = client
        routes_live_decision._get_service = lambda: None
        resp = test_client.post("/agent/live-decision/run", json={"ticker": "aapl", "strategy_id": "sma_cross"})
        assert resp.status_code == 503

    def test_parses_the_decision_json_block_out_of_the_team_content(self, client) -> None:
        test_client, _app = client
        fake_svc, session_service = _fake_service({
            "status": "completed",
            "content": (
                "EXECUTE -- precondition held, evidence supports it.\n\n"
                "```json\n"
                '{"decision": "EXECUTE", "ticker": "AAPL", "strategy_id": "sma_cross", '
                '"precondition_held": true, "reasoning": "real evidence cited"}\n'
                "```"
            ),
        })
        routes_live_decision._get_service = lambda: fake_svc

        resp = test_client.post(
            "/agent/live-decision/run",
            json={"ticker": "aapl", "strategy_id": "sma_cross", "trigger_id": "trig_abc"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["ticker"] == "AAPL"
        assert body["decision"] == "EXECUTE"
        assert body["precondition_held"] is True

        # The team was actually run with the real ticker/strategy/trigger.
        session_service.run_team_once.assert_called_once()
        args, kwargs = session_service.run_team_once.call_args
        assert args[0] == "live_decision"
        assert "AAPL" in args[1]
        assert "sma_cross" in args[1]
        assert "trig_abc" in args[1]
        assert kwargs["tag"] == "AAPL-sma_cross"

    def test_team_not_completing_is_reported_as_an_error_not_a_crash(self, client) -> None:
        test_client, _app = client
        fake_svc, _session_service = _fake_service({"status": "failed", "content": ""})
        routes_live_decision._get_service = lambda: fake_svc

        resp = test_client.post("/agent/live-decision/run", json={"ticker": "AAPL", "strategy_id": "sma_cross"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "error"

    def test_missing_json_block_returns_empty_decision_not_a_crash(self, client) -> None:
        test_client, _app = client
        fake_svc, _session_service = _fake_service({"status": "completed", "content": "no json block here"})
        routes_live_decision._get_service = lambda: fake_svc

        resp = test_client.post("/agent/live-decision/run", json={"ticker": "AAPL", "strategy_id": "sma_cross"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["decision"] == ""
