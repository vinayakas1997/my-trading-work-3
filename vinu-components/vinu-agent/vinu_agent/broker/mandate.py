"""Trading mandate — user-committed constraints on trading activity."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from vinu_infra.runtime_settings import RuntimeSettings

logger = logging.getLogger(__name__)

DEFAULT_MANDATE_PATH = Path.home() / ".vinu" / "mandate.yaml"

# Live-editable overlay for the numeric risk limits below, via
# POST /agent/admin/settings -- no restart, no mandate.yaml edit needed.
# OrderGuard constructs a fresh TradingMandate on every order (see
# order_guard.py's docstring), so an override set here takes effect on the
# very next order attempt. Deliberately overlays TradingMandate.load()'s
# result rather than replacing mandate.yaml on disk: a restart always goes
# back to whatever mandate.yaml actually says, so a live loosening can
# never silently survive a redeploy. allowed/blocked_tickers,
# require_active_artifact, require_market_open, require_confirmation,
# allow_short, allow_margin, and the correlation/concentration caps are
# NOT here on purpose -- those are pass/fail policy switches, not tuning
# knobs, and belong in mandate.yaml where changing them is a deliberate,
# reviewable edit.
SETTINGS = RuntimeSettings()
SETTINGS.register(
    "max_position_pct", default=0.25, minimum=0.0, maximum=1.0,
    description="Max single position size as a fraction of equity.",
)
SETTINGS.register(
    "max_order_value", default=50000.0, minimum=0.0,
    description="Max notional value of a single order.",
)
SETTINGS.register(
    "max_daily_orders", default=10, caster=int, minimum=0,
    description="Max orders per symbol per day.",
)
SETTINGS.register(
    "max_daily_trade_volume", default=200000.0, minimum=0.0,
    description="Max traded notional per symbol per day.",
)
SETTINGS.register(
    "max_daily_orders_portfolio", default=0, caster=int, minimum=0,
    description="Max orders per day across the whole portfolio (0 = no cap).",
)
SETTINGS.register(
    "max_capital_utilization_pct", default=1.0, minimum=0.0, maximum=1.0,
    description="Max fraction of equity that may be deployed across all open positions.",
)


@dataclass
class TradingMandate:
    allowed_tickers: set[str] = field(default_factory=lambda: {"*"})
    blocked_tickers: set[str] = field(default_factory=set)
    max_position_pct: float = 0.25
    max_order_value: float = 50000.0
    max_daily_orders: int = 10
    max_daily_trade_volume: float = 200000.0
    # Stage 2 (how-to-make-it-live.md #8): max_daily_orders/max_daily_trade_volume
    # above are both PER-SYMBOL -- 10/symbol x 20 traded symbols is 200 orders/day
    # with nothing capping the total. 0 here (the dataclass fallback used only
    # when a mandate.yaml is absent or omits the key) = no portfolio-wide cap;
    # the actual deployed value is set in vinu-agent/entrypoint.sh's seeded
    # mandate.yaml (currently 50, sized for a ~3-9 symbol universe). reduce_only
    # orders are exempt so this never blocks de-risking.
    max_daily_orders_portfolio: int = 0
    # Cap on total capital deployed across ALL open positions combined, as a
    # fraction of account equity — distinct from max_position_pct, which only
    # caps a single order/position. e.g. 0.60 means at most 60% of equity may
    # ever be in open positions at once, leaving 40% as an untouched buffer.
    # 1.0 (default) means no restriction.
    max_capital_utilization_pct: float = 1.0
    # When True, an order is only allowed if the symbol has a strategy artifact
    # in vinu-research with status ACTIVE (i.e. it cleared the promotion gate —
    # deflated Sharpe, holdout, stress test). False disables the check entirely,
    # for deliberate manual/discretionary trades outside the research pipeline.
    require_active_artifact: bool = True
    # Reject orders while the market is closed. Alpaca will happily queue
    # many order types (e.g. "opg") for next open, so this is a deliberate
    # safety default, not a hard technical requirement — set False for
    # strategies that intentionally queue orders outside market hours.
    require_market_open: bool = True
    # Portfolio-level checks, independent of max_position_pct (which only
    # reasons about this one order). Re-checked against vinu-portfolio's
    # current target weights and correlation matrix at order time, so target
    # weights computed upstream can't silently drift from what's actually
    # enforced when an order fires. 1.0 (default) = no restriction.
    max_symbol_concentration_pct: float = 1.0
    max_pairwise_correlation: float = 1.0
    require_confirmation: bool = True
    allow_short: bool = False
    allow_margin: bool = False

    @classmethod
    def load(cls, path: Path | None = None) -> TradingMandate:
        path = path or DEFAULT_MANDATE_PATH
        if not path.exists():
            logger.info("No mandate at %s, using defaults", path)
            return cls(**SETTINGS.overrides())
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            allowed = raw.get("allowed_tickers", ["*"])
            blocked = raw.get("blocked_tickers", [])
            kwargs: dict[str, Any] = dict(
                allowed_tickers=set(allowed) if isinstance(allowed, list) else {"*"},
                blocked_tickers=set(blocked) if isinstance(blocked, list) else set(),
                max_position_pct=float(raw.get("max_position_pct", 0.25)),
                max_order_value=float(raw.get("max_order_value", 50000.0)),
                max_daily_orders=int(raw.get("max_daily_orders", 10)),
                max_daily_trade_volume=float(raw.get("max_daily_trade_volume", 200000.0)),
                max_daily_orders_portfolio=int(raw.get("max_daily_orders_portfolio", 0)),
                max_capital_utilization_pct=float(raw.get("max_capital_utilization_pct", 1.0)),
                require_active_artifact=bool(raw.get("require_active_artifact", True)),
                require_market_open=bool(raw.get("require_market_open", True)),
                max_symbol_concentration_pct=float(raw.get("max_symbol_concentration_pct", 1.0)),
                max_pairwise_correlation=float(raw.get("max_pairwise_correlation", 1.0)),
                require_confirmation=bool(raw.get("require_confirmation", True)),
                allow_short=bool(raw.get("allow_short", False)),
                allow_margin=bool(raw.get("allow_margin", False)),
            )
            # Live admin overrides (POST /agent/admin/settings) win over
            # mandate.yaml -- an operator tightening/loosening a numeric
            # risk limit at runtime is deliberately allowed to override
            # the file without editing it; a restart drops back to the
            # file's own value (see SETTINGS' module docstring above).
            kwargs.update(SETTINGS.overrides())
            return cls(**kwargs)
        except Exception as exc:
            logger.warning("Failed to load mandate from %s: %s — using defaults", path, exc)
            return cls(**SETTINGS.overrides())

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_tickers": sorted(self.allowed_tickers),
            "blocked_tickers": sorted(self.blocked_tickers),
            "max_position_pct": self.max_position_pct,
            "max_order_value": self.max_order_value,
            "max_daily_orders": self.max_daily_orders,
            "max_daily_trade_volume": self.max_daily_trade_volume,
            "max_daily_orders_portfolio": self.max_daily_orders_portfolio,
            "max_capital_utilization_pct": self.max_capital_utilization_pct,
            "require_active_artifact": self.require_active_artifact,
            "require_market_open": self.require_market_open,
            "max_symbol_concentration_pct": self.max_symbol_concentration_pct,
            "max_pairwise_correlation": self.max_pairwise_correlation,
            "require_confirmation": self.require_confirmation,
            "allow_short": self.allow_short,
            "allow_margin": self.allow_margin,
        }
