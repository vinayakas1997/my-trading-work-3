from __future__ import annotations

import os
from typing import Any

_PROVIDER_ENV_MAP: dict[str, dict[str, str]] = {
    "openai": {"api_key": "OPENAI_API_KEY", "base_url": "OPENAI_BASE_URL"},
    "anthropic": {"api_key": "ANTHROPIC_API_KEY", "base_url": "ANTHROPIC_BASE_URL"},
    "deepseek": {"api_key": "DEEPSEEK_API_KEY", "base_url": "DEEPSEEK_BASE_URL"},
    "kimi": {"api_key": "KIMI_API_KEY", "base_url": "KIMI_BASE_URL"},
    "gemini": {"api_key": "GEMINI_API_KEY", "base_url": "GEMINI_BASE_URL"},
    "ollama": {"api_key": "", "base_url": "OLLAMA_BASE_URL"},
    "mistral": {"api_key": "MISTRAL_API_KEY", "base_url": "MISTRAL_BASE_URL"},
    "groq": {"api_key": "GROQ_API_KEY", "base_url": "GROQ_BASE_URL"},
    "together": {"api_key": "TOGETHER_API_KEY", "base_url": "TOGETHER_BASE_URL"},
    "perplexity": {"api_key": "PERPLEXITY_API_KEY", "base_url": "PERPLEXITY_BASE_URL"},
    "cohere": {"api_key": "COHERE_API_KEY", "base_url": "COHERE_BASE_URL"},
    "azure_openai": {"api_key": "AZURE_OPENAI_API_KEY", "base_url": "AZURE_OPENAI_BASE_URL"},
    "qwen": {"api_key": "QWEN_API_KEY", "base_url": "QWEN_BASE_URL"},
}


def resolve_env(provider: str) -> dict[str, str]:
    mapping = _PROVIDER_ENV_MAP.get(provider, _PROVIDER_ENV_MAP.get("openai", {}))
    result: dict[str, str] = {}
    for key, env_var in mapping.items():
        if env_var:
            val = os.environ.get(env_var, "")
            if val:
                result[key] = val
    return result


def default_base_url(provider: str) -> str:
    defaults: dict[str, str] = {
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "gemini": "https://generativelanguage.googleapis.com/v1beta",
        "ollama": "http://127.0.0.1:11434/v1",
        "mistral": "https://api.mistral.ai/v1",
        "groq": "https://api.groq.com/openai/v1",
    }
    return defaults.get(provider, "http://127.0.0.1:11434/v1")
