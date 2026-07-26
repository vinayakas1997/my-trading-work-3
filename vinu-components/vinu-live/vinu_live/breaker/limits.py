from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BreakerLimits:
    max_daily_loss_pct: float = 0.05
    max_var_95_pct: float = 0.03
    max_greeks_delta: float = 1000.0
    max_greeks_gamma: float = 500.0
    max_greeks_vega: float = 500.0
    max_position_count: int = 20
    max_cluster_exposure_pct: float = 0.30
    max_leverage: float = 2.0


DEFAULT_LIMITS = BreakerLimits()


@dataclass
class BreakerState:
    halted: bool = False
    halted_at: str = ""
    halted_reason: str = ""
    limits: BreakerLimits = field(default_factory=lambda: DEFAULT_LIMITS)

    def reset(self) -> None:
        self.halted = False
        self.halted_at = ""
        self.halted_reason = ""
