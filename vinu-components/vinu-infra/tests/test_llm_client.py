"""Tests for LlmClient's new raise-on-failure contract and the shared
retry policy actually being applied -- chat_json() used to return `None`
on final failure and give up immediately on a parse error without
retrying or trying another candidate endpoint. See
missing-pieces-of-system/llm-configuration-settings-system/."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

import pytest
import requests

from vinu_infra.llm.client import LlmClient
from vinu_infra.llm.config import LlmConfig
from vinu_infra.llm.retry import LlmCallFailed


def _config(**overrides) -> LlmConfig:
    defaults = dict(
        base_url="http://fake-llm/v1",
        model="test-model",
        retry_max=3,
        rate_limit=1000,
        rate_period_sec=1.0,
        ttl_sec=0,  # disable cache by default so tests hit the request path
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


def _client(session, tmp) -> LlmClient:
    return LlmClient(config=_config(data_root=tmp), service="test-service", session=session)


class TestSuccessPath:
    def test_returns_parsed_dict_on_success(self):
        with TemporaryDirectory() as tmp:
            session = MagicMock()
            session.post.return_value = _ok_response()
            client = _client(session, tmp)
            assert client.chat_json("sys", "user") == {"answer": 42}
            client.close()

    def test_cache_hit_skips_the_request(self):
        with TemporaryDirectory() as tmp:
            session = MagicMock()
            session.post.return_value = _ok_response()
            config = _config(data_root=tmp, ttl_sec=3600)
            client = LlmClient(config=config, session=session)
            first = client.chat_json("sys", "user")
            session.post.reset_mock()
            second = client.chat_json("sys", "user")
            assert first == second == {"answer": 42}
            session.post.assert_not_called()
            client.close()


class TestRetryOnFailure:
    def test_retries_connection_error_then_succeeds(self, monkeypatch):
        monkeypatch.setattr("time.sleep", lambda *_: None)
        with TemporaryDirectory() as tmp:
            session = MagicMock()
            session.post.side_effect = [
                requests.ConnectionError("dropped"),
                _ok_response(),
            ]
            client = _client(session, tmp)
            assert client.chat_json("sys", "user") == {"answer": 42}
            assert session.post.call_count == 2
            client.close()

    def test_retries_a_malformed_json_response_then_succeeds(self, monkeypatch):
        """The gap this session's audit found: nothing used to retry a
        parse failure, only connection/HTTP errors."""
        monkeypatch.setattr("time.sleep", lambda *_: None)
        with TemporaryDirectory() as tmp:
            session = MagicMock()
            session.post.side_effect = [
                _ok_response(content="not valid json at all"),
                _ok_response(),
            ]
            client = _client(session, tmp)
            assert client.chat_json("sys", "user") == {"answer": 42}
            assert session.post.call_count == 2
            client.close()

    def test_retries_transient_5xx_then_succeeds(self, monkeypatch):
        monkeypatch.setattr("time.sleep", lambda *_: None)
        with TemporaryDirectory() as tmp:
            session = MagicMock()
            error_resp = MagicMock(status_code=503, headers={})
            http_error = requests.RequestException("server error")
            http_error.response = error_resp
            session.post.side_effect = [http_error, _ok_response()]
            client = _client(session, tmp)
            assert client.chat_json("sys", "user") == {"answer": 42}
            client.close()

    def test_does_not_retry_a_non_transient_4xx(self):
        with TemporaryDirectory() as tmp:
            session = MagicMock()
            error_resp = MagicMock(status_code=401, headers={})
            http_error = requests.RequestException("unauthorized")
            http_error.response = error_resp
            session.post.side_effect = http_error
            client = _client(session, tmp)
            with pytest.raises(LlmCallFailed):
                client.chat_json("sys", "user")
            assert session.post.call_count == 1  # no retry for a non-transient error
            client.close()


class TestExhaustionRaises:
    def test_raises_llm_call_failed_not_none_after_exhausting_retries(self, monkeypatch):
        monkeypatch.setattr("time.sleep", lambda *_: None)
        with TemporaryDirectory() as tmp:
            session = MagicMock()
            session.post.side_effect = requests.ConnectionError("always down")
            client = _client(session, tmp)
            with pytest.raises(LlmCallFailed):
                client.chat_json("sys", "user")
            assert session.post.call_count == 3  # retry_max
            client.close()

    def test_not_configured_raises_immediately(self):
        with TemporaryDirectory() as tmp:
            config = _config(data_root=tmp, base_url="")
            client = LlmClient(config=config, session=MagicMock())
            with pytest.raises(LlmCallFailed):
                client.chat_json("sys", "user")
            client.close()

    def test_exhausting_parse_retries_raises_llm_call_failed(self, monkeypatch):
        monkeypatch.setattr("time.sleep", lambda *_: None)
        with TemporaryDirectory() as tmp:
            session = MagicMock()
            session.post.return_value = _ok_response(content="still not json")
            client = _client(session, tmp)
            with pytest.raises(LlmCallFailed):
                client.chat_json("sys", "user")
            client.close()
