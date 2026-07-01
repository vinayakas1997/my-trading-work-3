"""Bar data models (Fincept BrokerCandle-aligned)."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class BarRecord:
    symbol: str
    provider: str
    bar_ts: int  # UTC epoch seconds, bar open
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: float = 0.0
    trades: int = 0
    adj_factor: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BarRecord:
        return cls(
            symbol=str(data["symbol"]),
            provider=str(data["provider"]),
            bar_ts=int(data["bar_ts"]),
            open=float(data["open"]),
            high=float(data["high"]),
            low=float(data["low"]),
            close=float(data["close"]),
            volume=float(data["volume"]),
            vwap=float(data.get("vwap", 0.0)),
            trades=int(data.get("trades", 0)),
            adj_factor=float(data.get("adj_factor", 1.0) or 1.0),
        )
