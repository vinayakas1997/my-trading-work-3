from __future__ import annotations

import math
import os as _os
from abc import ABC, abstractmethod

import numpy as np

# Fill parity (16 gap1): spread + queue + latency knobs. Env only, no rebuild to flip.
# Defaults 0 keep old behavior. Set SPREAD_BPS=5, QUEUE_PCT=0.1 for honest 15min.
DEFAULT_SPREAD_BPS = float(_os.environ.get("VINU_SIM_SPREAD_BPS", "0"))
DEFAULT_QUEUE_PCT = float(_os.environ.get("VINU_SIM_QUEUE_PCT", "0"))

# Outside the regular session spreads are wider and books thinner, so slippage and spread cost more. The multipliers scale the
# slippage and the spread part of a trade's cost, not the commission. Daily bars carry no time of day and are never scaled.
# BASE FROM PUBLISHED FIGURES (2026-10-08; Proper-Project-Implementation/03-guards-configs-and-settings/session-cost-evidence.md):
#   after-hours 7  : quoted spread 58.1 bps against 8.4 bps in regular trading (arXiv 2601.08962); median 4 to 10 times regular elsewhere
#   pre-market  5  : no direct figure found; the middle of the same 4 to 10 times band
#   overnight   3  : about 3 times regular for stocks that trade consistently on Blue Ocean; 10 to 20 times for thin ones (BMLL, Eaton)
# Our own quote recorder (/stock/spread-stats) will refine these, but its feed is IEX-only and reads too wide in absolute terms.
DEFAULT_SESSION_COST_MULT = "premarket=5,regular=1,afterhours=7,overnight=3"


def parse_session_multipliers(spec: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for part in (spec or "").split(","):
        name, _, value = part.partition("=")
        if name.strip() and value.strip():
            out[name.strip().lower()] = max(1.0, float(value))
    return out


SESSION_COST_MULT = parse_session_multipliers(_os.environ.get("VINU_SIM_SESSION_COST_MULT", DEFAULT_SESSION_COST_MULT))


def session_cost_multiplier(bar_time, multipliers: dict[str, float] | None = None) -> float:
    """The cost multiplier for a bar opened at `bar_time` (a pandas Timestamp, naive = UTC). 1.0 for the regular session."""
    from vinu_infra.sessions import session_of

    ts = bar_time.timestamp() if getattr(bar_time, "tzinfo", None) is not None else bar_time.tz_localize("UTC").timestamp()
    return (multipliers if multipliers is not None else SESSION_COST_MULT).get(session_of(ts), 1.0)


class CostModel(ABC):
    #: Scales slippage and spread for the bar being traded (set by the engine per bar; 1.0 = regular session).
    session_multiplier: float = 1.0

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
        return price * (self.spread_bps * self.session_multiplier / 10000.0) / 2.0

    def buy_cost(
        self,
        price: float,
        shares: float,
        volume: float | None = None,
        volatility: float | None = None,
    ) -> float:
        effective_price = price * (1 + self.slippage_pct * self.session_multiplier) + self._spread_half(price)
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
        effective_price = price * (1 - self.slippage_pct * self.session_multiplier) - self._spread_half(price)
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
        return price * (self.spread_bps * self.session_multiplier / 10000.0) / 2.0

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
        effective_price = price * (1 + self.slippage_pct * self.session_multiplier) + self._spread_half(price)
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
        effective_price = price * (1 - self.slippage_pct * self.session_multiplier) - self._spread_half(price)
        fixed = effective_price * shares * self.fixed_cost_pct
        impact = self._market_impact(price, shares, volume)
        queue = price * shares * self.queue_pct * self._participation_rate(shares, volume) if self.queue_pct > 0 else 0.0
        return max(0.0, effective_price * shares - fixed - impact - queue)
