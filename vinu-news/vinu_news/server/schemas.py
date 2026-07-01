"""Pydantic schemas for HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DataResponse(BaseModel):
    count: int
    data: list[dict[str, Any]]


class SettingsResponse(BaseModel):
    mode: str
    poll_interval_sec: int
    llm_analysis_mode: str
    llm_analysis_concurrency: int


class SettingsPatchRequest(BaseModel):
    mode: str | None = None
    poll_interval_sec: int | None = Field(default=None, ge=60)
    llm_analysis_mode: str | None = None
    llm_analysis_concurrency: int | None = Field(default=None, ge=1, le=20)


class WatchlistResponse(BaseModel):
    tickers: list[str]


class WatchlistAddRequest(BaseModel):
    tickers: list[str] = Field(min_length=1)


class AnalyzeRequest(BaseModel):
    url_or_id: str = Field(min_length=1)


class AnalyzeResponse(BaseModel):
    url: str
    cached: bool
    analysis: dict[str, Any]


class ThreadDetailResponse(BaseModel):
    thread: dict[str, Any]
    articles: list[dict[str, Any]]


class IngestTriggerResponse(BaseModel):
    ok: bool
    summary: dict[str, Any]


class ToggleEnabledRequest(BaseModel):
    enabled: bool
