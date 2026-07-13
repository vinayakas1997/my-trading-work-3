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
    slippage_model: Literal["flat", "almgren_chriss"] = "almgren_chriss"
    benchmark_tickers: list[str] | None = None
    allow_short: bool = True
    deviation_threshold: float | None = None
    dry_run: bool = False


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
    features_api_url: str
    deviation_threshold: float


import time as _time
_SIMULATOR_START_TIME = _time.time()


class CustomSimulateRequest(BaseModel):
    strategy_code: str = Field(..., description="Python class definition for the strategy")
    class_name: str = Field(..., description="Name of the strategy class in strategy_code")
    symbols: list[str] = Field(..., min_length=1)
    start_date: str = Field(default="2020-01-01", pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    initial_capital: float | None = None
    transaction_cost_pct: float | None = None
    slippage_pct: float | None = None
    slippage_model: Literal["flat", "almgren_chriss"] = "almgren_chriss"
    benchmark_tickers: list[str] | None = None
    allow_short: bool = True
    deviation_threshold: float | None = None


class CustomSimulateResponse(BaseModel):
    run_id: str
    strategy_name: str
    timestamp: datetime
    metrics: dict[str, float]
    benchmark_metrics: dict[str, dict[str, float]] = Field(default_factory=dict)
    trade_count: int
    equity_points: int


class SimulateDryRunResponse(BaseModel):
    strategy_name: str
    dry_run: bool = True
    message: str = "Dry run — no simulation performed"


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "vinu-simulator"
    strategy_api_healthy: bool = False
    stock_api_healthy: bool = False
    features_api_healthy: bool = False
    uptime_seconds: float = Field(default_factory=lambda: _time.time() - _SIMULATOR_START_TIME)
    total_runs: int = 0
