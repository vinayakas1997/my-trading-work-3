"""Pydantic schemas for HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FeatureSpecIn(BaseModel):
    kind: str
    params: dict[str, int | float | str] = Field(default_factory=dict)


class FeatureRequestIn(BaseModel):
    title: str
    symbols: list[str]
    from_ts: int | None = None
    to_ts: int | None = None
    days: int | None = Field(default=None, ge=1, le=3650)
    interval: str = "1d"
    preset: str | None = None
    features: list[str | FeatureSpecIn] = Field(default_factory=list)
    conditions: str | None = None
    ml_model: str | None = None
    ml_label: str | None = None
    run_immediately: bool = False


class FeatureRequestOut(BaseModel):
    id: int | None
    title: str
    slug: str
    symbols: list[str]
    from_ts: int
    to_ts: int
    interval: str
    preset: str | None
    features: list[str]
    conditions: str | None
    status: str
    file_path: str | None
    error_message: str | None
    request_hash: str
    created_at: str
    updated_at: str
    row_count: int = 0
    ml_model: str | None = None
    ml_label: str | None = None

    @classmethod
    def from_model(cls, req: Any) -> FeatureRequestOut:
        return cls(**req.to_dict())


class FeatureRequestListResponse(BaseModel):
    count: int
    data: list[FeatureRequestOut]


class PresetOut(BaseModel):
    name: str
    features: list[str]
    description: str = ""


class PresetListResponse(BaseModel):
    count: int
    data: list[PresetOut]


class IndicatorMetaOut(BaseModel):
    kind: str
    description: str
    params: dict[str, dict[str, int | float | str | None]]
    output_columns: list[str]
    examples: list[str]
    legacy_aliases: dict[str, dict[str, int | float]]
    help_text: str | None = None


class FeatureCatalogResponse(BaseModel):
    count: int
    data: list[IndicatorMetaOut]


class HealthResponse(BaseModel):
    ok: bool = True
    info: dict[str, Any]
