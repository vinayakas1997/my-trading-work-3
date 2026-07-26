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
    def __init__(self) -> None:
        self._entries: list[CostEntry] = []
        self._lock = threading.Lock()

    def record(self, entry: CostEntry) -> None:
        with self._lock:
            self._entries.append(entry)

    @property
    def total_cost_usd(self) -> float:
        with self._lock:
            return round(sum(e.estimated_cost_usd for e in self._entries), 6)

    @property
    def total_tokens(self) -> int:
        with self._lock:
            return sum(e.total_tokens for e in self._entries)

    @property
    def total_calls(self) -> int:
        with self._lock:
            return len(self._entries)

    @property
    def successful_calls(self) -> int:
        with self._lock:
            return sum(1 for e in self._entries if e.success)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_calls": len(self._entries),
                "successful_calls": sum(1 for e in self._entries if e.success),
                "total_tokens": sum(e.total_tokens for e in self._entries),
                "prompt_tokens": sum(e.prompt_tokens for e in self._entries),
                "completion_tokens": sum(e.completion_tokens for e in self._entries),
                "total_cost_usd": round(sum(e.estimated_cost_usd for e in self._entries), 6),
                "calls_by_model": _count_by(self._entries, "model"),
                "calls_by_service": _count_by(self._entries, "service"),
            }

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()


_global_tracker: CostTracker | None = None
_tracker_lock = threading.Lock()


def get_global_cost_tracker() -> CostTracker:
    global _global_tracker
    if _global_tracker is None:
        with _tracker_lock:
            if _global_tracker is None:
                _global_tracker = CostTracker()
    return _global_tracker


def _count_by(entries: list[CostEntry], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for e in entries:
        key = getattr(e, field, "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts
