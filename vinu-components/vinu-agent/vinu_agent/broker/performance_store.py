from __future__ import annotations

from typing import Any


class PaperPerformanceStore:
    """In-memory store for per-artifact paper-trading daily returns.

    This is a lightweight, non-persistent store for v1. Each entry maps an
    artifact_id to its list of daily returns from paper trading. The data is
    accumulated by vinu-live's cycle and read by the broker performance endpoint
    for ShadowEvaluator.
    """

    def __init__(self) -> None:
        self._data: dict[str, list[float]] = {}

    def record_daily_return(self, artifact_id: str, daily_return: float) -> None:
        if artifact_id not in self._data:
            self._data[artifact_id] = []
        self._data[artifact_id].append(daily_return)

    def record_daily_returns(self, artifact_id: str, returns: list[float]) -> None:
        self._data[artifact_id] = list(returns)

    def get_daily_returns(self, artifact_id: str) -> list[float]:
        return self._data.get(artifact_id, [])

    def get_all(self) -> dict[str, list[float]]:
        return dict(self._data)

    def clear(self) -> None:
        self._data.clear()


_store = PaperPerformanceStore()


def get_store() -> PaperPerformanceStore:
    return _store
