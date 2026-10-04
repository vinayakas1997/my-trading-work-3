"""The first real HTTP surface for MaturityAssessor -- previously only
reachable in-process. `00-maturity-agentic-system-explanation.md` itself
named this exact route as the intended shape for a cross-service caller
with no in-process bridge (vinu-live's risk_gatekeeper/live_decision)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vinu_research.server.app import create_app


@pytest.fixture
def client(service):
    app = create_app(service)
    with TestClient(app) as test_client:
        yield test_client


def test_empty_strategy_store_reports_cold_start(client) -> None:
    resp = client.get("/research/maturity/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["tier"] == "cold_start"
    assert body["n_real_trades"] == 0


def test_response_carries_the_real_evidence_not_just_the_tier(client) -> None:
    resp = client.get("/research/maturity/status")
    body = resp.json()
    assert set(body.keys()) == {
        "tier", "n_real_trades", "n_paper_trading_days",
        "directional_accuracy", "regime_coverage",
    }


def test_answer_matches_the_edge_contract(client) -> None:
    """Layer B (producer side): the route validates against the contract its consumers are checked with."""
    from vinu_infra.edge_contracts import check_payload

    body = client.get("/research/maturity/status").json()
    assert check_payload("maturity.status->live.limits", body) == []
    assert check_payload("maturity.status->agent.live_decision_context", body) == []
