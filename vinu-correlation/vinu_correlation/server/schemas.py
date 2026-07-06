from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class DataResponse(BaseModel, Generic[T]):
    count: int
    data: list[T] | dict[str, Any]


class HealthResponse(BaseModel):
    ok: bool = True


class SettingsResponse(BaseModel):
    data_root: str
    news_api_url: str
    stock_api_url: str
    port: int
    impact_high_threshold: float
    impact_medium_threshold: float
    drawdown_min_pct: float
    drawdown_lookback_hours: int
    baseline_window_days: int
    market_hours_only: bool
    session_break_on_close: bool
    cache_ttl_sec: int
    compute_poll_interval_sec: int
    compact_threshold: int
