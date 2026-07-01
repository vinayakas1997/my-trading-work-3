"""Provider HTTP retry helper (TASK-S03)."""

from __future__ import annotations

import functools
import logging
import time
from typing import Callable, TypeVar

import requests

LOG = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable)


def retry_on_transient(
    n: int = 3,
    backoff: float = 1.5,
    *,
    exceptions: tuple[type[BaseException], ...] = (
        requests.Timeout,
        requests.ConnectionError,
    ),
) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = 1.0
            last_exc: BaseException | None = None
            for attempt in range(1, n + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt >= n:
                        break
                    LOG.warning(
                        "Transient provider error (attempt %s/%s): %s",
                        attempt,
                        n,
                        exc,
                    )
                    time.sleep(delay)
                    delay *= backoff
            if last_exc is not None:
                raise last_exc
            return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def http_get_with_retry(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = 30.0,
    n: int = 3,
    backoff: float = 1.5,
) -> requests.Response:
    @retry_on_transient(n=n, backoff=backoff)
    def _get() -> requests.Response:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code in (429, 500, 502, 503, 504):
            raise requests.ConnectionError(f"HTTP {resp.status_code}")
        resp.raise_for_status()
        return resp

    return _get()
