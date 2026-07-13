from __future__ import annotations

import math
from abc import ABC, abstractmethod

import numpy as np


class CostModel(ABC):
    #: Annual stock-loan/borrow rate charged on short notional, applied once per day.
    #: A generic easy-to-borrow assumption — not calibrated per symbol, but far closer
    #: to reality than the implicit zero the engine used to charge on shorts.
    borrow_cost_annual: float = 0.0075

    @abstractmethod
    def buy_cost(
        self,
        price: float,
        shares: float,
        volume: float | None = None,
        volatility: float | None = None,
    ) -> float:
        ...

    @abstractmethod
    def sell_proceeds(
        self,
        price: float,
        shares: float,
        volume: float | None = None,
        volatility: float | None = None,
    ) -> float:
        ...

    def daily_borrow_cost(self, short_notional: float) -> float:
        if short_notional <= 0:
            return 0.0
        return short_notional * self.borrow_cost_annual / 252.0


class FlatCostModel(CostModel):
    def __init__(
        self,
        cost_pct: float = 0.001,
        slippage_pct: float = 0.0005,
        borrow_cost_annual: float = 0.0075,
    ):
        self.cost_pct = cost_pct
        self.slippage_pct = slippage_pct
        self.borrow_cost_annual = borrow_cost_annual

    def buy_cost(
        self,
        price: float,
        shares: float,
        volume: float | None = None,
        volatility: float | None = None,
    ) -> float:
        effective_price = price * (1 + self.slippage_pct)
        return effective_price * shares * (1 + self.cost_pct)

    def sell_proceeds(
        self,
        price: float,
        shares: float,
        volume: float | None = None,
        volatility: float | None = None,
    ) -> float:
        effective_price = price * (1 - self.slippage_pct)
        return max(0.0, effective_price * shares * (1 - self.cost_pct))


class AlmgrenChrissCostModel(CostModel):
    def __init__(
        self,
        fixed_cost_pct: float = 0.001,
        market_impact_coeff: float = 0.01,
        market_impact_exp: float = 0.5,
        slippage_pct: float = 0.0005,
        borrow_cost_annual: float = 0.0075,
        # Missing/zero volume means we have no basis for estimating impact — treat that
        # as a liquidity-risk penalty, not as evidence the trade was costless. Expressed
        # as a fraction of notional (0.005 = 50bps), applied instead of a computed impact.
        missing_volume_impact_pct: float = 0.005,
    ):
        self.fixed_cost_pct = fixed_cost_pct
        self.market_impact_coeff = market_impact_coeff
        self.market_impact_exp = market_impact_exp
        self.slippage_pct = slippage_pct
        self.borrow_cost_annual = borrow_cost_annual
        self.missing_volume_impact_pct = missing_volume_impact_pct

    def _participation_rate(self, shares: float, volume: float | None) -> float:
        if volume is None or volume <= 0 or shares <= 0:
            return 0.0
        return min(shares / volume, 1.0)

    def _market_impact(self, price: float, shares: float, volume: float | None) -> float:
        if shares <= 0:
            return 0.0
        if volume is None or volume <= 0:
            # No liquidity data to estimate impact from — assume worst-case thin
            # liquidity rather than silently charging zero impact.
            return price * shares * self.missing_volume_impact_pct
        rate = self._participation_rate(shares, volume)
        if rate <= 0:
            return 0.0
        return (
            price
            * shares
            * self.market_impact_coeff
            * (rate**self.market_impact_exp)
        )

    def buy_cost(
        self,
        price: float,
        shares: float,
        volume: float | None = None,
        volatility: float | None = None,
    ) -> float:
        effective_price = price * (1 + self.slippage_pct)
        fixed = effective_price * shares * self.fixed_cost_pct
        impact = self._market_impact(price, shares, volume)
        return effective_price * shares + fixed + impact

    def sell_proceeds(
        self,
        price: float,
        shares: float,
        volume: float | None = None,
        volatility: float | None = None,
    ) -> float:
        effective_price = price * (1 - self.slippage_pct)
        fixed = effective_price * shares * self.fixed_cost_pct
        impact = self._market_impact(price, shares, volume)
        return max(0.0, effective_price * shares - fixed - impact)
