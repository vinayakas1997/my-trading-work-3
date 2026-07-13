from __future__ import annotations

from datetime import datetime
from typing import Any

from typing import Literal

from pydantic import BaseModel, Field


class SimulateRequest(BaseModel):
    strategy_name: str
    start_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    initial_capital: float | None = None
    transaction_cost_pct: float | None = None
    slippage_pct: float | None = None
    slippage_model: Literal["flat", "almgren_chriss"] = "flat"
    benchmark_tickers: list[str] | None = None
    allow_short: bool = True
    deviation_threshold: float | None = None


class SimulateResponse(BaseModel):
    run_id: str
    strategy_name: str
    timestamp: datetime
    metrics: dict[str, float]
    benchmark_metrics: dict[str, dict[str, float]] = Field(default_factory=dict)
    trade_count: int
    equity_points: int


class MetricRow(BaseModel):
    metric: str
    strategy: float
    benchmarks: dict[str, float] = Field(default_factory=dict)


class RunSummary(BaseModel):
    run_id: str
    strategy_name: str
    timestamp: str
    metrics: dict[str, float]
    benchmark_metrics: dict[str, dict[str, float]]
    trade_count: int
    equity_points: int


class SettingsResponse(BaseModel):
    initial_capital: float
    transaction_cost_pct: float
    slippage_pct: float
    benchmark_tickers: list[str]
    allow_short: bool
    strategy_api_url: str
    stock_api_url: str
    deviation_threshold: float


class HealthResponse(BaseModel):
    ok: bool = True
