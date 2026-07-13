"""Ticker news provider interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class NotConfiguredError(RuntimeError):
    pass


@dataclass(frozen=True)
class TickerNewsProviderConfig:
    id: str
    enabled: bool
    priority: int


@runtime_checkable
class TickerNewsProvider(Protocol):
    provider_id: str

    def is_configured(self) -> bool: ...

    def fetch_ticker_news(
        self,
        ticker: str,
        from_ts: int,
        to_ts: int,
    ) -> list[dict]: ...
