"""Pydantic schemas for HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DataResponse(BaseModel):
    count: int
    data: list[dict[str, Any]]


class CandlesResponse(DataResponse):
    # True when more bars exist in the requested window than `limit` allowed. `next_from` is where to resume (forward
    # pagination: the first bar_ts after the last bar returned). Without this a long intraday window was silently cut
    # to its oldest `limit` bars and callers backtested on a fraction of what they asked for.
    truncated: bool = False
    next_from: int | None = None


class CandlesBatchRequest(BaseModel):
    symbols: list[str] = Field(min_length=1)
    interval: str = "1m"
    from_ts: int | None = Field(default=None, alias="from")
    to_ts: int | None = Field(default=None, alias="to")
    days: int | None = Field(default=None, ge=1, le=3650)
    provider: str | None = None
    limit: int = Field(default=5000, ge=1, le=50000)
    indicators: list[str] | None = None
    adjusted: bool = True
    session: str | None = None

    model_config = {"populate_by_name": True}


class CandlesBatchResponse(BaseModel):
    results: dict[str, DataResponse]


class SettingsResponse(BaseModel):
    poll_interval_sec: int
    default_provider: str
    data_root: str


class SettingsPatchRequest(BaseModel):
    poll_interval_sec: int | None = Field(default=None, ge=10)
    default_provider: str | None = None
    data_root: str | None = None


class WatchlistResponse(BaseModel):
    tickers: list[str]


class WatchlistAddRequest(BaseModel):
    tickers: list[str] = Field(min_length=1)


class TriggerResponse(BaseModel):
    ok: bool
    summary: dict[str, Any]
