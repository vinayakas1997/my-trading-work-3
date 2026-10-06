"""Who is asking, and why: the two facts the LLM gateway needs to order its queue.

Every LLM client adds `X-Vinu-Caller` (the service) and, when the surrounding code set one, `X-Vinu-Purpose`
(what the answer is for, e.g. `live_decision`). The purpose lives in a context variable so code far from the HTTP call
-- a worker thread that is about to run a live team -- can set it once for everything below it:

    with purpose_scope("live_decision"):
        run_team(...)

Without a purpose the gateway uses the caller's default (see vinu_llm_gateway.priorities). Only the gateway turns a
purpose into a priority, so setting one cannot make a call jump the queue unless the table says it may.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from typing import Any, Callable, Iterator

_PURPOSE: ContextVar[str | None] = ContextVar("vinu_llm_purpose", default=None)


@contextmanager
def purpose_scope(purpose: str) -> Iterator[None]:
    token = _PURPOSE.set(purpose)
    try:
        yield
    finally:
        _PURPOSE.reset(token)


def current_purpose() -> str | None:
    return _PURPOSE.get()


def llm_identity_headers(caller: str) -> dict[str, str]:
    headers = {"X-Vinu-Caller": caller}
    purpose = _PURPOSE.get()
    if purpose:
        headers["X-Vinu-Purpose"] = purpose
    return headers


def bind_context(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap `fn` so that, run later on another thread, it still sees the purpose set where it was wrapped.

    A thread pool does not inherit context variables: without this a tool call executed in a pool thread would reach the
    gateway with no purpose and fall to the caller's default priority, however urgent the team that started it."""
    ctx = copy_context()

    def runner(*args: Any, **kwargs: Any) -> Any:
        return ctx.run(fn, *args, **kwargs)

    return runner
