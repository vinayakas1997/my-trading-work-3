"""Route-level test for POST /portfolio/evaluate-batch (Phase 2, New-talk-
agents/new-thinking/new-restructure/phases/phase-2-funding-mechanics/).
vinu-portfolio's app.py has no dependency-injection hook (unlike
vinu-research's set_tools() pattern) -- `_service = PortfolioService()` is
a closure-local instance built fresh inside create_app(). Patching the
PortfolioService CLASS method before create_app() runs still works, since
Python looks up the method on the class at call time, not at bind time.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from vinu_portfolio.server.app import create_app
from vinu_portfolio.service import PortfolioService


def test_evaluate_batch_calls_build_portfolio_with_shaped_candidates() -> None:
    fake_result = {
        "status": "ok", "n_strategies": 1, "strategies": [], "correlation_matrix": None,
        "weights": [{"name": "cand", "artifact_id": "art_1", "target_weight": 0.3, "is_candidate": True}],
    }
    with patch.object(PortfolioService, "build_portfolio", new=AsyncMock(return_value=fake_result)) as mock_build:
        app = create_app()
        client = TestClient(app)
        resp = client.post(
            "/portfolio/evaluate-batch",
            json={"candidates": [{"artifact_id": "art_1", "name": "cand", "symbol": "AAPL"}]},
        )

    assert resp.status_code == 200
    assert resp.json() == fake_result
    mock_build.assert_awaited_once()
    _, kwargs = mock_build.call_args
    shaped = kwargs["extra_candidates"]
    assert shaped == [{
        "name": "cand", "kind": "llm_python", "symbol": "AAPL",
        "artifact_id": "art_1", "weights_source": "artifact:art_1", "is_candidate": True,
    }]


def test_evaluate_batch_daily_allocation_flag_routes_to_compute_daily_allocation() -> None:
    with patch.object(
        PortfolioService, "compute_daily_allocation", new=AsyncMock(return_value={"status": "ok"})
    ) as mock_daily:
        app = create_app()
        client = TestClient(app)
        resp = client.post(
            "/portfolio/evaluate-batch",
            json={
                "candidates": [{"artifact_id": "art_1", "name": "cand"}],
                "daily_allocation": True,
            },
        )

    assert resp.status_code == 200
    mock_daily.assert_awaited_once()


def test_evaluate_batch_empty_candidates_is_422() -> None:
    app = create_app()
    client = TestClient(app)
    resp = client.post("/portfolio/evaluate-batch", json={"candidates": []})
    assert resp.status_code == 422
