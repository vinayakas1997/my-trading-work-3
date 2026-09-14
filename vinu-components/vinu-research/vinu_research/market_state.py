"""Unified market-state container (high-expectations spec #2/#15: a single
'market state representation' instead of data passed as loose parallel dict
arguments).

MarketState is the *input* side of a trade decision -- it aggregates
everything trade_plan_authoring.author_trade_plan() and vinu-agent's
trade_plan_tool._build_structured_plan() already fetch (angles, features,
liquidity, news, risk_state, validation, active strategies), plus the two new
inputs later phases add (options, market_regime_stats). TradePlan (in
models.py) remains the *output* side -- this module intentionally does not
duplicate or replace anything there.

This is additive: existing call sites keep passing their individual dict
arguments unchanged. A MarketState is just a convenient way to construct and
carry those same dicts together going forward.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MarketState:
    symbol: str
    as_of: str = ""
    # trend_lifecycle / shock_personality / shock_clustering / regime_analysis
    # angle rows, same shape as trade_plan_tool.py's `angles` dict arg.
    angles: dict[str, list[dict]] = field(default_factory=dict)
    # vinu-tools factor features, same shape as the `features` dict arg.
    features: dict[str, Any] = field(default_factory=dict)
    liquidity: dict[str, Any] = field(default_factory=dict)
    news: dict[str, Any] = field(default_factory=dict)
    # Phase 5 -- options IV/skew snapshot from ResearchTools.get_options_snapshot.
    options: dict[str, Any] = field(default_factory=dict)
    # trade_plan_authoring.fetch_risk_state() output.
    risk_state: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)
    active_strategies: list[dict] = field(default_factory=list)
    # Phase 4 -- get_market_regime_stats() output; {} when unavailable.
    market_regime_stats: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_parts(cls, symbol: str, **parts: Any) -> "MarketState":
        """Construct from the same keyword shape trade_plan_tool.py's
        _build_structured_plan/_render_plan already use (angles, features,
        liquidity, news, validation, ...) -- unknown keys are ignored so this
        stays tolerant of callers passing a superset."""
        known = {f for f in cls.__dataclass_fields__ if f != "symbol"}
        return cls(symbol=symbol, **{k: v for k, v in parts.items() if k in known})

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "as_of": self.as_of,
            "angles": self.angles,
            "features": self.features,
            "liquidity": self.liquidity,
            "news": self.news,
            "options": self.options,
            "risk_state": self.risk_state,
            "validation": self.validation,
            "active_strategies": self.active_strategies,
            "market_regime_stats": self.market_regime_stats,
        }
