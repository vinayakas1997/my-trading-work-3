"""Exponential backoff retry helper (mirrors vinu_stock/providers/retry.py pattern)."""

from __future__ import annotations

import functools
import logging
import time
from typing import Callable, TypeVar

LOG = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable)


class TransientError(Exception):
    """Transient error (rate limit, server error, connection drop) that can be retried."""


def retry_on_transient(
    n: int = 3,
    backoff: float = 1.5,
    *,
    exceptions: tuple[type[BaseException], ...] = (
        ConnectionError,
        TimeoutError,
        TransientError,
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
                        "Transient error (attempt %s/%s): %s",
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
