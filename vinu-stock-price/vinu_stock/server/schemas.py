"""Pydantic schemas for HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DataResponse(BaseModel):
    count: int
    data: list[dict[str, Any]]


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
