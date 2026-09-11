"""Stage B (B9): `call_with_timeout` — a daemon-thread guard for bounding
a flaky upstream fetch call.

Ported from daily_stock_analysis's `source_guard.py` pattern. At
~8000-symbol scale, some fraction of per-symbol fetches (here, `GET
/candles/{symbol}` against vinu-stock-price — confirmed there's no bulk
endpoint, so a scan cycle really is ~8000 individual calls) will hang far
longer than the median: a slow upstream provider, a network blip, a
misbehaving retry inside the HTTP client. One hung call must not stall the
whole cycle.

Python has no safe way to forcibly kill a running thread, so this doesn't
try to — the worker thread is started as a daemon and, on timeout, simply
abandoned (it either finishes harmlessly in the background and its result
is discarded, or the interpreter exits and takes it with it). What the
caller gets back is a `TimeoutResult` with `timed_out=True` immediately at
the deadline, not "eventually, whenever the slow call finishes."
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class TimeoutResult:
    ok: bool
    value: Any = None
    error: str | None = None
    timed_out: bool = False
    latency_ms: float = 0.0


def call_with_timeout(
    fn: Callable[..., Any],
    *args: Any,
    timeout_sec: float = 5.0,
    **kwargs: Any,
) -> TimeoutResult:
    """Run `fn(*args, **kwargs)` on a daemon thread, wait at most
    `timeout_sec`. Never raises — a fetch failure or timeout is reported in
    the returned `TimeoutResult`, exactly like every other fail-open
    upstream-dependent check in this codebase."""
    box: dict[str, Any] = {}

    def _run() -> None:
        try:
            box["value"] = fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 -- reported, not raised, to the caller
            box["error"] = str(exc)

    start = time.monotonic()
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    thread.join(timeout_sec)
    latency_ms = (time.monotonic() - start) * 1000.0

    if thread.is_alive():
        return TimeoutResult(ok=False, timed_out=True, error=f"timed out after {timeout_sec:g}s", latency_ms=latency_ms)
    if "error" in box:
        return TimeoutResult(ok=False, error=box["error"], latency_ms=latency_ms)
    return TimeoutResult(ok=True, value=box.get("value"), latency_ms=latency_ms)
