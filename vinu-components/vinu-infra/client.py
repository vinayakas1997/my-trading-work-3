"""Resilient HTTP client with circuit breaker, retry, and fallback."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

import httpx

from vinu_lib.debug import debug_timer

LOG = logging.getLogger(__name__)

_CircuitState = str
_STATE_CLOSED: _CircuitState = "closed"
_STATE_OPEN: _CircuitState = "open"
_STATE_HALF_OPEN: _CircuitState = "half_open"


class CircuitBreaker:
    """Simple circuit breaker for async use.

    States: closed (normal) → open (tripped) → half-open (probing) → closed.
    """

    def __init__(
        self,
        threshold: int = 3,
        recovery_timeout: float = 30.0,
    ) -> None:
        self._threshold = threshold
        self._recovery_timeout = recovery_timeout
        self._failures = 0
        self._state: _CircuitState = _STATE_CLOSED
        self._last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

    async def call(self, fn: Callable[[], Any], fallback: Any = None) -> Any:
        state, _ = await self._check_state()
        if state == _STATE_OPEN:
            LOG.warning("Circuit breaker OPEN for %s — using fallback", fn.__name__ if hasattr(fn, "__name__") else "")
            return fallback

        try:
            result = await fn()
        except Exception as e:
            await self._record_failure()
            LOG.warning("Request failed (%s), failure %d/%d", e, self._failures, self._threshold)
            state, _ = await self._check_state()
            if state == _STATE_OPEN:
                return fallback
            raise

        await self._record_success()
        return result

    async def _check_state(self) -> tuple[_CircuitState, int]:
        async with self._lock:
            if self._state == _STATE_OPEN:
                if asyncio.get_event_loop().time() - self._last_failure_time >= self._recovery_timeout:
                    self._state = _STATE_HALF_OPEN
                    LOG.info("Circuit breaker HALF-OPEN — probing")
            return self._state, self._failures

    async def _record_failure(self) -> None:
        async with self._lock:
            self._failures += 1
            self._last_failure_time = asyncio.get_event_loop().time()
            if self._failures >= self._threshold:
                self._state = _STATE_OPEN
                LOG.warning("Circuit breaker OPEN after %d failures", self._failures)

    async def _record_success(self) -> None:
        async with self._lock:
            if self._state == _STATE_HALF_OPEN:
                LOG.info("Circuit breaker CLOSED — probe succeeded")
            self._state = _STATE_CLOSED
            self._failures = 0


class ResilientClient:
    """Async HTTP client with circuit breaker, retry, and optional fallback.

    Usage:
        client = ResilientClient("http://localhost:8080", "my-service")
        data = await client.get("/health", fallback={"ok": False})
        result = await client.post("/data", json={"key": "value"})
        await client.close()
    """

    def __init__(
        self,
        base_url: str,
        service_name: str,
        *,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
        circuit_breaker_threshold: int = 3,
        circuit_breaker_timeout: float = 30.0,
        fallback: Any = None,
        allow_local: bool = True,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._service_name = service_name
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._default_fallback = fallback
        self._http = httpx.AsyncClient(timeout=timeout, headers=headers)
        self._breaker = CircuitBreaker(
            threshold=circuit_breaker_threshold,
            recovery_timeout=circuit_breaker_timeout,
        )
        self._allow_local = allow_local

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def service_name(self) -> str:
        return self._service_name

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        fallback: Any = None,
    ) -> Any:
        url = f"{self._base_url}{path}"
        if not self._allow_local:
            from vinu_lib.security.network import validate_url_target
            if not validate_url_target(url):
                raise ValueError(f"URL target failed SSRF security validation: {url}")
        fb = fallback if fallback is not None else self._default_fallback
        try:
            return await self._breaker.call(
                lambda: self._request("GET", path, params=params),
                fallback=fb,
            )
        except ValueError:
            raise
        except Exception:
            return fb

    async def post(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        fallback: Any = None,
    ) -> Any:
        url = f"{self._base_url}{path}"
        if not self._allow_local:
            from vinu_lib.security.network import validate_url_target
            if not validate_url_target(url):
                raise ValueError(f"URL target failed SSRF security validation: {url}")
        fb = fallback if fallback is not None else self._default_fallback
        try:
            return await self._breaker.call(
                lambda: self._request("POST", path, json=json),
                fallback=fb,
            )
        except ValueError:
            raise
        except Exception:
            return fb

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self._base_url}{path}"
        label = f"http.{method} {url}"
        async with debug_timer(label):
            return await self._request_impl(method, path, **kwargs)

    async def _request_impl(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self._base_url}{path}"
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                resp = await self._http.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                last_exc = e
                LOG.warning(
                    "HTTP %d on %s %s (attempt %d/%d)",
                    e.response.status_code, method, url,
                    attempt + 1, self._max_retries,
                )
                if e.response.status_code < 500:
                    raise
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_exc = e
                LOG.warning(
                    "%s on %s %s (attempt %d/%d)",
                    type(e).__name__, method, url,
                    attempt + 1, self._max_retries,
                )
            except Exception as e:
                last_exc = e
                LOG.warning("Unexpected error on %s %s: %s", method, url, e)
                raise
            if attempt < self._max_retries - 1:
                await asyncio.sleep(self._retry_backoff * (2 ** attempt))
        raise RuntimeError(
            f"Request failed after {self._max_retries} attempts to {method} {url}: {last_exc}"
        ) from last_exc

    async def health(self) -> bool:
        try:
            resp = await self._http.get(f"{self._base_url}/health", timeout=5.0)
            return resp.status_code < 500
        except Exception:
            return False

    async def close(self) -> None:
        await self._http.aclose()
