"""OpenAI-compatible LLM HTTP client (TASK-N01)."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import requests

from vinu_news.config import VinuConfig, load_config
from vinu_news.net import request as http_request

LOG = logging.getLogger(__name__)


class LlmClientError(RuntimeError):
    pass


def _log_llm_call(
    config: VinuConfig,
    system: str,
    user: str,
    duration_sec: float,
    response: Any,
    success: bool,
    error: str | None,
) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "service": "vinu-news",
        "event": "llm_call",
        "model": config.llm_model,
        "base_url": config.llm_base_url,
        "system_prompt": system,
        "user_prompt": user,
        "response": response,
        "duration_sec": round(duration_sec, 3),
        "success": success,
        "error": error,
    }
    try:
        log_path = config.db_path.parent / "llm_calls.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as exc:
        LOG.warning("Failed to write llm_calls.jsonl: %s", exc)


class LlmClient:
    def __init__(self, config: VinuConfig | None = None) -> None:
        self._config = config or load_config()

    def is_configured(self) -> bool:
        return bool(self._config.llm_base_url and self._config.llm_model)

    def chat_json(self, system: str, user: str) -> dict[str, Any]:
        if not self.is_configured():
            raise LlmClientError("LLM not configured (VINU_LLM_BASE_URL / VINU_LLM_MODEL)")
        url = self._config.llm_base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self._config.llm_api_key:
            headers["Authorization"] = f"Bearer {self._config.llm_api_key}"
        payload = {
            "model": self._config.llm_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": self._config.llm_max_tokens,
        }
        start = time.perf_counter()
        try:
            resp = http_request("POST", url, headers=headers, json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = _parse_json_content(content)
            _log_llm_call(self._config, system, user, time.perf_counter() - start, parsed, True, None)
            return parsed
        except (requests.RequestException, KeyError, json.JSONDecodeError) as exc:
            LOG.warning("LLM request failed: %s", exc)
            _log_llm_call(self._config, system, user, time.perf_counter() - start, None, False, str(exc))
            raise LlmClientError(str(exc)) from exc


def _parse_json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)
