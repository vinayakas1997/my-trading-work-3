from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager, contextmanager
from typing import Any

_DEBUG = os.environ.get("VINU_DEBUG", "false").lower() in ("true", "1", "yes")


def is_debug() -> bool:
    return _DEBUG


def setup_logging(service: str, *, verbose: bool = False) -> None:
    """Unified logging setup for all services.

    When VINU_DEBUG=true the root level is DEBUG with a full timestamped format
    that includes the logger name.  Otherwise it is INFO with a compact format.
    """
    if _DEBUG or verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    fmt = (
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        if _DEBUG
        else "%(asctime)s %(levelname)s %(message)s"
    )
    logging.basicConfig(level=level, format=fmt)


def debug_log(msg: str, *args: Any) -> None:
    """Print a debug message only when VINU_DEBUG=true."""
    if _DEBUG:
        if args:
            msg = msg % args
        print(f"[DEBUG] {msg}", flush=True)


_INDENT = 0


def _indent() -> str:
    return "  " * _INDENT


@contextmanager
def sync_timer(label: str):
    """Synchronous context manager for timing blocks."""
    global _INDENT
    if not _DEBUG:
        yield
        return
    t0 = time.perf_counter()
    _INDENT += 1
    print(f"{_indent()}[TIMER] {label} START", flush=True)
    try:
        yield
    finally:
        dt = time.perf_counter() - t0
        _INDENT -= 1
        print(f"{_indent()}[TIMER] {label} END ({dt:.2f}s)", flush=True)


@asynccontextmanager
async def debug_timer(label: str):
    """Async context manager ― logs START / END with wall‑clock duration.

    Nested timers are indented to create a readable call tree.
    """
    global _INDENT
    if not _DEBUG:
        yield
        return
    t0 = time.perf_counter()
    _INDENT += 1
    print(f"{_indent()}[TIMER] {label} START", flush=True)
    try:
        yield
    finally:
        dt = time.perf_counter() - t0
        _INDENT -= 1
        print(f"{_indent()}[TIMER] {label} END ({dt:.2f}s)", flush=True)
