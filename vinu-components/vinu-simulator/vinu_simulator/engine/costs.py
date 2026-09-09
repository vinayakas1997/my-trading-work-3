from __future__ import annotations

import math
import os as _os
from abc import ABC, abstractmethod

import numpy as np

# Fill parity (16 gap1): spread + queue + latency knobs. Env only, no rebuild to flip.
# Defaults 0 keep old behavior. Set SPREAD_BPS=5, QUEUE_PCT=0.1 for honest 15min.
DEFAULT_SPREAD_BPS = float(_os.environ.get("VINU_SIM_SPREAD_BPS", "0"))
DEFAULT_QUEUE_PCT = float(_os.environ.get("VINU_SIM_QUEUE_PCT", "0"))


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
        spread_bps: float = DEFAULT_SPREAD_BPS,
        queue_pct: float = DEFAULT_QUEUE_PCT,
    ):
        self.cost_pct = cost_pct
        self.slippage_pct = slippage_pct
        self.borrow_cost_annual = borrow_cost_annual
        self.spread_bps = spread_bps
        self.queue_pct = queue_pct

    def _spread_half(self, price: float) -> float:
        return price * (self.spread_bps / 10000.0) / 2.0

    def buy_cost(
        self,
        price: float,
        shares: float,
        volume: float | None = None,
        volatility: float | None = None,
    ) -> float:
        effective_price = price * (1 + self.slippage_pct) + self._spread_half(price)
        # Queue: pay extra queue_pct of notional when participation high (thin).
        base = effective_price * shares * (1 + self.cost_pct)
        if volume and volume > 0 and self.queue_pct > 0:
            base += price * shares * self.queue_pct * min(shares / volume, 1.0)
        return base

    def sell_proceeds(
        self,
        price: float,
        shares: float,
        volume: float | None = None,
        volatility: float | None = None,
    ) -> float:
        effective_price = price * (1 - self.slippage_pct) - self._spread_half(price)
        base = max(0.0, effective_price * shares * (1 - self.cost_pct))
        if volume and volume > 0 and self.queue_pct > 0:
            base = max(0.0, base - price * shares * self.queue_pct * min(shares / volume, 1.0))
        return base


class AlmgrenChrissCostModel(CostModel):
    def __init__(
        self,
        fixed_cost_pct: float = 0.001,
        market_impact_coeff: float = 0.01,
        market_impact_exp: float = 0.5,
        slippage_pct: float = 0.0005,
        borrow_cost_annual: float = 0.0075,
        spread_bps: float = DEFAULT_SPREAD_BPS,
        queue_pct: float = DEFAULT_QUEUE_PCT,
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
        self.spread_bps = spread_bps
        self.queue_pct = queue_pct
        self.missing_volume_impact_pct = missing_volume_impact_pct

    def _spread_half(self, price: float) -> float:
        return price * (self.spread_bps / 10000.0) / 2.0

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
        effective_price = price * (1 + self.slippage_pct) + self._spread_half(price)
        fixed = effective_price * shares * self.fixed_cost_pct
        impact = self._market_impact(price, shares, volume)
        queue = price * shares * self.queue_pct * self._participation_rate(shares, volume) if self.queue_pct > 0 else 0.0
        return effective_price * shares + fixed + impact + queue

    def sell_proceeds(
        self,
        price: float,
        shares: float,
        volume: float | None = None,
        volatility: float | None = None,
    ) -> float:
        effective_price = price * (1 - self.slippage_pct) - self._spread_half(price)
        fixed = effective_price * shares * self.fixed_cost_pct
        impact = self._market_impact(price, shares, volume)
        queue = price * shares * self.queue_pct * self._participation_rate(shares, volume) if self.queue_pct > 0 else 0.0
        return max(0.0, effective_price * shares - fixed - impact - queue)
