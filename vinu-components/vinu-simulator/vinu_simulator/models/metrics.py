from __future__ import annotations

from dataclasses import dataclass
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

    @classmethod
    def from_dict(cls, d: dict[str, float]) -> MetricBundle:
        return cls(**{k: d.get(k, 0.0) for k in cls.__dataclass_fields__})

    def to_dict(self) -> dict[str, float]:
        return {
            "total_return": self.total_return,
            "cagr": self.cagr,
            "annual_volatility": self.annual_volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_drawdown": self.max_drawdown,
            "calmar_ratio": self.calmar_ratio,
            "win_rate": self.win_rate,
            "skewness": self.skewness,
            "kurtosis": self.kurtosis,
        }
