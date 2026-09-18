from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from vinu_infra.debug import debug_timer
from vinu_infra.llm.cache import LlmCache
from vinu_infra.llm.config import LlmConfig
from vinu_infra.llm.docker import alternative_urls, is_running_in_docker
from vinu_infra.llm.cost import CostEntry, TokenUsage, get_global_cost_tracker
from vinu_infra.llm.providers import detect_provider, get_capabilities
from vinu_infra.llm.retry import LlmCallFailed, LlmParseError, build_async_retry
from vinu_infra.rate_limit import TokenBucket
from vinu_infra.telemetry import LLMCallRecord, get_telemetry_store, record_llm_call_safe

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
    token_usage: TokenUsage | None = None,
    estimated_cost: float = 0.0,
) -> None:
    entry: dict[str, Any] = {
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
    if token_usage is not None:
        entry["token_usage"] = {
            "prompt": token_usage.prompt_tokens,
            "completion": token_usage.completion_tokens,
            "total": token_usage.total_tokens,
        }
        entry["estimated_cost_usd"] = estimated_cost
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


def _should_retry(exc: BaseException) -> bool:
    """Same policy as the sync client's predicate, ported to httpx's
    exception hierarchy: httpx.ConnectError/other RequestError subtypes
    always retry (matches the original unconditional-retry branches for
    both), httpx.HTTPStatusError only for 429/5xx, LlmParseError always
    (the gap nothing retried before this module existed)."""
    if isinstance(exc, LlmParseError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    if isinstance(exc, httpx.RequestError):
        return True
    return False


class AsyncLlmClient:
    def __init__(
        self,
        config: LlmConfig | None = None,
        service: str = "vinu-infra",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config or LlmConfig.from_env()
        self._service = service
        self._http = http_client or httpx.AsyncClient(timeout=self._config.timeout_sec)

        self._provider = (
            detect_provider(self._config.model, self._config.base_url)
            if self._config.provider == "auto"
            else self._config.provider
        )
        self._caps = get_capabilities(self._provider)

        data_root = Path(self._config.data_root) if self._config.data_root else Path.cwd() / "data"
        self._log_path = data_root / "llm_calls.jsonl"
        self._telemetry_db_path = data_root / "telemetry.db"

        cache_path = self._config.cache_path or str(data_root / "llm_cache.db")
        self._cache = LlmCache(cache_path, ttl_sec=self._config.ttl_sec)
        self._limiter = TokenBucket(rate=self._config.rate_limit, per=self._config.rate_period_sec)

        self._in_docker = is_running_in_docker()

    def is_configured(self) -> bool:
        return bool(self._config.base_url and self._config.model)

    async def chat_json(self, system: str, user: str) -> dict[str, Any]:
        """Raises `LlmCallFailed` (never returns `None`) once every
        candidate endpoint has exhausted its retries -- callers must
        handle the failure explicitly instead of being able to mistake a
        `None` for a real, empty answer."""
        if not self.is_configured():
            msg = "LLM not configured (VINU_LLM_BASE_URL / VINU_LLM_MODEL)"
            LOG.warning(msg)
            raise LlmCallFailed(msg)

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
        await self._limiter.wait_async()

        async with debug_timer(f"llm.{self._config.model}"):
            return await self._chat_request(system, user, cache_key, start)

    async def _chat_request(self, system: str, user: str, cache_key: str, start: float) -> dict[str, Any]:
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
        total_attempts = 0

        for candidate_base in candidates:
            url = candidate_base.rstrip("/") + "/chat/completions"
            attempts_this_candidate = {"n": 0}

            async def _attempt() -> tuple[dict[str, Any], TokenUsage]:
                attempts_this_candidate["n"] += 1
                resp = await self._http.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                try:
                    content = data["choices"][0]["message"]["content"]
                    parsed = _parse_json_content(content)
                except (KeyError, json.JSONDecodeError) as e:
                    raise LlmParseError(str(e)) from e
                return parsed, TokenUsage.from_api_response(data)

            try:
                parsed, token_usage = await build_async_retry(self._config.retry_max, _should_retry)(_attempt)
            except Exception as e:
                last_error = e
                total_attempts += attempts_this_candidate["n"]
                LOG.debug(
                    "LLM call to %s failed after %d attempt(s): %s",
                    candidate_base, attempts_this_candidate["n"], e,
                )
                continue

            total_attempts += attempts_this_candidate["n"]
            cost = self._caps.estimate_cost(
                self._config.model, token_usage.prompt_tokens, token_usage.completion_tokens,
            ) if self._caps else 0.0

            if self._config.ttl_sec > 0:
                self._cache.set(cache_key, parsed)
            _log_llm_call(
                self._log_path, self._service, self._config.model, candidate_base,
                system, user, time.perf_counter() - start, parsed, True, None,
                token_usage=token_usage, estimated_cost=cost,
            )
            get_global_cost_tracker().record(CostEntry(
                ts=datetime.now(timezone.utc).isoformat(),
                service=self._service,
                model=self._config.model,
                provider=self._provider,
                prompt_tokens=token_usage.prompt_tokens,
                completion_tokens=token_usage.completion_tokens,
                total_tokens=token_usage.total_tokens,
                estimated_cost_usd=cost,
                duration_sec=time.perf_counter() - start,
                success=True,
            ))
            record_llm_call_safe(
                LLMCallRecord(
                    service=self._service,
                    model=self._config.model,
                    base_url=candidate_base,
                    prompt_tokens=token_usage.prompt_tokens,
                    completion_tokens=token_usage.completion_tokens,
                    total_tokens=token_usage.total_tokens,
                    token_count_source="provider",
                    retry_count=total_attempts - 1,
                    latency_sec=time.perf_counter() - start,
                    success=True,
                    outcome="completed",
                ),
                db_path=self._telemetry_db_path,
            )
            return parsed

        error_msg = str(last_error) if last_error else "all endpoints failed"
        _log_llm_call(
            self._log_path, self._service, self._config.model, self._config.base_url,
            system, user, time.perf_counter() - start, None, False, error_msg,
        )
        LOG.warning("LLM call failed after trying %d endpoint(s) x %d retries: %s",
                    len(candidates), self._config.retry_max, last_error)
        outcome = "parse_error" if isinstance(last_error, LlmParseError) else "all_endpoints_failed"
        record_llm_call_safe(
            LLMCallRecord(
                service=self._service,
                model=self._config.model,
                base_url=self._config.base_url,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                token_count_source="provider",
                retry_count=total_attempts - 1,
                latency_sec=time.perf_counter() - start,
                success=False,
                outcome=outcome,
                error=error_msg,
            ),
            db_path=self._telemetry_db_path,
        )
        raise LlmCallFailed(error_msg, last_error=last_error)

    async def close(self) -> None:
        await self._http.aclose()
        self._cache.close()
        # See LlmClient.close() (client.py) -- same fix: TelemetryStore.close()
        # exists to release telemetry.db's sqlite connection (Windows won't
        # delete a file with an open connection) but was never wired up here.
        get_telemetry_store(self._telemetry_db_path).close()
