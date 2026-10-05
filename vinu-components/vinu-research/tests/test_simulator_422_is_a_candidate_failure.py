"""A simulator 422 ("No weight data generated") means the candidate's code produced nothing; the simulator is up. It must
raise a plain candidate failure the loop can replace, never an InfrastructureError that stops the run. Real outages
(5xx, auth, unreachable) still are infrastructure."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from vinu_research.tools import InfrastructureError, ResearchTools


def _tools_failing_with(status: int) -> ResearchTools:
    tools = ResearchTools.__new__(ResearchTools)
    request = httpx.Request("POST", "http://sim/simulate/custom")
    err = httpx.HTTPStatusError("x", request=request, response=httpx.Response(
        status, json={"detail": "No weight data generated — all symbols returned empty"}, request=request))
    tools._simulator_client = MagicMock()
    tools._simulator_client.post = AsyncMock(side_effect=err)
    return tools


async def _run(tools):
    return await tools.run_backtest("code", "UserStrategy", ["AAPL"], "2022-01-01", "2024-01-01")


@pytest.mark.asyncio
async def test_422_is_a_candidate_failure_not_infrastructure():
    with pytest.raises(RuntimeError) as exc:
        await _run(_tools_failing_with(422))
    assert not isinstance(exc.value, InfrastructureError)
    assert "No weight data generated" in str(exc.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 500, 503])
async def test_outages_and_auth_failures_are_still_infrastructure(status):
    with pytest.raises(InfrastructureError):
        await _run(_tools_failing_with(status))
