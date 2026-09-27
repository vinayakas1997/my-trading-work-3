from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from vinu_infra.client import ResilientClient


def _client(**overrides) -> ResilientClient:
    return ResilientClient("http://fake-service", "test-service", **overrides)


def _http_error(status: int, detail: str = "bad request") -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://fake-service/x")
    response = httpx.Response(status, json={"detail": detail}, request=request)
    return httpx.HTTPStatusError(f"HTTP {status}", request=request, response=response)


@pytest.mark.asyncio
class TestRaiseOnErrorDefaultFalse:
    """item #17 finding #1: the default (False) must keep every existing
    caller's graceful-fallback-to-None-or-fallback behavior unchanged."""

    async def test_get_swallows_http_error_and_returns_fallback_by_default(self) -> None:
        client = _client()
        client._http = AsyncMock(spec=httpx.AsyncClient)
        client._http.request = AsyncMock(side_effect=_http_error(404))
        result = await client.get("/x", fallback={"default": True})
        assert result == {"default": True}
        await client.close()

    async def test_post_swallows_http_error_and_returns_fallback_by_default(self) -> None:
        client = _client()
        client._http = AsyncMock(spec=httpx.AsyncClient)
        client._http.request = AsyncMock(side_effect=_http_error(404))
        result = await client.post("/x", json={}, fallback={"default": True})
        assert result == {"default": True}
        await client.close()


@pytest.mark.asyncio
class TestRaiseOnErrorOptedIn:
    """The actual fix: raise_on_error=True lets a caller's own
    already-written exception handling (e.g. vinu-research's
    run_backtest(), which specifically catches httpx.HTTPStatusError to
    extract the simulator's real error detail) actually receive the real
    exception instead of a silently-substituted fallback value."""

    async def test_get_reraises_http_status_error_when_opted_in(self) -> None:
        client = _client()
        client._http = AsyncMock(spec=httpx.AsyncClient)
        client._http.request = AsyncMock(side_effect=_http_error(422, detail="no weight data"))
        with pytest.raises(httpx.HTTPStatusError) as excinfo:
            await client.get("/x", raise_on_error=True)
        assert excinfo.value.response.status_code == 422
        await client.close()

    async def test_post_reraises_http_status_error_when_opted_in(self) -> None:
        client = _client()
        client._http = AsyncMock(spec=httpx.AsyncClient)
        client._http.request = AsyncMock(side_effect=_http_error(422, detail="no weight data"))
        with pytest.raises(httpx.HTTPStatusError) as excinfo:
            await client.post("/x", json={}, raise_on_error=True)
        assert excinfo.value.response.status_code == 422
        await client.close()

    async def test_reraises_after_retries_exhausted_on_persistent_5xx(self) -> None:
        """A persistent 5xx exhausts _request_impl's retry budget and
        surfaces as a RuntimeError (wrapping the last HTTPStatusError),
        not the HTTPStatusError itself -- raise_on_error=True must still
        let it through rather than substituting a fallback."""
        client = _client(max_retries=1)
        client._http = AsyncMock(spec=httpx.AsyncClient)
        client._http.request = AsyncMock(side_effect=_http_error(500))
        with pytest.raises(RuntimeError):
            await client.post("/x", json={}, raise_on_error=True)
        await client.close()

    async def test_ssrf_value_error_still_raises_regardless_of_raise_on_error(self) -> None:
        client = ResilientClient("http://localhost:9", "test-service", allow_local=False)
        with pytest.raises(ValueError):
            await client.get("/x", raise_on_error=False)
        await client.close()

    async def test_successful_call_unaffected_by_raise_on_error(self) -> None:
        client = _client()
        client._http = AsyncMock(spec=httpx.AsyncClient)
        request = httpx.Request("GET", "http://fake-service/x")
        client._http.request = AsyncMock(
            return_value=httpx.Response(200, json={"ok": True}, request=request)
        )
        result = await client.get("/x", raise_on_error=True)
        assert result == {"ok": True}
        await client.close()
