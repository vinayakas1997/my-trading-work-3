from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class DataResponse(BaseModel, Generic[T]):
    count: int = 0
    data: list[T] | dict[str, Any] | None = None


class HealthResponse(BaseModel):
    ok: bool = True


class StoryResponse(BaseModel):
    ticker: str
    data: dict[str, Any]


class SettingsResponse(BaseModel):
    data_root: str = ""
    news_api_url: str = ""
    stock_api_url: str = ""
    host: str = ""
    port: int = 8083
    cache_maxsize: int = 256
    cache_ttl_sec: int = 300
    compute_poll_interval_sec: int = 3600


class AngleInfo(BaseModel):
    name: str
    title: str
    purpose: str = ""


class AnalysisResult(BaseModel):
    symbol: str
    angle_results: dict[str, Any]
