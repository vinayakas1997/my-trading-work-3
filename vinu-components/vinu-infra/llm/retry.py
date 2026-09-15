"""Shared retry policy for every LLM call site in the vinu system.

Built on tenacity instead of the three hand-rolled retry loops this
replaces (vinu-infra's sync/async clients, vinu-agent's per-provider
ChatLLM classes) -- see
missing-pieces-of-system/llm-configuration-settings-system/ for why.

Each call site supplies its own `should_retry` predicate (exception
types differ per underlying HTTP/SDK library -- requests vs httpx vs
the openai/anthropic SDKs vs a raw Ollama request), but the actual
policy (how many attempts, how long to wait, how to honor a Retry-After
header) lives here once, not copied per call site.
"""

from __future__ import annotations

import logging
import random
from typing import Callable

from tenacity import (
    AsyncRetrying,
    RetryCallState,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
)

LOG = logging.getLogger(__name__)


class LlmCallFailed(Exception):
    """Raised when an LLM call fails after every retry attempt is
    exhausted. Callers must handle this explicitly -- it is never a
    silent `None`/fake value a caller could mistake for a real answer
    (the gap that let forecast_skill.py substitute a fake neutral
    forecast for an actual LLM failure)."""

    def __init__(self, message: str, *, last_error: BaseException | None = None) -> None:
        super().__init__(message)
        self.last_error = last_error


class LlmParseError(Exception):
    """Raised when an LLM response can't be parsed as JSON. Treated as a
    retryable failure -- a malformed response deserves the same second
    chance a dropped connection already gets, which nothing did before
    this module existed (every prior retry loop only retried on
    connection/HTTP errors, never on a parse failure)."""


def _retry_after_seconds(exc: BaseException) -> float | None:
    """Duck-typed against `.response.headers` -- works for both
    `requests.RequestException` and `httpx.HTTPStatusError` without a
    per-client special case, since both expose case-insensitive header
    access the same way."""
    resp = getattr(exc, "response", None)
    if resp is None:
        return None
    headers = getattr(resp, "headers", None)
    if headers is None:
        return None
    try:
        raw = (headers.get("retry-after") or "").strip()
        return float(raw) if raw else None
    except (ValueError, AttributeError):
        return None


def _wait(retry_state: RetryCallState) -> float:
    """Exponential backoff (1s, 2s, 4s, ...) with jitter, extended to
    honor a Retry-After header when the failing exception carries one --
    ports the hand-rolled logic previously duplicated in
    vinu-infra/llm/client.py and client_async.py."""
    attempt = max(retry_state.attempt_number - 1, 0)
    delay = (2**attempt) * 1.0
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if exc is not None:
        retry_after = _retry_after_seconds(exc)
        if retry_after is not None:
            delay = min(max(delay, retry_after), 120.0)
            delay += random.uniform(0, 1.0)
    return delay


def _before_sleep(retry_state: RetryCallState) -> None:
    """Logs each retry the way the hand-rolled loops this replaces used
    to (attempt count, exception, computed delay) -- tenacity itself
    stays silent by default, and losing that operational visibility
    would be a regression, not a cleanup."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    delay = retry_state.upcoming_sleep
    LOG.warning(
        "LLM call failed (%s: %s), retrying in %.1fs (attempt %d)",
        type(exc).__name__ if exc else "unknown", exc, delay, retry_state.attempt_number,
    )


def build_retry(retry_max: int, should_retry: Callable[[BaseException], bool]) -> Retrying:
    """Sync retry controller. Use as:

        retryer = build_retry(retry_max, my_predicate)
        result = retryer(my_request_fn, *args, **kwargs)

    Takes a plain `retry_max: int` (not a full `LlmConfig`) so any caller
    can use this -- including vinu-agent's `ChatLLM` classes, which have
    their own `retry_max` constructor param and no `LlmConfig` of their
    own.

    `reraise=True` means the underlying exception propagates as-is on
    final exhaustion (not wrapped in tenacity's own RetryError) -- each
    call site decides what to do with that (client.py/client_async.py
    wrap it in LlmCallFailed; vinu-agent's ChatLLM classes wrap it in
    their own existing RuntimeError, unchanged)."""
    return Retrying(
        stop=stop_after_attempt(max(retry_max, 1)),
        wait=_wait,
        retry=retry_if_exception(should_retry),
        before_sleep=_before_sleep,
        reraise=True,
    )


def build_async_retry(retry_max: int, should_retry: Callable[[BaseException], bool]) -> AsyncRetrying:
    """Async counterpart of build_retry -- same policy, awaitable:

        retryer = build_async_retry(retry_max, my_predicate)
        result = await retryer(my_async_request_fn, *args, **kwargs)
    """
    return AsyncRetrying(
        stop=stop_after_attempt(max(retry_max, 1)),
        wait=_wait,
        retry=retry_if_exception(should_retry),
        before_sleep=_before_sleep,
        reraise=True,
    )
