from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vinu_infra.secrets_loader import load_secret


LLM_ENV_PREFIX = "VINU_LLM"

_DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"
_DEFAULT_MODEL = "llama3.2"
_DEFAULT_MAX_TOKENS = 8000
_DEFAULT_TIMEOUT_SEC = 300.0
_DEFAULT_TTL_SEC = 86400
_DEFAULT_RETRY_MAX = 3
_DEFAULT_CIRCUIT_THRESHOLD = 5
_DEFAULT_CIRCUIT_RECOVERY_SEC = 30.0
_DEFAULT_RATE_LIMIT = 10
_DEFAULT_RATE_PERIOD_SEC = 60.0


def _env(key: str, default: Any = None) -> str:
    return os.environ.get(f"{LLM_ENV_PREFIX}_{key}", str(default) if default is not None else "")


def _api_key() -> str | None:
    """LLM provider credential: mounted Docker secret file first (deploy),
    legacy VINU_LLM_API_KEY env fallback (local dev). The secret file name
    matches the docker-compose `secrets:` entry /run/secrets/vinu_llm_api_key."""
    return load_secret("vinu_llm_api_key", "VINU_LLM_API_KEY")


@dataclass
class LlmConfig:
    base_url: str = _DEFAULT_BASE_URL
    model: str = _DEFAULT_MODEL
    api_key: str | None = None
    max_tokens: int = _DEFAULT_MAX_TOKENS
    timeout_sec: float = _DEFAULT_TIMEOUT_SEC
    ttl_sec: int = _DEFAULT_TTL_SEC
    retry_max: int = _DEFAULT_RETRY_MAX
    circuit_threshold: int = _DEFAULT_CIRCUIT_THRESHOLD
    circuit_recovery_sec: float = _DEFAULT_CIRCUIT_RECOVERY_SEC
    rate_limit: int = _DEFAULT_RATE_LIMIT
    rate_period_sec: float = _DEFAULT_RATE_PERIOD_SEC
    data_root: str | None = None
    cache_path: str | None = None
    provider: str = "auto"

    @classmethod
    def from_env(cls, **overrides: Any) -> LlmConfig:
        return cls(
            base_url=overrides.get("base_url") or _env("BASE_URL", _DEFAULT_BASE_URL),
            model=overrides.get("model") or _env("MODEL", _DEFAULT_MODEL),
            api_key=overrides.get("api_key") or _api_key() or None,
            max_tokens=int(overrides.get("max_tokens") or _env("MAX_TOKENS", _DEFAULT_MAX_TOKENS)),
            timeout_sec=float(overrides.get("timeout_sec") or _env("TIMEOUT_SEC", _DEFAULT_TIMEOUT_SEC)),
            ttl_sec=int(overrides.get("ttl_sec") or _env("TTL_SEC", _DEFAULT_TTL_SEC)),
            retry_max=int(overrides.get("retry_max") or _env("RETRY_MAX", _DEFAULT_RETRY_MAX)),
            circuit_threshold=int(overrides.get("circuit_threshold") or _env("CIRCUIT_THRESHOLD", _DEFAULT_CIRCUIT_THRESHOLD)),
            circuit_recovery_sec=float(overrides.get("circuit_recovery_sec") or _env("CIRCUIT_RECOVERY_SEC", _DEFAULT_CIRCUIT_RECOVERY_SEC)),
            rate_limit=int(overrides.get("rate_limit") or _env("RATE_LIMIT", _DEFAULT_RATE_LIMIT)),
            rate_period_sec=float(overrides.get("rate_period_sec") or _env("RATE_PERIOD_SEC", _DEFAULT_RATE_PERIOD_SEC)),
            data_root=overrides.get("data_root") or _env("DATA_ROOT") or None,
            cache_path=overrides.get("cache_path") or _env("CACHE_PATH") or None,
            provider=overrides.get("provider") or _env("PROVIDER", "auto"),
        )

    def api_url(self) -> str:
        return self.base_url.rstrip("/") + "/chat/completions"
