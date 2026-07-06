from __future__ import annotations

from typing import Any

from vinu_strategy.clients.base import BaseClient


class FeaturesClient(BaseClient):
    def get_features(
        self,
        symbol: str,
        indicators: list[str] | None = None,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if indicators:
            params["indicators"] = ",".join(indicators)
        if from_ts:
            params["from"] = str(from_ts)
        if to_ts:
            params["to"] = str(to_ts)
        return self._get(f"/features/{symbol}", params=params)
