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
        as_of: int | None = None,
    ) -> dict[str, Any]:
        """`as_of` (item #22 finding #3, system-wide-audit-and-design/
        02-open-questions-strategy-and-simulation.md): forwarded to
        vinu-tools' `/{symbol}` route, which forwards it again to
        vinu-stock-price's own `clamp_to_as_of()` enforcement -- without
        it, this call always reflects wall-clock "now," not the strategy
        run's own decision-time instant."""
        params: dict[str, Any] = {}
        if indicators:
            params["indicators"] = ",".join(indicators)
        if from_ts:
            params["from"] = str(from_ts)
        if to_ts:
            params["to"] = str(to_ts)
        if as_of is not None:
            params["as_of"] = str(as_of)
        return self._get(f"/features/{symbol}", params=params)
