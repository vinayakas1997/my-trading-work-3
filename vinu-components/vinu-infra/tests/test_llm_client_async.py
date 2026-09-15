"""Async counterpart of test_llm_client.py -- see that file's module
docstring for why this changed (raise on failure, retry on parse
failure)."""

from __future__ import annotations

from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from vinu_infra.llm.client_async import AsyncLlmClient
from vinu_infra.llm.config import LlmConfig
from vinu_infra.llm.retry import LlmCallFailed


def _config(**overrides) -> LlmConfig:
    defaults = dict(
        base_url="http://fake-llm/v1",
        model="test-model",
        retry_max=3,
        rate_limit=1000,
        rate_period_sec=1.0,
        ttl_sec=0,
    )
    defaults.update(overrides)
    return LlmConfig(**defaults)


def _ok_response(content: str = '{"answer": 42}') -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    return resp


def _client(http_client, tmp) -> AsyncLlmClient:
    return AsyncLlmClient(config=_config(data_root=tmp), service="test-service", http_client=http_client)


@pytest.mark.asyncio
class TestSuccessPath:
    async def test_returns_parsed_dict_on_success(self):
        with TemporaryDirectory() as tmp:
            http = AsyncMock(spec=httpx.AsyncClient)
            http.post.return_value = _ok_response()
            client = _client(http, tmp)
            assert await client.chat_json("sys", "user") == {"answer": 42}
            await client.close()

    async def test_cache_hit_skips_the_request(self):
        with TemporaryDirectory() as tmp:
            http = AsyncMock(spec=httpx.AsyncClient)
            http.post.return_value = _ok_response()
            config = _config(data_root=tmp, ttl_sec=3600)
            client = AsyncLlmClient(config=config, http_client=http)
            first = await client.chat_json("sys", "user")
            http.post.reset_mock()
            second = await client.chat_json("sys", "user")
            assert first == second == {"answer": 42}
            http.post.assert_not_called()
            await client.close()


@pytest.mark.asyncio
class TestRetryOnFailure:
    async def test_retries_connect_error_then_succeeds(self, monkeypatch):
        monkeypatch.setattr("asyncio.sleep", AsyncMock())
        with TemporaryDirectory() as tmp:
            http = AsyncMock(spec=httpx.AsyncClient)
            http.post.side_effect = [
                httpx.ConnectError("dropped"),
                _ok_response(),
            ]
            client = _client(http, tmp)
            assert await client.chat_json("sys", "user") == {"answer": 42}
            assert http.post.call_count == 2
            await client.close()

    async def test_retries_a_malformed_json_response_then_succeeds(self, monkeypatch):
        monkeypatch.setattr("asyncio.sleep", AsyncMock())
        with TemporaryDirectory() as tmp:
            http = AsyncMock(spec=httpx.AsyncClient)
            http.post.side_effect = [
                _ok_response(content="not valid json"),
                _ok_response(),
            ]
            client = _client(http, tmp)
            assert await client.chat_json("sys", "user") == {"answer": 42}
            assert http.post.call_count == 2
            await client.close()

    async def test_retries_transient_5xx_then_succeeds(self, monkeypatch):
        monkeypatch.setattr("asyncio.sleep", AsyncMock())
        with TemporaryDirectory() as tmp:
            http = AsyncMock(spec=httpx.AsyncClient)
            request = httpx.Request("POST", "http://fake-llm/v1/chat/completions")
            error_resp = httpx.Response(503, request=request, headers={})
            http_error = httpx.HTTPStatusError("server error", request=request, response=error_resp)
            http.post.side_effect = [http_error, _ok_response()]
            client = _client(http, tmp)
            assert await client.chat_json("sys", "user") == {"answer": 42}
            await client.close()

    async def test_does_not_retry_a_non_transient_4xx(self):
        with TemporaryDirectory() as tmp:
            http = AsyncMock(spec=httpx.AsyncClient)
            request = httpx.Request("POST", "http://fake-llm/v1/chat/completions")
            error_resp = httpx.Response(401, request=request, headers={})
            http_error = httpx.HTTPStatusError("unauthorized", request=request, response=error_resp)
            http.post.side_effect = http_error
            client = _client(http, tmp)
            with pytest.raises(LlmCallFailed):
                await client.chat_json("sys", "user")
            assert http.post.call_count == 1
            await client.close()


@pytest.mark.asyncio
class TestExhaustionRaises:
    async def test_raises_llm_call_failed_not_none_after_exhausting_retries(self, monkeypatch):
        monkeypatch.setattr("asyncio.sleep", AsyncMock())
        with TemporaryDirectory() as tmp:
            http = AsyncMock(spec=httpx.AsyncClient)
            http.post.side_effect = httpx.ConnectError("always down")
            client = _client(http, tmp)
            with pytest.raises(LlmCallFailed):
                await client.chat_json("sys", "user")
            assert http.post.call_count == 3
            await client.close()

    async def test_not_configured_raises_immediately(self):
        with TemporaryDirectory() as tmp:
            config = _config(data_root=tmp, base_url="")
            client = AsyncLlmClient(config=config, http_client=AsyncMock(spec=httpx.AsyncClient))
            with pytest.raises(LlmCallFailed):
                await client.chat_json("sys", "user")
            await client.close()
