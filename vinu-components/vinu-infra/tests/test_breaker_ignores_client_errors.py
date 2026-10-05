"""A 4xx is an answer from a live service, so it must never open the circuit breaker.

Found in the first real research batch: one bad candidate (simulator 422) and a lookup of a run id that does not exist
(404) opened the shared breaker, and the next three tickers were then reported as "simulator down or circuit open"
although the simulator was fine. Only outages (5xx, timeouts, connection errors) may open it."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from vinu_infra.client import ResilientClient


def _client() -> ResilientClient:
    return ResilientClient("http://fake-service", "test-service", retry_backoff=0.0)


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://fake-service/x")
    return httpx.HTTPStatusError(f"HTTP {status}", request=request,
                                 response=httpx.Response(status, json={"detail": "no"}, request=request))


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 404, 422])
async def test_repeated_client_errors_do_not_open_the_breaker(status):
    client = _client()
    client._http = AsyncMock(spec=httpx.AsyncClient)
    client._http.request = AsyncMock(side_effect=_http_error(status))
    for _ in range(6):                                              # twice the threshold of 3
        with pytest.raises(httpx.HTTPStatusError):
            await client.post("/x", json={}, raise_on_error=True)
    client._http.request = AsyncMock(return_value=httpx.Response(200, json={"ok": True},
                                                                 request=httpx.Request("POST", "http://fake-service/x")))
    assert await client.post("/x", json={}, raise_on_error=True) == {"ok": True}      # the service still answers
    await client.close()


@pytest.mark.asyncio
async def test_real_outages_still_open_the_breaker():
    client = _client()
    client._http = AsyncMock(spec=httpx.AsyncClient)
    client._http.request = AsyncMock(side_effect=_http_error(503))
    for _ in range(4):
        try:
            await client.post("/x", json={}, raise_on_error=True)
        except Exception:                                           # noqa: BLE001
            pass
    client._http.request = AsyncMock(return_value=httpx.Response(200, json={"ok": True},
                                                                 request=httpx.Request("POST", "http://fake-service/x")))
    assert await client.post("/x", json={}, fallback={"open": True}) == {"open": True}   # still failing fast
    await client.close()
