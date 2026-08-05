from __future__ import annotations

import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

LOG = logging.getLogger(__name__)

_PROVIDERS_PATH = Path(__file__).resolve().parent / "providers.json"
_PROVIDERS_DEFAULTS_PATH = Path(__file__).resolve().parent / "provider_defaults.json"


@dataclass(frozen=True)
class ProviderCapabilities:
    name: str
    capture_reasoning: bool = False
    send_reasoning_content: bool = False
    temperature_override: float | None = None
    normalize_assistant_content: bool = False
    default_headers: dict[str, str] = field(default_factory=dict)
    supports_streaming: bool = True
    max_tokens_default: int = 4096
    requires_api_key: bool = True
    pricing: dict[str, dict[str, float]] = field(default_factory=dict)

    def get_model_pricing(self, model: str) -> dict[str, float]:
        """Return pricing for a specific model, falling back to 'default'."""
        if model in self.pricing:
            return self.pricing[model]
        return self.pricing.get("default", {"input_per_1m": 0.0, "output_per_1m": 0.0})

    def estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate USD cost for a call given token counts and model pricing."""
        p = self.get_model_pricing(model)
        input_cost = (prompt_tokens / 1_000_000) * p.get("input_per_1m", 0.0)
        output_cost = (completion_tokens / 1_000_000) * p.get("output_per_1m", 0.0)
        return round(input_cost + output_cost, 6)


_providers_cache: dict[str, ProviderCapabilities] | None = None
_defaults_cache: dict[str, dict[str, str]] | None = None


def _load_providers() -> dict[str, ProviderCapabilities]:
    global _providers_cache
    if _providers_cache is not None:
        return _providers_cache
    if not _PROVIDERS_PATH.exists():
        _providers_cache = {"ollama": ProviderCapabilities(name="ollama", requires_api_key=False)}
        return _providers_cache
    raw = json.loads(_PROVIDERS_PATH.read_text(encoding="utf-8"))
    _providers_cache = {k: ProviderCapabilities(**v) for k, v in raw.items()}
    return _providers_cache


def _load_defaults() -> dict[str, dict[str, str]]:
    global _defaults_cache
    if _defaults_cache is not None:
        return _defaults_cache
    if not _PROVIDERS_DEFAULTS_PATH.exists():
        _defaults_cache = {
            "ollama": {"base_url": "http://127.0.0.1:11434/v1"},
            "openai": {"base_url": "https://api.openai.com/v1"},
        }
        return _defaults_cache
    raw = json.loads(_PROVIDERS_DEFAULTS_PATH.read_text(encoding="utf-8"))
    _defaults_cache = raw
    return _defaults_cache


def get_capabilities(provider: str) -> ProviderCapabilities | None:
    providers = _load_providers()
    return providers.get(provider)


def list_providers() -> list[str]:
    return sorted(_load_providers().keys())


def detect_provider(model: str, base_url: str) -> str:
    m = model.lower()
    url = base_url.lower()
    if "deepseek" in m or "deepseek" in url:
        return "deepseek"
    if "openai" in m or "openai" in url:
        return "openai"
    if "anthropic" in m or "claude" in m or "anthropic" in url:
        return "anthropic"
    if "gemini" in m or "gemini" in url:
        return "gemini"
    if "mistral" in m or "mistral" in url:
        return "mistral"
    if "groq" in m or "groq" in url:
        return "groq"
    if "together" in m or "together" in url:
        return "together"
    if "perplexity" in m or "perplexity" in url:
        return "perplexity"
    if "cohere" in m or "cohere" in url:
        return "cohere"
    if "qwen" in m or "qwen" in url:
        return "qwen"
    if "kimi" in m or "kimi" in url:
        return "kimi"
    if "ollama" in m or "ollama" in url or "11434" in url:
        return "ollama"
    return "openai"


def resolve_provider_config(provider: str) -> dict[str, str]:
    defaults = _load_defaults()
    return dict(defaults.get(provider, {}))


def resolve_url(provider: str, user_url: str | None = None) -> str:
    if user_url:
        return user_url
    defaults = resolve_provider_config(provider)
    return defaults.get("base_url", "http://127.0.0.1:11434/v1")


def default_model(provider: str) -> str:
    models = {
        "openai": "gpt-4o",
        "anthropic": "claude-3-opus-20240229",
        "deepseek": "deepseek-chat",
        "kimi": "moonshot-v1-8k",
        "gemini": "gemini-1.5-pro",
        "ollama": "llama3.2",
        "qwen": "qwen2.5:7b",
        "mistral": "mistral-large-latest",
        "groq": "llama3-70b-8192",
    }
    return models.get(provider, "gpt-4o")
