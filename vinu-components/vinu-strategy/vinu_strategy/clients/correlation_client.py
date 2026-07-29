from __future__ import annotations

from typing import Any

from vinu_strategy.clients.base import BaseClient


class CorrelationClient(BaseClient):
    def get_impact(self, symbol: str, from_ts: int | None = None, to_ts: int | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if from_ts:
            params["from"] = str(from_ts)
        if to_ts:
            params["to"] = str(to_ts)
        return self._get(f"/impact/{symbol}", params=params)

    def get_correlation(self, symbol: str, from_ts: int | None = None, to_ts: int | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if from_ts:
            params["from"] = str(from_ts)
        if to_ts:
            params["to"] = str(to_ts)
        return self._get(f"/correlation/{symbol}", params=params)

    def get_drawdown(self, symbol: str, from_ts: int | None = None, to_ts: int | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if from_ts:
            params["from"] = str(from_ts)
        if to_ts:
            params["to"] = str(to_ts)
        return self._get(f"/drawdown/{symbol}", params=params)

    def get_angle(self, symbol: str, angle_name: str) -> dict[str, Any]:
        return self._get(f"/angle/{angle_name}/{symbol}")
