from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from vinu_live.trade_plan_approval_worker import TradePlanApprovalWorker


class MockResponse:
    def __init__(self, status_code: int, json_data: object) -> None:
        self.status_code = status_code
        self._json = json_data

    def json(self):
        return self._json


@pytest.fixture
def worker():
    return TradePlanApprovalWorker(
        research_api_url="http://test-research:8087", agent_api_url="http://test-agent:8086",
    )


def _mock_get(created_plans: list[dict]):
    async def side_effect(url, **kwargs):
        if "research/artifacts" in str(url):
            return MockResponse(200, created_plans)
        return MockResponse(404, {})
    return AsyncMock(side_effect=side_effect)


def _mock_post(status_code: int, body: object):
    async def side_effect(url, **kwargs):
        return MockResponse(status_code, body)
    return AsyncMock(side_effect=side_effect)


@pytest.mark.asyncio
async def test_approves_a_bootstrap_eligible_plan(worker):
    plans = [{"artifact_id": "tp-1", "name": "trade_plan_AAPL_daily"}]

    with patch.object(worker._http, "get", _mock_get(plans)):
        with patch.object(worker._http, "post", _mock_post(200, {"status": "promoted"})):
            results = await worker.approve_all()

    assert len(results) == 1
    assert results[0] == {"artifact_id": "tp-1", "name": "trade_plan_AAPL_daily", "approved": True, "status": "approved"}


@pytest.mark.asyncio
async def test_gate_rejection_is_not_an_error(worker):
    # Stage 0 (G2a): a 409 from the approve route is the gate correctly
    # fail-closing (no calibration history and no ACTIVE strategy to
    # bootstrap from, or calibration failed) -- not a worker malfunction.
    # Retried automatically next cycle, same as ShadowEvaluator's
    # below_threshold status.
    plans = [{"artifact_id": "tp-2", "name": "trade_plan_MSFT_daily"}]
    body = {"detail": {"message": "...", "reasons": ["no ACTIVE strategy artifact for MSFT"]}}

    with patch.object(worker._http, "get", _mock_get(plans)):
        with patch.object(worker._http, "post", _mock_post(409, body)):
            results = await worker.approve_all()

    assert len(results) == 1
    assert results[0]["approved"] is False
    assert results[0]["status"] == "rejected"
    assert results[0]["reasons"] == ["no ACTIVE strategy artifact for MSFT"]


@pytest.mark.asyncio
async def test_no_created_plans_returns_empty(worker):
    with patch.object(worker._http, "get", _mock_get([])):
        results = await worker.approve_all()

    assert results == []


@pytest.mark.asyncio
async def test_one_plans_error_does_not_block_the_rest(worker):
    plans = [
        {"artifact_id": "tp-3", "name": "a"},
        {"artifact_id": "tp-4", "name": "b"},
    ]
    call_count = 0

    async def post_side_effect(url, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("research api down")
        return MockResponse(200, {"status": "promoted"})

    with patch.object(worker._http, "get", _mock_get(plans)):
        with patch.object(worker._http, "post", AsyncMock(side_effect=post_side_effect)):
            results = await worker.approve_all()

    assert len(results) == 2
    assert results[0]["status"] == "error"
    assert results[1]["approved"] is True


@pytest.mark.asyncio
async def test_list_failure_returns_empty_not_raise(worker):
    with patch.object(worker._http, "get", AsyncMock(side_effect=ConnectionError("down"))):
        results = await worker.approve_all()

    assert results == []


class TestNotifyOnRejection:
    """Stage 0 (G2b): a rejected plan should notify vinu-agent's chat
    channels so a human can force-approve it; an approved plan should not."""

    @staticmethod
    def _dispatching_post(approve_status: int, approve_body: object):
        calls: list[tuple[str, dict]] = []

        async def side_effect(url, **kwargs):
            calls.append((str(url), kwargs))
            if "notify/trade-plan-pending" in str(url):
                return MockResponse(200, {"status": "ok"})
            return MockResponse(approve_status, approve_body)

        return AsyncMock(side_effect=side_effect), calls

    @pytest.mark.asyncio
    async def test_rejection_notifies_with_symbol_and_reasons(self, worker):
        plans = [{"artifact_id": "tp-5", "name": "trade_plan_MSFT_daily", "universe": ["MSFT"]}]
        body = {"detail": {"reasons": ["no ACTIVE strategy artifact for MSFT"]}}
        post_mock, calls = self._dispatching_post(409, body)

        with patch.object(worker._http, "get", _mock_get(plans)):
            with patch.object(worker._http, "post", post_mock):
                await worker.approve_all()

        notify_calls = [c for c in calls if "notify/trade-plan-pending" in c[0]]
        assert len(notify_calls) == 1
        assert notify_calls[0][0] == "http://test-agent:8086/agent/notify/trade-plan-pending"
        assert notify_calls[0][1]["json"] == {
            "artifact_id": "tp-5", "symbol": "MSFT", "reasons": ["no ACTIVE strategy artifact for MSFT"],
        }

    @pytest.mark.asyncio
    async def test_approval_does_not_notify(self, worker):
        plans = [{"artifact_id": "tp-6", "name": "trade_plan_AAPL_daily", "universe": ["AAPL"]}]
        post_mock, calls = self._dispatching_post(200, {"status": "promoted"})

        with patch.object(worker._http, "get", _mock_get(plans)):
            with patch.object(worker._http, "post", post_mock):
                await worker.approve_all()

        assert not [c for c in calls if "notify/trade-plan-pending" in c[0]]

    @pytest.mark.asyncio
    async def test_notify_failure_does_not_affect_the_reported_rejection(self, worker):
        plans = [{"artifact_id": "tp-7", "name": "x", "universe": ["TSLA"]}]

        async def side_effect(url, **kwargs):
            if "notify/trade-plan-pending" in str(url):
                raise ConnectionError("agent down")
            return MockResponse(409, {"detail": {"reasons": ["rejected"]}})

        with patch.object(worker._http, "get", _mock_get(plans)):
            with patch.object(worker._http, "post", AsyncMock(side_effect=side_effect)):
                results = await worker.approve_all()  # must not raise

        assert results[0]["status"] == "rejected"
