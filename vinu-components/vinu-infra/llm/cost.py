from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> TokenUsage:
        usage = data.get("usage") if isinstance(data, dict) else None
        if usage and isinstance(usage, dict):
            return cls(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            )
        return cls()


@dataclass
class CostEntry:
    ts: str
    service: str
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    duration_sec: float
    success: bool


class CostTracker:
    """Real fix: this used to append every real `CostEntry` to an
    ever-growing `list`, unbounded, for the lifetime of the process, then
    re-scan the whole list on every `summary()`/`total_cost_usd` call.
    `get_global_cost_tracker()` is a process-wide singleton and `reset()`
    is never called anywhere in production code (confirmed by a repo-wide
    grep) -- so a real long-running service making thousands of LLM calls
    over days/weeks grew this list forever, and every aggregate read got
    slower as it grew (an O(n) scan under a lock, blocking concurrent
    `record()` calls for longer each time). Capping/evicting old entries
    isn't a safe fix either -- `total_cost_usd` is meant to be the true
    cumulative total, and silently dropping old entries would make it
    quietly wrong (a misleading number is worse than a slow one). The real
    fix: maintain the aggregates themselves incrementally (O(1) per
    `record()` call, O(1) memory), not the raw entries."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total_calls = 0
        self._successful_calls = 0
        self._total_tokens = 0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._total_cost_usd = 0.0
        self._calls_by_model: dict[str, int] = {}
        self._calls_by_service: dict[str, int] = {}

    def record(self, entry: CostEntry) -> None:
        with self._lock:
            self._total_calls += 1
            if entry.success:
                self._successful_calls += 1
            self._total_tokens += entry.total_tokens
            self._prompt_tokens += entry.prompt_tokens
            self._completion_tokens += entry.completion_tokens
            self._total_cost_usd += entry.estimated_cost_usd
            self._calls_by_model[entry.model] = self._calls_by_model.get(entry.model, 0) + 1
            self._calls_by_service[entry.service] = self._calls_by_service.get(entry.service, 0) + 1

    @property
    def total_cost_usd(self) -> float:
        with self._lock:
            return round(self._total_cost_usd, 6)

    @property
    def total_tokens(self) -> int:
        with self._lock:
            return self._total_tokens

    @property
    def total_calls(self) -> int:
        with self._lock:
            return self._total_calls

    @property
    def successful_calls(self) -> int:
        with self._lock:
            return self._successful_calls

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_calls": self._total_calls,
                "successful_calls": self._successful_calls,
                "total_tokens": self._total_tokens,
                "prompt_tokens": self._prompt_tokens,
                "completion_tokens": self._completion_tokens,
                "total_cost_usd": round(self._total_cost_usd, 6),
                "calls_by_model": dict(self._calls_by_model),
                "calls_by_service": dict(self._calls_by_service),
            }

    def reset(self) -> None:
        with self._lock:
            self._total_calls = 0
            self._successful_calls = 0
            self._total_tokens = 0
            self._prompt_tokens = 0
            self._completion_tokens = 0
            self._total_cost_usd = 0.0
            self._calls_by_model.clear()
            self._calls_by_service.clear()


_global_tracker: CostTracker | None = None
_tracker_lock = threading.Lock()


def get_global_cost_tracker() -> CostTracker:
    global _global_tracker
    if _global_tracker is None:
        with _tracker_lock:
            if _global_tracker is None:
                _global_tracker = CostTracker()
    return _global_tracker
