from __future__ import annotations

import pytest

from vinu_agent.agent.llm import (
    ChatLLM,
    FallbackChatLLM,
    create_llm_from_config,
)
from vinu_agent.config import LLMConfig


class _FakeLLM(ChatLLM):
    def __init__(self, name: str, *, fail: bool = False, response: dict | None = None):
        self._name = name
        self._fail = fail
        self._response = response or {"content": f"from {name}"}
        self.calls = 0

    @property
    def model(self) -> str:
        return self._name

    def chat(self, messages: list, tools=None, **kwargs) -> dict:
        self.calls += 1
        if self._fail:
            raise RuntimeError(f"{self._name} is down")
        return dict(self._response)


class TestFallbackChatLLM:
    """Implementation-plan task 07: a simple provider waterfall, ported from
    Jarvis's `_call_llm()`. Falls to the next provider only on genuine
    failure (after the provider's own retries are exhausted); a successful
    primary response never triggers fallback."""

    def test_primary_failure_falls_back_and_succeeds(self):
        primary = _FakeLLM("primary", fail=True)
        fallback = _FakeLLM("fallback")
        llm = FallbackChatLLM([primary, fallback])

        result = llm.chat([{"role": "user", "content": "hi"}])

        assert primary.calls == 1
        assert fallback.calls == 1
        assert result["content"] == "from fallback"
        assert result["provider"] == "_FakeLLM/fallback"

    def test_primary_success_never_touches_fallback(self):
        primary = _FakeLLM("primary")
        fallback = _FakeLLM("fallback")
        llm = FallbackChatLLM([primary, fallback])

        result = llm.chat([{"role": "user", "content": "hi"}])

        assert primary.calls == 1
        assert fallback.calls == 0
        assert result["content"] == "from primary"
        assert result["provider"] == "_FakeLLM/primary"

    def test_all_providers_failed_raises_naming_everyone(self):
        primary = _FakeLLM("primary", fail=True)
        fallback = _FakeLLM("fallback", fail=True)
        llm = FallbackChatLLM([primary, fallback])

        with pytest.raises(RuntimeError) as exc:
            llm.chat([{"role": "user", "content": "hi"}])
        assert "_FakeLLM/primary" in str(exc.value)
        assert "_FakeLLM/fallback" in str(exc.value)

    def test_single_provider_is_backward_compatible(self):
        only = _FakeLLM("only")
        llm = FallbackChatLLM([only])

        result = llm.chat([{"role": "user", "content": "hi"}])

        assert only.calls == 1
        assert "provider" not in result  # no extra tag when there's nothing to fall back to

    def test_fallback_does_not_fire_on_a_successful_slow_response(self):
        # A slow-but-successful primary must be returned as-is: fallback is
        # keyed on failure (exception after retries), not on latency.
        primary = _FakeLLM("primary", response={"content": "slow but fine"})
        fallback = _FakeLLM("fallback")
        llm = FallbackChatLLM([primary, fallback])

        result = llm.chat([{"role": "user", "content": "hi"}])

        assert result["content"] == "slow but fine"
        assert fallback.calls == 0

    def test_empty_providers_rejected(self):
        with pytest.raises(ValueError):
            FallbackChatLLM([])


class TestCreateLlmFromConfigFallbacks:
    def test_fallbacks_build_a_waterfall(self):
        primary = LLMConfig(
            provider="ollama", model_name="primary-model",
            base_url="http://primary", context_window=8000,
        )
        fallback = LLMConfig(
            provider="ollama", model_name="fallback-model",
            base_url="http://fallback", context_window=8000,
        )
        llm = create_llm_from_config(LLMConfig(
            provider="ollama", model_name="primary-model",
            base_url="http://primary", context_window=8000,
            fallbacks=[fallback],
        ))
        assert isinstance(llm, FallbackChatLLM)

    def test_no_fallbacks_returns_plain_llm(self):
        llm = create_llm_from_config(LLMConfig(
            provider="ollama", model_name="m", base_url="http://x", context_window=8000,
        ))
        assert not isinstance(llm, FallbackChatLLM)
        assert llm.model == "m"

    def test_config_parses_env_fallbacks(self, monkeypatch):
        monkeypatch.setenv(
            "VINU_LLM_FALLBACKS",
            '[{"provider": "ollama", "model_name": "fb", "base_url": "http://fb"}]',
        )
        from vinu_agent.config import load_config

        cfg = load_config()
        assert len(cfg.llm.fallbacks) == 1
        assert cfg.llm.fallbacks[0].provider == "ollama"
        assert cfg.llm.fallbacks[0].model_name == "fb"

    def test_malformed_fallbacks_env_is_loud(self, monkeypatch):
        monkeypatch.setenv("VINU_LLM_FALLBACKS", "{not json")
        from vinu_agent.config import load_config

        with pytest.raises(Exception):
            load_config()