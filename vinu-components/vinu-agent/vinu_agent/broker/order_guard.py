"""Pre-trade safety checks — validates orders against mandate + kill switch."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from .alpaca import AlpacaBroker
from .kill_switch import is_trading_halted
from .mandate import TradingMandate

logger = logging.getLogger(__name__)


@dataclass
class GuardResult:
    allowed: bool
    reason: str = ""

    def __bool__(self) -> bool:
        return self.allowed


class OrderGuard:
    def __init__(
        self,
        mandate: TradingMandate | None = None,
        broker: AlpacaBroker | None = None,
    ) -> None:
        self._mandate = mandate or TradingMandate.load()
        self._broker = broker or AlpacaBroker()
        self._daily_order_count: dict[str, int] = {}
        self._last_reset_date: date = date.today()

    def _reset_daily_if_needed(self) -> None:
        today = date.today()
        if today != self._last_reset_date:
            self._daily_order_count.clear()
            self._last_reset_date = today

    def _count_daily_orders(self, symbol: str) -> int:
        self._reset_daily_if_needed()
        return self._daily_order_count.get(symbol, 0)

    def _increment_daily_count(self, symbol: str) -> None:
        self._reset_daily_if_needed()
        self._daily_order_count[symbol] = self._daily_order_count.get(symbol, 0) + 1

    def check(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float | None = None,
        estimated_value: float | None = None,
    ) -> GuardResult:
        if is_trading_halted():
            return GuardResult(False, "Trading is halted by kill switch")

        mandate = self._mandate

        if symbol in mandate.blocked_tickers:
            return GuardResult(False, f"{symbol} is in the blocked tickers list")

        if "*" not in mandate.allowed_tickers and symbol not in mandate.allowed_tickers:
            return GuardResult(False, f"{symbol} is not in the allowed tickers list")

        if side == "sell" and not mandate.allow_short:
            return GuardResult(False, "Short selling is not permitted by mandate")

        value = estimated_value or (qty * (price or 0.0))
        if value > mandate.max_order_value:
            return GuardResult(
                False,
                f"Order value {value:.2f} exceeds max_order_value {mandate.max_order_value:.2f}",
            )

        daily_count = self._count_daily_orders(symbol)
        if daily_count >= mandate.max_daily_orders:
            return GuardResult(
                False,
                f"Daily order limit ({mandate.max_daily_orders}) reached for {symbol}",
            )

        return GuardResult(True)

    def pre_approve(self, symbol: str, side: str, qty: float, price: float | None = None) -> GuardResult:
        result = self.check(symbol, side, qty, price)
        if result:
            self._increment_daily_count(symbol)
        return result
