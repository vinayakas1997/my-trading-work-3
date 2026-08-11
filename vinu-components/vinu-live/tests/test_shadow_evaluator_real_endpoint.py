"""Real cross-service integration test for ShadowEvaluator's performance
fetch -- Phase 4 (New-talk-agents/new-thinking/new-restructure/phases/
phase-4-live-shadow-fix/). The existing test_shadow_evaluator.py tests
mock evaluator._http.get entirely, which can't catch a URL/route mismatch
between the two services (exactly the kind of bug this phase fixed
elsewhere in this session -- prior findings recorded in vinu-agent's
skills/live-safety/SKILL.md). This runs ShadowEvaluator's REAL httpx call
against vinu-agent's REAL routes_broker.py FastAPI app, in-process via
httpx.ASGITransport (no live server needed, but the real ASGI route
handler code runs, not a mock).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from vinu_live.shadow_evaluator import ShadowEvaluator


def _real_agent_app() -> FastAPI:
    import vinu_agent.server.routes_broker as routes_broker
    app = FastAPI()
    app.include_router(routes_broker.router, prefix="/agent")
    return app


@pytest.fixture
def evaluator_against_real_agent_app():
    import httpx
    from vinu_agent.broker.performance_store import get_store

    get_store().clear()
    app = _real_agent_app()
    evaluator = ShadowEvaluator(agent_api_url="http://testserver")
    evaluator._http = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver",
    )
    yield evaluator
    get_store().clear()


@pytest.mark.asyncio
async def test_shadow_fetch_reaches_the_real_endpoint_not_mocked(evaluator_against_real_agent_app) -> None:
    """The literal regression test: before this phase's fix, this call
    404'd (the endpoint's own module claimed it didn't exist -- see
    shadow_evaluator.py's now-removed stale comment). Against the real
    app, it must now succeed and return the recorded returns."""
    evaluator = evaluator_against_real_agent_app
    from vinu_agent.broker.performance_store import get_store

    get_store().record_daily_returns("art-real-1", [0.01, 0.02, -0.005, 0.015, 0.01, 0.02])

    sharpe = await evaluator._fetch_paper_sharpe("art-real-1")

    assert sharpe is not None
    assert sharpe > 0  # positive mean returns -> positive Sharpe


@pytest.mark.asyncio
async def test_shadow_fetch_unknown_artifact_is_insufficient_data_not_an_error(
    evaluator_against_real_agent_app,
) -> None:
    evaluator = evaluator_against_real_agent_app
    sharpe = await evaluator._fetch_paper_sharpe("art-never-recorded")
    assert sharpe is None  # ShadowEvaluator's own insufficient_data signal


@pytest.mark.asyncio
async def test_evaluate_all_promotes_via_the_real_endpoint_end_to_end(evaluator_against_real_agent_app) -> None:
    """End-to-end (03-test.md): a BENCHING artifact with real recorded
    paper returns, run through evaluate_all()'s UNMODIFIED promotion
    logic against the real endpoint. list_benching_artifacts/promote
    still mocked here (a separate real service, vinu-research) -- only
    the performance fetch, the actual bug this phase closes, is real."""
    from unittest.mock import AsyncMock, patch
    from vinu_agent.broker.performance_store import get_store

    get_store().record_daily_returns(
        "art-real-2",
        [0.02, 0.015, -0.005, 0.01, 0.025, 0.0, 0.018],  # same shape as the existing mocked test
    )

    evaluator = evaluator_against_real_agent_app
    artifacts = [{"artifact_id": "art-real-2", "name": "real-endpoint-strategy", "initial_sharpe": 1.5}]

    async def fake_list_benching(self):
        return artifacts

    with patch.object(ShadowEvaluator, "_list_benching_artifacts", fake_list_benching):
        with patch.object(evaluator, "_promote_artifact", new=AsyncMock()) as mock_promote:
            results = await evaluator.evaluate_all()

    assert len(results) == 1
    assert results[0]["status"] == "promoted"
    assert results[0]["promoted"] is True
    mock_promote.assert_awaited_once_with("art-real-2")
