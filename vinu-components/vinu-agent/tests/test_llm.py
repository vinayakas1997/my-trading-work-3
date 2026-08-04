from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.agent.llm import (
    OllamaChatLLM,
    OpenAIChatLLM,
    _DEFAULT_CONTEXT_WINDOW,
    create_llm,
    resolve_context_window,
)
from vinu_agent.config import AgentConfig, LLMConfig


def _openai_response(content: str = "hello", usage: SimpleNamespace | None = None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], usage=usage)


class TestOpenAIChatLLM:
    def test_chat_succeeds_first_attempt_reports_zero_retries(self) -> None:
        llm = OpenAIChatLLM(model="test-model", base_url="http://fake")
        llm._client = MagicMock()
        llm._client.chat.completions.create.return_value = _openai_response("hi there")

        result = llm.chat([{"role": "user", "content": "hi"}])

        assert result["content"] == "hi there"
        assert result["retry_count"] == 0

    def test_chat_populates_real_usage_from_provider(self) -> None:
        llm = OpenAIChatLLM(model="test-model", base_url="http://fake")
        llm._client = MagicMock()
        usage = SimpleNamespace(prompt_tokens=123, completion_tokens=45, total_tokens=168)
        llm._client.chat.completions.create.return_value = _openai_response("ok", usage=usage)

        result = llm.chat([{"role": "user", "content": "hi"}])

        assert result["usage"] == {
            "prompt_tokens": 123,
            "completion_tokens": 45,
            "total_tokens": 168,
        }

    def test_chat_retries_on_transient_error_and_reports_retry_count(self) -> None:
        from openai import APIConnectionError

        llm = OpenAIChatLLM(model="test-model", base_url="http://fake", retry_max=3)
        llm._client = MagicMock()
        transient = APIConnectionError(request=MagicMock())
        llm._client.chat.completions.create.side_effect = [
            transient, transient, _openai_response("recovered"),
        ]

        with patch("vinu_agent.agent.llm.time.sleep"):
            result = llm.chat([{"role": "user", "content": "hi"}])

        assert result["content"] == "recovered"
        assert result["retry_count"] == 2
        assert llm._client.chat.completions.create.call_count == 3

    def test_chat_raises_after_exhausting_retries(self) -> None:
        from openai import APIConnectionError

        llm = OpenAIChatLLM(model="test-model", base_url="http://fake", retry_max=2)
        llm._client = MagicMock()
        llm._client.chat.completions.create.side_effect = APIConnectionError(request=MagicMock())

        with patch("vinu_agent.agent.llm.time.sleep"):
            with pytest.raises(RuntimeError, match="failed after 2 attempt"):
                llm.chat([{"role": "user", "content": "hi"}])

        assert llm._client.chat.completions.create.call_count == 2

    def test_chat_does_not_retry_non_transient_error(self) -> None:
        llm = OpenAIChatLLM(model="test-model", base_url="http://fake", retry_max=3)
        llm._client = MagicMock()
        llm._client.chat.completions.create.side_effect = ValueError("bad request")

        with pytest.raises(RuntimeError, match="failed after 1 attempt"):
            llm.chat([{"role": "user", "content": "hi"}])

        assert llm._client.chat.completions.create.call_count == 1

    def test_max_retries_zero_passed_to_sdk_client(self) -> None:
        with patch("openai.OpenAI") as mock_openai_cls:
            OpenAIChatLLM(model="m", base_url="http://fake")
            _, kwargs = mock_openai_cls.call_args
            assert kwargs["max_retries"] == 0


class TestOllamaChatLLM:
    def test_chat_populates_usage_from_eval_counts(self) -> None:
        llm = OllamaChatLLM(model="llama3", base_url="http://fake")
        fake_resp = MagicMock()
        fake_resp.raise_for_status.return_value = None
        fake_resp.json.return_value = {
            "message": {"content": "hi"},
            "prompt_eval_count": 50,
            "eval_count": 20,
        }
        with patch("requests.post", return_value=fake_resp):
            result = llm.chat([{"role": "user", "content": "hi"}])

        assert result["retry_count"] == 0
        assert result["usage"] == {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70}

    def test_chat_retries_on_connection_error(self) -> None:
        import requests

        llm = OllamaChatLLM(model="llama3", base_url="http://fake", retry_max=2)
        fake_resp = MagicMock()
        fake_resp.raise_for_status.return_value = None
        fake_resp.json.return_value = {"message": {"content": "recovered"}}
        with patch("requests.post", side_effect=[requests.ConnectionError("down"), fake_resp]):
            with patch("time.sleep"):
                result = llm.chat([{"role": "user", "content": "hi"}])

        assert result["content"] == "recovered"
        assert result["retry_count"] == 1


class TestResolveContextWindow:
    def test_returns_n_ctx_when_present(self) -> None:
        fake_resp = MagicMock()
        fake_resp.raise_for_status.return_value = None
        fake_resp.json.return_value = {"n_ctx": 32000}
        with patch("httpx.get", return_value=fake_resp):
            assert resolve_context_window("http://localhost:8009/v1") == 32000

    def test_finds_context_length_nested_in_data_list(self) -> None:
        fake_resp = MagicMock()
        fake_resp.raise_for_status.return_value = None
        fake_resp.json.return_value = {"data": [{"id": "m1", "context_length": 4096}]}
        with patch("httpx.get", return_value=fake_resp):
            assert resolve_context_window("http://localhost:8009/v1") == 4096

    def test_falls_back_to_default_on_request_error(self) -> None:
        with patch("httpx.get", side_effect=OSError("connection refused")):
            assert resolve_context_window("http://localhost:8009/v1") == _DEFAULT_CONTEXT_WINDOW

    def test_falls_back_to_default_when_no_base_url(self) -> None:
        assert resolve_context_window("") == _DEFAULT_CONTEXT_WINDOW


class TestCreateLlmContextWindow:
    def test_uses_config_override_without_network_call(self) -> None:
        config = AgentConfig(llm=LLMConfig(
            provider="openai", model_name="m", base_url="http://fake", context_window=32000,
        ))
        with patch("vinu_agent.agent.llm.resolve_context_window") as mock_resolve:
            llm = create_llm(config)
        mock_resolve.assert_not_called()
        assert llm.context_window == 32000

    def test_auto_resolves_when_no_override(self) -> None:
        config = AgentConfig(llm=LLMConfig(
            provider="openai", model_name="m", base_url="http://fake", context_window=0,
        ))
        with patch("vinu_agent.agent.llm.resolve_context_window", return_value=32000) as mock_resolve:
            llm = create_llm(config)
        mock_resolve.assert_called_once_with("http://fake", "m")
        assert llm.context_window == 32000
