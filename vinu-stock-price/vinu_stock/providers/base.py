"""Price provider interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from vinu_stock.storage.models import BarRecord


@dataclass(frozen=True)
class FetchBarsResult:
    success: bool
    bars: list[BarRecord]
    error: str = ""


@dataclass(frozen=True)
class EarliestResult:
    success: bool
    earliest_ts: int | None  # UTC epoch seconds
    error: str = ""


@runtime_checkable
class PriceProvider(Protocol):
    provider_id: str

    def is_configured(self) -> bool: ...

    def fetch_bars(
        self,
        symbol: str,
        start_ts: int,
        end_ts: int,
        *,
        interval: str = "1m",
    ) -> FetchBarsResult: ...

    def earliest_available(self, symbol: str) -> EarliestResult: ...
