from __future__ import annotations

import contextvars
import logging
import os
import time
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any

_DEBUG = os.environ.get("VINU_DEBUG", "false").lower() in ("true", "1", "yes")
_DEBUG_LEVEL = int(os.environ.get("VINU_DEBUG_LEVEL", "1"))
_DEBUG_LOGGER = logging.getLogger("vinu.debug")


def is_debug(level: int = 1) -> bool:
    return _DEBUG and _DEBUG_LEVEL >= level


def setup_logging(service: str, *, verbose: bool = False) -> None:
    """Unified logging setup for all services.

    Every service (`vinu-news`, `vinu-live`, `vinu-research`, ...) calls this once at
    startup with its own name. When VINU_DEBUG=true (or verbose=True), root level is
    DEBUG and every `logger.info/warning/error` call from every service -- plus
    `debug_log()` below -- is ALSO appended to one shared file, so a run spanning
    multiple service processes can be read back in one place, in timestamp order,
    instead of piecing together N separate consoles.

    File sink location: `VINU_LOG_FILE` env var if set, else `logs/vinu-trace.log`
    (relative to cwd) whenever VINU_DEBUG=true. Set `VINU_LOG_FILE=` (empty) to force
    console-only. Console output is unaffected either way.
    """
    level = logging.DEBUG if (_DEBUG or verbose) else logging.INFO
    fmt = f"%(asctime)s [{service}] [%(levelname)s] %(name)s: %(message)s"

    handlers: list[logging.Handler] = [logging.StreamHandler()]

    log_file = os.environ.get("VINU_LOG_FILE", "/tmp/logs/vinu-trace.log" if _DEBUG else "")
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(path, mode="a", encoding="utf-8"))

    # force=True: some services boot uvicorn/other libs that call basicConfig first;
    # without it this setup would silently no-op and every service would keep logging
    # to its own console only, defeating the point of a shared file.
    logging.basicConfig(level=level, format=fmt, handlers=handlers, force=True)


def debug_log(msg: str, level: int = 1) -> None:
    """Log a debug message only when VINU_DEBUG=true and VINU_DEBUG_LEVEL >= level.

    Level 1: step tracking, timing, budget warnings
    Level 2: LLM prompts/responses, memory context, evidence detail

    Goes through the same handlers `setup_logging()` configured -- console AND the
    shared file -- instead of a bare print() that only the console would ever see.
    """
    if _DEBUG and _DEBUG_LEVEL >= level:
        prefix = "[DEBUG1]" if level <= 1 else "[DEBUG2]"
        _DEBUG_LOGGER.debug("%s %s", prefix, msg)


# A plain module-level int here (the original implementation) is a real
# race condition: `debug_timer` wraps every HTTP request in
# `client.py`'s `ResilientClient`, so any two concurrent requests -- two
# threads, or two interleaved asyncio tasks on the same thread, which a
# plain int OR threading.local both fail to distinguish -- increment/
# decrement the SAME shared counter. Under real concurrency this doesn't
# just garble the log's indentation cosmetically: interleaved +1/-1 pairs
# from different requests can leave the counter permanently above 0,
# so indentation drifts deeper forever and never recovers. ContextVar is
# the correct primitive: each thread AND each asyncio task gets its own
# independent value, automatically, with no explicit propagation code.
_indent_var: contextvars.ContextVar[int] = contextvars.ContextVar("vinu_debug_indent", default=0)


def _indent() -> str:
    return "  " * _indent_var.get()


@contextmanager
def sync_timer(label: str):
    """Synchronous context manager for timing blocks."""
    if not _DEBUG:
        yield
        return
    t0 = time.perf_counter()
    token = _indent_var.set(_indent_var.get() + 1)
    debug_log(f"[TIMER] {label} START", level=1)
    try:
        yield
    finally:
        dt = time.perf_counter() - t0
        _indent_var.reset(token)
        debug_log(f"[TIMER] {label} END ({dt:.2f}s)", level=1)


@asynccontextmanager
async def debug_timer(label: str):
    """Async context manager ― logs START / END with wall‑clock duration.

    Nested timers are indented to create a readable call tree.
    """
    if not _DEBUG:
        yield
        return
    t0 = time.perf_counter()
    token = _indent_var.set(_indent_var.get() + 1)
    debug_log(f"[TIMER] {label} START", level=1)
    try:
        yield
    finally:
        dt = time.perf_counter() - t0
        _indent_var.reset(token)
        debug_log(f"[TIMER] {label} END ({dt:.2f}s)", level=1)
