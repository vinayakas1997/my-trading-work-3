from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from vinu_research.llm_capabilities.capabilities import ProviderCapabilities
from vinu_research.llm_capabilities.env import default_base_url, resolve_env

LOG = logging.getLogger(__name__)

_PROVIDERS_PATH = Path(__file__).resolve().parent / "providers.json"

_providers_cache: dict[str, ProviderCapabilities] | None = None


def _load_providers() -> dict[str, ProviderCapabilities]:
    global _providers_cache
    if _providers_cache is not None:
        return _providers_cache
    raw = json.loads(_PROVIDERS_PATH.read_text(encoding="utf-8"))
    _providers_cache = {
        k: ProviderCapabilities(**v) for k, v in raw.items()
    }
    return _providers_cache


def get_capabilities(provider: str) -> ProviderCapabilities | None:
    providers = _load_providers()
    return providers.get(provider)


def list_providers() -> list[str]:
    return sorted(_load_providers().keys())


class ChatLLM:
    def __init__(
        self,
        provider: str = "ollama",
        model: str = "",
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        caps = get_capabilities(provider)
        if caps is None:
            raise ValueError(f"Unknown provider: {provider}. Available: {list_providers()}")

        self._provider = provider
        self._caps = caps

        env = resolve_env(provider)
        self._base_url = base_url or env.get("base_url") or default_base_url(provider)
        self._api_key = api_key or env.get("api_key", "")

        if caps.requires_api_key and not self._api_key and provider != "ollama":
            LOG.warning("Provider %s requires an API key but none found in env", provider)

        self._model = model or self._default_model()

    def _default_model(self) -> str:
        defaults = {
            "openai": "gpt-4o",
            "anthropic": "claude-3-opus-20240229",
            "deepseek": "deepseek-chat",
            "kimi": "moonshot-v1-8k",
            "gemini": "gemini-1.5-pro",
            "ollama": "llama3.2",
            "mistral": "mistral-large-latest",
            "groq": "llama3-70b-8192",
        }
        return defaults.get(self._provider, "gpt-4o")

    def get_headers(self) -> dict[str, str]:
        headers = dict(self._caps.default_headers)
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        headers["Content-Type"] = "application/json"
        return headers

    def build_request(self, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": kwargs.get("stream", self._caps.supports_streaming),
            "max_tokens": kwargs.get("max_tokens", self._caps.max_tokens_default),
        }
        if self._caps.temperature_override is not None:
            request["temperature"] = self._caps.temperature_override
        elif "temperature" in kwargs:
            request["temperature"] = kwargs["temperature"]
        return request

    def normalize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        choice = (response.get("choices") or [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")

        result: dict[str, Any] = {
            "content": content,
            "role": message.get("role", "assistant"),
            "finish_reason": choice.get("finish_reason", "stop"),
        }

        if self._caps.capture_reasoning:
            result["reasoning_content"] = message.get("reasoning_content", "")

        if self._caps.normalize_assistant_content:
            result["content"] = content.strip()

        return result

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._caps

    @property
    def base_url(self) -> str:
        return self._base_url
