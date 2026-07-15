"""Trading mandate — user-committed constraints on trading activity."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

DEFAULT_MANDATE_PATH = Path.home() / ".vinu" / "mandate.yaml"


@dataclass
class TradingMandate:
    allowed_tickers: set[str] = field(default_factory=lambda: {"*"})
    blocked_tickers: set[str] = field(default_factory=set)
    max_position_pct: float = 0.25
    max_order_value: float = 50000.0
    max_daily_orders: int = 10
    max_daily_trade_volume: float = 200000.0
    require_confirmation: bool = True
    allow_short: bool = False
    allow_margin: bool = False

    @classmethod
    def load(cls, path: Path | None = None) -> TradingMandate:
        path = path or DEFAULT_MANDATE_PATH
        if not path.exists():
            logger.info("No mandate at %s, using defaults", path)
            return cls()
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            allowed = raw.get("allowed_tickers", ["*"])
            blocked = raw.get("blocked_tickers", [])
            return cls(
                allowed_tickers=set(allowed) if isinstance(allowed, list) else {"*"},
                blocked_tickers=set(blocked) if isinstance(blocked, list) else set(),
                max_position_pct=float(raw.get("max_position_pct", 0.25)),
                max_order_value=float(raw.get("max_order_value", 50000.0)),
                max_daily_orders=int(raw.get("max_daily_orders", 10)),
                max_daily_trade_volume=float(raw.get("max_daily_trade_volume", 200000.0)),
                require_confirmation=bool(raw.get("require_confirmation", True)),
                allow_short=bool(raw.get("allow_short", False)),
                allow_margin=bool(raw.get("allow_margin", False)),
            )
        except Exception as exc:
            logger.warning("Failed to load mandate from %s: %s — using defaults", path, exc)
            return cls()

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_tickers": sorted(self.allowed_tickers),
            "blocked_tickers": sorted(self.blocked_tickers),
            "max_position_pct": self.max_position_pct,
            "max_order_value": self.max_order_value,
            "max_daily_orders": self.max_daily_orders,
            "max_daily_trade_volume": self.max_daily_trade_volume,
            "require_confirmation": self.require_confirmation,
            "allow_short": self.allow_short,
            "allow_margin": self.allow_margin,
        }
