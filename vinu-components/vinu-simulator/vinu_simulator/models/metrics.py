from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricBundle:
    total_return: float = 0.0
    cagr: float = 0.0
    annual_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0

    var_95: float = 0.0
    var_99: float = 0.0
    cvar_95: float = 0.0
    tail_ratio: float = 0.0
    max_dd_duration_days: int = 0
    avg_drawdown: float = 0.0
    recovery_time_days: int = 0
    profit_factor: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    win_loss_ratio: float = 0.0
    hit_rate: float = 0.0
    annual_turnover: float = 0.0
    sharpe_standard_error: float = 0.0
    sharpe_p_value: float = 1.0
    sharpe_ci_95_low: float = 0.0
    sharpe_ci_95_high: float = 0.0

    beta: float = 0.0
    alpha: float = 0.0
    tracking_error: float = 0.0
    information_ratio: float = 0.0
    market_correlation: float = 0.0
    up_capture: float = 0.0
    down_capture: float = 0.0

    @classmethod
    def from_dict(cls, d: dict[str, float]) -> MetricBundle:
        return cls(**{k: d.get(k, 0.0) for k in cls.__dataclass_fields__})

    def to_dict(self) -> dict[str, float]:
        result = {}
        for k in self.__dataclass_fields__:
            v = getattr(self, k)
            if isinstance(v, (int, float)):
                result[k] = float(v)
            else:
                result[k] = v
        return result
