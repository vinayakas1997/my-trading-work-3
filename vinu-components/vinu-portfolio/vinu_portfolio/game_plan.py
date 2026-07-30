from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class SymbolPlan:
    ticker: str
    target_weight: float = 0.0
    base_weight: float = 0.0
    regime_multiplier: float = 1.0
    outcome_multiplier: float = 1.0
    outcome_source: str = "not_tracked"
    position_size: float | None = None
    direction: str | None = None
    forecast: dict[str, Any] | None = None
    invalidation_conditions: list[dict[str, Any]] | None = None
    p_failure: float | None = None
    shock_correlation: dict[str, Any] | None = None
    plan_status: str = "no_plan"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DailyGamePlan:
    date: str = ""
    readiness_score: float = 0.0
    readiness_flags: dict[str, Any] = field(default_factory=dict)
    n_symbols: int = 0
    symbols: list[dict[str, Any]] = field(default_factory=list)
    portfolio: dict[str, Any] = field(default_factory=dict)
    regime: dict[str, Any] | None = None
    shock_correlation: dict[str, Any] | None = None
    account_equity: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
