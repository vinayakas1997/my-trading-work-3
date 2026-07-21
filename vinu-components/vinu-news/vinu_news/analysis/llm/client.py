"""OpenAI-compatible LLM HTTP client — delegates to vinu_lib.llm."""

from __future__ import annotations

from typing import Any

from vinu_news.config import VinuConfig, load_config
from vinu_lib.llm import LlmClient as SharedLlmClient, LlmConfig

LOG = None  # unused, logging is handled by vinu_lib.llm


class LlmClientError(RuntimeError):
    pass


class LlmClient:
    def __init__(self, config: VinuConfig | None = None) -> None:
        cfg = config or load_config()
        self._config = cfg
        llm_cfg = LlmConfig(
            base_url=cfg.llm_base_url,
            model=cfg.llm_model,
            api_key=cfg.llm_api_key,
            max_tokens=cfg.llm_max_tokens,
            timeout_sec=300.0,
            ttl_sec=cfg.llm_ttl_sec,
            data_root=str(cfg.db_path.parent),
            rate_limit=30,
            rate_period_sec=60.0,
        )
        self._client = SharedLlmClient(llm_cfg, service="vinu-news")

    def is_configured(self) -> bool:
        return bool(self._config.llm_base_url and self._config.llm_model)

    def chat_json(self, system: str, user: str) -> dict[str, Any]:
        if not self.is_configured():
            raise LlmClientError("LLM not configured (VINU_LLM_BASE_URL / VINU_LLM_MODEL)")
        result = self._client.chat_json(system, user)
        if result is None:
            raise LlmClientError("LLM request failed (all endpoints tried)")
        return result
