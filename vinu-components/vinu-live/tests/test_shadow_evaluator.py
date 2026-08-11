from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from vinu_live.shadow_evaluator import ShadowEvaluator


class MockResponse:
    def __init__(self, status_code: int, json_data: object) -> None:
        self.status_code = status_code
        self._json = json_data

    def json(self):
        # Synchronous, matching the real httpx.Response.json() -- this
        # mock used to declare `async def json()`, which matched a real
        # bug in shadow_evaluator.py (`await resp.json()`) instead of
        # catching it. See test_shadow_evaluator_real_endpoint.py, which
        # runs the real (non-mocked) code path and caught the mismatch.
        return self._json


@pytest.fixture
def evaluator():
    return ShadowEvaluator(research_api_url="http://test-research:8087", agent_api_url="http://test-agent:8086")


def _mock_get(artifacts_list: list[dict], returns_list: list[float] | None, returns_status: int = 200):
    async def side_effect(url, **kwargs):
        url_str = str(url)
        if "research/artifacts" in url_str:
            return MockResponse(200, artifacts_list)
        if "broker/performance" in url_str:
            return MockResponse(returns_status, {"daily_returns": returns_list or []})
        return MockResponse(404, {})
    return AsyncMock(side_effect=side_effect)


def _mock_post():
    async def side_effect(url, **kwargs):
        return MockResponse(200, {"status": "ok"})
    return AsyncMock(side_effect=side_effect)


@pytest.mark.asyncio
async def test_promotes_artifact_when_paper_performance_within_tolerance(evaluator):
    artifacts = [
        {"artifact_id": "art-1", "name": "test-strategy", "initial_sharpe": 1.5},
    ]
    returns = [0.02, 0.015, -0.005, 0.01, 0.025, 0.0, 0.018]

    with patch.object(evaluator._http, "get", _mock_get(artifacts, returns)):
        with patch.object(evaluator._http, "post", _mock_post()):
            results = await evaluator.evaluate_all()

    assert len(results) == 1
    r = results[0]
    assert r["artifact_id"] == "art-1"
    assert r["status"] == "promoted"
    assert r["promoted"] is True
    assert r["paper_sharpe"] > 0


@pytest.mark.asyncio
async def test_insufficient_data_when_no_daily_returns(evaluator):
    artifacts = [
        {"artifact_id": "art-2", "name": "no-data-strategy", "initial_sharpe": 1.0},
    ]

    with patch.object(evaluator._http, "get", _mock_get(artifacts, None)):
        results = await evaluator.evaluate_all()

    assert len(results) == 1
    r = results[0]
    assert r["artifact_id"] == "art-2"
    assert r["status"] == "insufficient_data"
    assert r["paper_sharpe"] is None
    assert r["promoted"] is False


@pytest.mark.asyncio
async def test_withholds_promotion_when_degradation_exceeds_tolerance(evaluator):
    """Paper Sharpe degrades well beyond max_sharpe_degradation (default
    0.5) vs. backtest Sharpe -- must NOT promote. Confirmed against the
    real branch in _evaluate_one: `promoted = paper_sharpe > 0 and
    degradation <= self._max_sharpe_degradation`, status becomes
    'below_threshold', artifact stays exactly where it was (no promote
    call is made at all -- _promote_artifact is only ever called inside
    the `if promoted:` branch)."""
    artifacts = [
        {"artifact_id": "art-bad", "name": "degraded-strategy", "initial_sharpe": 2.0},
    ]
    # Small, consistently-negative daily returns -> negative paper Sharpe,
    # a massive degradation from a backtest Sharpe of 2.0.
    returns = [-0.01, -0.008, -0.012, -0.01, -0.015, -0.009, -0.011]

    with patch.object(evaluator._http, "get", _mock_get(artifacts, returns)):
        with patch.object(evaluator._http, "post", _mock_post()) as mock_post:
            results = await evaluator.evaluate_all()

    assert len(results) == 1
    r = results[0]
    assert r["artifact_id"] == "art-bad"
    assert r["status"] == "below_threshold"
    assert r["promoted"] is False
    assert r["paper_sharpe"] is not None
    mock_post.assert_not_called()  # no /promote call at all -- never touches the artifact's status


@pytest.mark.asyncio
async def test_insufficient_data_when_performance_endpoint_unreachable(evaluator):
    artifacts = [
        {"artifact_id": "art-3", "name": "unreachable-strategy", "initial_sharpe": 1.0},
    ]

    with patch.object(evaluator._http, "get", _mock_get(artifacts, None, returns_status=500)):
        results = await evaluator.evaluate_all()

    assert len(results) == 1
    r = results[0]
    assert r["artifact_id"] == "art-3"
    assert r["status"] == "insufficient_data"
    assert r["paper_sharpe"] is None
    assert r["promoted"] is False
