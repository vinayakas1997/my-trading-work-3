from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.agent.llm import (
    LoggingChatLLM,
    OllamaChatLLM,
    OpenAIChatLLM,
    _DEFAULT_CONTEXT_WINDOW,
    create_llm,
    create_llm_from_config,
    resolve_context_window,
    wrap_with_logging,
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


class TestCreateLlmFromConfig:
    """create_llm_from_config() builds an LLM from a standalone LLMConfig
    -- not tied to a whole AgentConfig -- so different tiers (orchestrator
    vs. teams/specialists) can each be independently configured."""

    def test_builds_from_standalone_llm_config(self) -> None:
        llm_config = LLMConfig(
            provider="openai", model_name="gpt-4o", api_key="sk-test",
            base_url="https://api.openai.com/v1", context_window=128000,
        )
        llm = create_llm_from_config(llm_config)
        assert isinstance(llm, OpenAIChatLLM)
        assert llm.model == "gpt-4o"
        assert llm.context_window == 128000

    def test_create_llm_delegates_to_create_llm_from_config(self) -> None:
        config = AgentConfig(llm=LLMConfig(
            provider="openai", model_name="m", base_url="http://fake", context_window=32000,
        ))
        assert create_llm(config).context_window == create_llm_from_config(config.llm).context_window

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_llm_from_config(LLMConfig(provider="not-a-real-provider"))


class FakeInnerLLM:
    """Minimal duck-typed ChatLLM -- LoggingChatLLM only relies on
    getattr(), so this doesn't need to subclass the real ABC."""

    def __init__(self, response=None, error: Exception | None = None):
        self.model = "fake-model"
        self.base_url = "http://fake"
        self.context_window = 32000
        self._response = response or {"content": "hello"}
        self._error = error
        self.last_messages = None
        self.last_tools = None

    def chat(self, messages, tools=None, **kwargs):
        self.last_messages = messages
        self.last_tools = tools
        if self._error:
            raise self._error
        return self._response


class FakeCallStore:
    def __init__(self):
        self.records = []

    def record(self, record):
        self.records.append(record)


class TestWrapWithLogging:
    def test_returns_unwrapped_when_store_is_none(self) -> None:
        inner = FakeInnerLLM()
        assert wrap_with_logging(inner, None) is inner

    def test_returns_logging_chat_llm_when_store_given(self) -> None:
        wrapped = wrap_with_logging(FakeInnerLLM(), FakeCallStore())
        assert isinstance(wrapped, LoggingChatLLM)


class TestLoggingChatLLM:
    def test_forwards_response_unchanged(self) -> None:
        inner = FakeInnerLLM(response={"content": "the answer", "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})
        store = FakeCallStore()
        wrapped = LoggingChatLLM(inner, store, tier="specialist")

        messages = [{"role": "user", "content": "hi"}]
        result = wrapped.chat(messages)

        assert result == inner._response
        assert inner.last_messages == messages

    def test_logs_prompt_response_tokens_and_latency_from_provider_usage(self) -> None:
        inner = FakeInnerLLM(response={
            "content": "the answer",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        })
        store = FakeCallStore()
        wrapped = LoggingChatLLM(
            inner, store, service="vinu-agent", tier="specialist",
            team="research", agent="idea_generator", role="idea-generator",
            session_id="sess-1",
        )
        messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]
        tools = [{"type": "function", "function": {"name": "echo"}}]

        wrapped.chat(messages, tools=tools)

        assert len(store.records) == 1
        rec = store.records[0]
        assert rec.tier == "specialist"
        assert rec.team == "research"
        assert rec.agent == "idea_generator"
        assert rec.role == "idea-generator"
        assert rec.session_id == "sess-1"
        assert rec.model == "fake-model"
        assert rec.base_url == "http://fake"
        assert rec.provider == "FakeInnerLLM"
        assert rec.prompt == messages
        assert rec.tools == tools
        assert rec.response_content == "the answer"
        assert rec.prompt_tokens == 10
        assert rec.completion_tokens == 5
        assert rec.total_tokens == 15
        assert rec.token_count_source == "provider"
        assert rec.success is True
        assert rec.latency_sec >= 0

    def test_estimates_tokens_when_provider_reports_no_usage(self) -> None:
        inner = FakeInnerLLM(response={"content": "short answer"})
        store = FakeCallStore()
        wrapped = LoggingChatLLM(inner, store)

        wrapped.chat([{"role": "user", "content": "hi"}])

        rec = store.records[0]
        assert rec.token_count_source == "estimated"
        assert rec.total_tokens == rec.prompt_tokens + rec.completion_tokens
        assert rec.total_tokens > 0

    def test_records_failure_and_still_reraises(self) -> None:
        inner = FakeInnerLLM(error=RuntimeError("connection refused"))
        store = FakeCallStore()
        wrapped = LoggingChatLLM(inner, store, tier="orchestrator")

        with pytest.raises(RuntimeError, match="connection refused"):
            wrapped.chat([{"role": "user", "content": "hi"}])

        assert len(store.records) == 1
        assert store.records[0].success is False
        assert store.records[0].error == "connection refused"

    def test_logging_failure_does_not_break_the_real_call(self) -> None:
        class BrokenStore:
            def record(self, record):
                raise RuntimeError("db is down")

        inner = FakeInnerLLM(response={"content": "still works"})
        wrapped = LoggingChatLLM(inner, BrokenStore())

        result = wrapped.chat([{"role": "user", "content": "hi"}])
        assert result == {"content": "still works"}

    def test_model_base_url_context_window_proxy_to_inner(self) -> None:
        inner = FakeInnerLLM()
        wrapped = LoggingChatLLM(inner, FakeCallStore())
        assert wrapped.model == "fake-model"
        assert wrapped.base_url == "http://fake"
        assert wrapped.context_window == 32000
