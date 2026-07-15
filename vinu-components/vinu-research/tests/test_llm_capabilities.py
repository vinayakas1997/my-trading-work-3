from __future__ import annotations

import os

from vinu_research.llm_capabilities.capabilities import ProviderCapabilities
from vinu_research.llm_capabilities.client import ChatLLM, get_capabilities, list_providers
from vinu_research.llm_capabilities.env import default_base_url, resolve_env


class TestProviderCapabilities:
    def test_openai_defaults(self):
        caps = get_capabilities("openai")
        assert caps is not None
        assert caps.name == "openai"
        assert not caps.capture_reasoning
        assert caps.requires_api_key is True

    def test_deepseek_has_reasoning(self):
        caps = get_capabilities("deepseek")
        assert caps is not None
        assert caps.capture_reasoning is True
        assert caps.send_reasoning_content is True

    def test_kimi_temperature_override(self):
        caps = get_capabilities("kimi")
        assert caps is not None
        assert caps.temperature_override == 1.0

    def test_ollama_no_api_key(self):
        caps = get_capabilities("ollama")
        assert caps is not None
        assert caps.requires_api_key is False

    def test_unknown_provider(self):
        caps = get_capabilities("nonexistent_provider")
        assert caps is None

    def test_list_providers(self):
        providers = list_providers()
        assert "openai" in providers
        assert "anthropic" in providers
        assert "deepseek" in providers
        assert len(providers) >= 15


class TestChatLLM:
    def test_create_ollama(self):
        llm = ChatLLM(provider="ollama")
        assert llm.provider == "ollama"
        assert llm.model == "llama3.2"
        assert not llm.capabilities.requires_api_key

    def test_create_openai(self):
        llm = ChatLLM(provider="openai")
        assert llm.provider == "openai"
        assert llm.model == "gpt-4o"

    def test_unknown_provider_raises(self):
        import pytest
        with pytest.raises(ValueError, match="Unknown provider"):
            ChatLLM(provider="nonexistent")

    def test_custom_model(self):
        llm = ChatLLM(provider="openai", model="gpt-4o-mini")
        assert llm.model == "gpt-4o-mini"

    def test_get_headers(self):
        llm = ChatLLM(provider="openai", api_key="test-key-123")
        headers = llm.get_headers()
        assert headers["Authorization"] == "Bearer test-key-123"
        assert headers["Content-Type"] == "application/json"

    def test_build_request(self):
        llm = ChatLLM(provider="openai", model="gpt-4")
        messages = [{"role": "user", "content": "hello"}]
        req = llm.build_request(messages, temperature=0.5)
        assert req["model"] == "gpt-4"
        assert req["messages"] == messages
        assert req["temperature"] == 0.5

    def test_build_request_kimi_temperature_override(self):
        llm = ChatLLM(provider="kimi")
        req = llm.build_request([{"role": "user", "content": "hi"}], temperature=0.9)
        assert req["temperature"] == 1.0

    def test_normalize_response(self):
        llm = ChatLLM(provider="openai")
        response = {
            "choices": [{
                "message": {"role": "assistant", "content": "Hello!"},
                "finish_reason": "stop",
            }]
        }
        normalized = llm.normalize_response(response)
        assert normalized["content"] == "Hello!"
        assert normalized["role"] == "assistant"

    def test_normalize_response_deepseek(self):
        llm = ChatLLM(provider="deepseek")
        response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Final answer",
                    "reasoning_content": "Thinking step by step...",
                },
                "finish_reason": "stop",
            }]
        }
        normalized = llm.normalize_response(response)
        assert normalized["content"] == "Final answer"
        assert normalized["reasoning_content"] == "Thinking step by step..."

    def test_capabilities_property(self):
        llm = ChatLLM(provider="ollama")
        assert llm.capabilities.name == "ollama"
        assert not llm.capabilities.requires_api_key


class TestLLMEnv:
    def test_resolve_env_empty_when_no_vars(self):
        result = resolve_env("openai")
        if "OPENAI_API_KEY" not in os.environ:
            assert "api_key" not in result

    def test_resolve_env_ollama(self):
        result = resolve_env("ollama")
        assert isinstance(result, dict)

    def test_default_base_url(self):
        assert default_base_url("openai") == "https://api.openai.com/v1"
        assert default_base_url("ollama") == "http://127.0.0.1:11434/v1"
        assert default_base_url("unknown") == "http://127.0.0.1:11434/v1"
