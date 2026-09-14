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
    0.5) vs. backtest Sharpe -- must NOT promote. Consistently-negative
    returns push paper Sharpe below the auto-pause floor (-1.0), so status
    is 'auto_paused' (a stronger below_threshold). Artifact stays exactly
    where it was (no promote call at all)."""
    artifacts = [
        {"artifact_id": "art-bad", "name": "degraded-strategy", "initial_sharpe": 2.0},
    ]
    # Small, consistently-negative daily returns -> deeply negative paper
    # Sharpe, a massive degradation from a backtest Sharpe of 2.0.
    returns = [-0.01, -0.008, -0.012, -0.01, -0.015, -0.009, -0.011]

    with patch.object(evaluator._http, "get", _mock_get(artifacts, returns)):
        with patch.object(evaluator._http, "post", _mock_post()) as mock_post:
            results = await evaluator.evaluate_all()

    assert len(results) == 1
    r = results[0]
    assert r["artifact_id"] == "art-bad"
    assert r["status"] == "auto_paused"
    assert r["promoted"] is False
    assert r["paper_sharpe"] is not None and r["paper_sharpe"] <= -1.0
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


class TestRecordDailyPaperReturns:
    """Regression: nothing in production ever called either the
    vinu-research paper-return endpoint or vinu-agent's performance-append
    endpoint, so PaperPerformanceStore stayed permanently empty and
    evaluate_all() could never see enough daily returns to promote
    anything (see high-expectations gate-conflict audit). This is the
    write side that was missing entirely."""

    @staticmethod
    def _mock_get_paper_return(artifacts_list, paper_return_payload, paper_return_status=200):
        async def side_effect(url, **kwargs):
            url_str = str(url)
            if "research/artifacts" in url_str and "paper-return" not in url_str:
                return MockResponse(200, artifacts_list)
            if "paper-return" in url_str:
                return MockResponse(paper_return_status, paper_return_payload)
            return MockResponse(404, {})
        return AsyncMock(side_effect=side_effect)

    @pytest.mark.asyncio
    async def test_records_a_returned_daily_value(self, evaluator):
        artifacts = [{"artifact_id": "art-1", "name": "test-strategy", "initial_sharpe": 1.5}]
        payload = {"artifact_id": "art-1", "status": "ok", "daily_return": 0.012, "trade_date": "2026-09-14"}

        posted = []

        async def _post_side_effect(url, **kwargs):
            posted.append((str(url), kwargs.get("json")))
            return MockResponse(200, {"status": "ok"})

        with patch.object(evaluator._http, "get", self._mock_get_paper_return(artifacts, payload)):
            with patch.object(evaluator._http, "post", AsyncMock(side_effect=_post_side_effect)):
                results = await evaluator.record_daily_paper_returns()

        assert len(results) == 1
        assert results[0]["status"] == "recorded"
        assert results[0]["trade_date"] == "2026-09-14"
        assert len(posted) == 1
        url, body = posted[0]
        assert "broker/performance/art-1/append" in url
        assert body == {"daily_return": 0.012, "trade_date": "2026-09-14"}

    @pytest.mark.asyncio
    async def test_no_data_status_is_not_appended(self, evaluator):
        artifacts = [{"artifact_id": "art-2", "name": "no-data-strategy", "initial_sharpe": 1.0}]
        payload = {"artifact_id": "art-2", "status": "no_returns", "daily_return": None}

        with patch.object(evaluator._http, "get", self._mock_get_paper_return(artifacts, payload)):
            with patch.object(evaluator._http, "post", AsyncMock()) as mock_post:
                results = await evaluator.record_daily_paper_returns()

        assert results[0]["status"] == "no_returns"
        mock_post.assert_not_called()

    @pytest.mark.asyncio
    async def test_unreachable_research_endpoint_does_not_raise(self, evaluator):
        artifacts = [{"artifact_id": "art-3", "name": "unreachable-strategy", "initial_sharpe": 1.0}]

        with patch.object(evaluator._http, "get", self._mock_get_paper_return(artifacts, {}, paper_return_status=500)):
            with patch.object(evaluator._http, "post", AsyncMock()) as mock_post:
                results = await evaluator.record_daily_paper_returns()

        assert results[0]["status"] == "fetch_failed"
        mock_post.assert_not_called()

    @pytest.mark.asyncio
    async def test_one_artifact_failing_does_not_block_another(self, evaluator):
        artifacts = [
            {"artifact_id": "art-bad", "name": "bad", "initial_sharpe": 1.0},
            {"artifact_id": "art-good", "name": "good", "initial_sharpe": 1.0},
        ]

        async def _get_side_effect(url, **kwargs):
            url_str = str(url)
            if "research/artifacts" in url_str and "paper-return" not in url_str:
                return MockResponse(200, artifacts)
            if "art-bad" in url_str:
                raise ConnectionError("boom")
            return MockResponse(200, {"artifact_id": "art-good", "status": "ok", "daily_return": 0.01, "trade_date": "2026-09-14"})

        with patch.object(evaluator._http, "get", AsyncMock(side_effect=_get_side_effect)):
            with patch.object(evaluator._http, "post", _mock_post()):
                results = await evaluator.record_daily_paper_returns()

        assert {r["artifact_id"]: r["status"] for r in results} == {
            "art-bad": "error", "art-good": "recorded",
        }
