"""Per-tool-instance in-memory cache for repeated identical fetches
within one agent run -- item #11 finding #4
(missing-pieces-of-system/new-theory-of-trading/system-wide-audit-and-
design/02-open-questions-strategy-and-simulation.md): stock_price_tool.py,
news_tool.py, options_tool.py, and fundamentals_tool.py all re-fetched
fresh on every execute() call, even when one agent loop asked for the
exact same symbol/range twice.

Scoped to the tool instance's own lifetime, not process-global or
cross-session: `tools/__init__.py::build_registry()` constructs a fresh
tool instance per run, each with its own fixed `_as_of` -- so caching on
`self` can never leak a stale response across two different replay
instants or two different sessions the way a module-level or class-level
cache would. No LRU/size cap needed for the same reason: one run's
realistic call volume for one tool is small, and the cache is discarded
along with the tool instance at the end of the run.
"""

from __future__ import annotations

from typing import Any


class CallCache:
    def __init__(self) -> None:
        self._store: dict[tuple[Any, ...], str] = {}

    def get(self, key: tuple[Any, ...]) -> str | None:
        return self._store.get(key)

    def set(self, key: tuple[Any, ...], value: str) -> None:
        self._store[key] = value
