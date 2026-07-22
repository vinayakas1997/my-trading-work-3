from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from vinu_lib.llm.cache import LlmCache
from vinu_lib.llm.config import LlmConfig
from vinu_lib.llm.docker import alternative_urls, is_running_in_docker
from vinu_lib.llm.providers import detect_provider, get_capabilities
from vinu_lib.rate_limit import TokenBucket

LOG = logging.getLogger(__name__)


def _log_llm_call(
    log_path: Path,
    service: str,
    model: str,
    base_url: str,
    system: str,
    user: str,
    duration_sec: float,
    response: Any,
    success: bool,
    error: str | None,
) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "service": service,
        "event": "llm_call",
        "model": model,
        "base_url": base_url,
        "system_prompt": system,
        "user_prompt": user,
        "response": response,
        "duration_sec": round(duration_sec, 3),
        "success": success,
        "error": error,
    }
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as exc:
        LOG.warning("Failed to write llm_calls.jsonl: %s", exc)


def _parse_json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


class LlmClient:
    def __init__(
        self,
        config: LlmConfig | None = None,
        service: str = "vinu-lib",
        session: requests.Session | None = None,
    ) -> None:
        self._config = config or LlmConfig.from_env()
        self._service = service
        self._session = session or requests.Session()

        self._provider = (
            detect_provider(self._config.model, self._config.base_url)
            if self._config.provider == "auto"
            else self._config.provider
        )
        self._caps = get_capabilities(self._provider)

        data_root = Path(self._config.data_root) if self._config.data_root else Path.cwd() / "data"
        self._log_path = data_root / "llm_calls.jsonl"

        cache_path = self._config.cache_path or str(data_root / "llm_cache.db")
        self._cache = LlmCache(cache_path, ttl_sec=self._config.ttl_sec)
        self._limiter = TokenBucket(rate=self._config.rate_limit, per=self._config.rate_period_sec)

        self._in_docker = is_running_in_docker()

    def is_configured(self) -> bool:
        return bool(self._config.base_url and self._config.model)

    def chat_json(self, system: str, user: str) -> dict[str, Any] | None:
        if not self.is_configured():
            LOG.warning("LLM not configured (VINU_LLM_BASE_URL / VINU_LLM_MODEL)")
            return None

        cache_key = hashlib.md5((system + user).encode()).hexdigest()
        if self._config.ttl_sec > 0:
            cached = self._cache.get(cache_key)
            if cached is not None:
                LOG.debug("LLM cache hit for %s", cache_key[:8])
                _log_llm_call(
                    self._log_path, self._service, self._config.model, self._config.base_url,
                    system, user, 0.0, cached, True, None,
                )
                return cached

        start = time.perf_counter()
        self._limiter.wait()

        payload = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": self._config.max_tokens,
        }
        if self._caps and self._caps.temperature_override is not None:
            payload["temperature"] = self._caps.temperature_override

        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"

        candidates = alternative_urls(self._config.base_url) if self._in_docker else [self._config.base_url]

        last_error: Exception | None = None
        for candidate_base in candidates:
            url = candidate_base.rstrip("/") + "/chat/completions"
            for attempt in range(self._config.retry_max):
                try:
                    resp = self._session.post(
                        url,
                        headers=headers,
                        json=payload,
                        timeout=self._config.timeout_sec,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = _parse_json_content(content)

                    if self._config.ttl_sec > 0:
                        self._cache.set(cache_key, parsed)
                    _log_llm_call(
                        self._log_path, self._service, self._config.model, candidate_base,
                        system, user, time.perf_counter() - start, parsed, True, None,
                    )
                    return parsed
                except requests.ConnectionError as e:
                    last_error = e
                    LOG.debug("LLM connection failed to %s: %s", candidate_base, e)
                    if attempt < self._config.retry_max - 1:
                        delay = (2 ** attempt) * 1.0
                        LOG.warning("LLM retrying in %.1fs (attempt %d/%d)", delay, attempt + 1, self._config.retry_max)
                        time.sleep(delay)
                        continue
                    break
                except requests.RequestException as e:
                    last_error = e
                    status = e.response.status_code if hasattr(e, 'response') and e.response is not None else None
                    is_transient = status is not None and (status == 429 or status >= 500)
                    if is_transient and attempt < self._config.retry_max - 1:
                        delay = (2 ** attempt) * 1.0
                        LOG.warning("LLM HTTP %d on %s, retrying in %.1fs (attempt %d/%d)",
                                    status, candidate_base, delay, attempt + 1, self._config.retry_max)
                        time.sleep(delay)
                        continue
                    LOG.warning("LLM request failed to %s: %s", candidate_base, e)
                    break
                except (KeyError, json.JSONDecodeError) as e:
                    last_error = e
                    LOG.warning("LLM response parse failed: %s", e)
                    error_msg = str(e)
                    _log_llm_call(
                        self._log_path, self._service, self._config.model, candidate_base,
                        system, user, time.perf_counter() - start, None, False, error_msg,
                    )
                    return None

        _log_llm_call(
            self._log_path, self._service, self._config.model, self._config.base_url,
            system, user, time.perf_counter() - start, None, False,
            str(last_error) if last_error else "all endpoints failed",
        )
        LOG.warning("LLM call failed after trying %d endpoints x %d retries: %s",
                    len(candidates), self._config.retry_max, last_error)
        return None

    def close(self) -> None:
        self._session.close()
        self._cache.close()
