"""The one definition of free cash, shared by the allocator (portfolio), the capital ledger (live) and the order guard
(agent), so the three can never disagree about how much money is left to spend.

    free cash = real capital - committed (open trades, at cost) - reserve (a share of real capital never allocated)
"""
from __future__ import annotations

from dataclasses import dataclass

from vinu_infra.account_mode import ACCOUNT_MODES


@dataclass(frozen=True)
class CapitalState:
    account_mode: str            # "paper" or "real"
    real_capital: float          # the money the sizes are computed from
    committed: float = 0.0       # money in open trades, at cost
    reserve_fraction: float = 0.4  # share of real_capital never allocated

    def __post_init__(self) -> None:
        if self.account_mode not in ACCOUNT_MODES:
            raise ValueError(f"account_mode must be one of {ACCOUNT_MODES}, got {self.account_mode!r}")
        if not (self.real_capital > 0):
            raise ValueError("real_capital must be positive")
        if self.committed < 0:
            raise ValueError("committed cannot be negative")
        if not (0.0 <= self.reserve_fraction < 1.0):
            raise ValueError("reserve_fraction must be in [0, 1)")

    @property
    def reserve(self) -> float:
        return self.real_capital * self.reserve_fraction

    @property
    def free_cash(self) -> float:
        """real capital, minus what open trades already hold, minus the reserve; never below zero."""
        return max(0.0, self.real_capital - self.committed - self.reserve)

    def as_dict(self) -> dict:
        return {
            "account_mode": self.account_mode, "real_capital": self.real_capital, "committed": round(self.committed, 4),
            "reserve_fraction": self.reserve_fraction, "reserve": round(self.reserve, 4), "free_cash": round(self.free_cash, 4),
        }
