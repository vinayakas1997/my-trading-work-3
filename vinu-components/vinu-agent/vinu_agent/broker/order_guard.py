"""Pre-trade safety checks — validates orders against mandate + kill switch."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import requests

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
        research_api_url: str | None = None,
        portfolio_api_url: str | None = None,
    ) -> None:
        self._mandate = mandate or TradingMandate.load()
        self._broker = broker or AlpacaBroker()
        self._research_api_url = research_api_url or os.environ.get(
            "VINU_RESEARCH_API_URL", "http://localhost:8087"
        )
        self._portfolio_api_url = portfolio_api_url or os.environ.get(
            "VINU_PORTFOLIO_API_URL", "http://localhost:8090"
        )
        self._daily_order_count: dict[str, int] = {}
        self._daily_volume: dict[str, float] = {}
        self._last_reset_date: date = date.today()

    def _reset_daily_if_needed(self) -> None:
        today = date.today()
        if today != self._last_reset_date:
            self._daily_order_count.clear()
            self._daily_volume.clear()
            self._last_reset_date = today

    def _count_daily_orders(self, symbol: str) -> int:
        self._reset_daily_if_needed()
        return self._daily_order_count.get(symbol, 0)

    def _increment_daily_count(self, symbol: str, value: float = 0.0) -> None:
        self._reset_daily_if_needed()
        self._daily_order_count[symbol] = self._daily_order_count.get(symbol, 0) + 1
        self._daily_volume[symbol] = self._daily_volume.get(symbol, 0.0) + value

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

        if mandate.max_position_pct < 1.0:
            try:
                account = self._broker.get_account()
                equity = float(account.equity)
                if equity > 0 and (value / equity) > mandate.max_position_pct:
                    return GuardResult(
                        False,
                        f"Position {value:.2f} would be {(value / equity):.1%} of equity "
                        f"({equity:.2f}), exceeding max_position_pct {mandate.max_position_pct:.0%}",
                    )
            except Exception as e:
                logger.warning("Could not check max_position_pct: %s", e)

        if mandate.max_capital_utilization_pct < 1.0:
            try:
                account = self._broker.get_account()
                equity = float(account.equity)
                # equity - cash = current market value of everything already
                # held, i.e. capital already deployed before this order.
                deployed = equity - float(account.cash)
                if equity > 0:
                    projected_utilization = (deployed + value) / equity
                    if projected_utilization > mandate.max_capital_utilization_pct:
                        return GuardResult(
                            False,
                            f"This order would bring total deployed capital to "
                            f"{projected_utilization:.1%} of equity ({equity:.2f}), exceeding "
                            f"max_capital_utilization_pct {mandate.max_capital_utilization_pct:.0%}",
                        )
            except Exception as e:
                logger.warning("Could not check max_capital_utilization_pct: %s", e)

        if mandate.require_active_artifact:
            active_result = self._check_active_artifact(symbol)
            if not active_result:
                return active_result

        if mandate.require_market_open:
            market_result = self._check_market_open()
            if not market_result:
                return market_result

        if mandate.max_symbol_concentration_pct < 1.0 or mandate.max_pairwise_correlation < 1.0:
            concentration_result = self._check_portfolio_concentration(symbol, side, value)
            if not concentration_result:
                return concentration_result

        if mandate.max_daily_trade_volume > 0:
            self._reset_daily_if_needed()
            daily_total = self._daily_volume.get(symbol, 0.0)
            if daily_total + value > mandate.max_daily_trade_volume:
                return GuardResult(
                    False,
                    f"Daily trade volume {daily_total + value:.2f} would exceed "
                    f"max_daily_trade_volume {mandate.max_daily_trade_volume:.2f}",
                )

        return GuardResult(True)

    def _check_active_artifact(self, symbol: str) -> GuardResult:
        """Reject orders for symbols with no strategy artifact that cleared the
        promotion gate (deflated Sharpe + holdout + stress test, see vinu-research).

        Fails open (allows the order, logs a warning) if the research-api is
        unreachable — consistent with how every other broker-dependent check in
        this class handles a downstream outage, so one unavailable service can't
        silently block all trading.
        """
        try:
            resp = requests.get(
                f"{self._research_api_url}/research/artifacts",
                params={"status": "ACTIVE"},
                timeout=10.0,
            )
            resp.raise_for_status()
            artifacts = resp.json()
        except Exception as e:
            logger.warning("Could not check active-artifact status for %s: %s", symbol, e)
            return GuardResult(True)

        for artifact in artifacts:
            if symbol in (artifact.get("universe") or []):
                return GuardResult(True)

        return GuardResult(
            False,
            f"{symbol} has no ACTIVE strategy artifact — it has not cleared the "
            f"research promotion gate (deflated Sharpe / holdout / stress test). "
            f"Set require_active_artifact: false in the mandate to override.",
        )

    def _check_market_open(self) -> GuardResult:
        """Reject orders while the market is closed, per Alpaca's clock endpoint.

        Fails open (allows the order, logs a warning) if the clock call fails —
        same posture as every other broker-dependent check in this class.
        """
        try:
            clock = self._broker.get_clock()
        except Exception as e:
            logger.warning("Could not check market clock: %s", e)
            return GuardResult(True)

        if not clock.get("is_open", True):
            return GuardResult(
                False,
                f"Market is closed (next open: {clock.get('next_open', 'unknown')}). "
                f"Set require_market_open: false in the mandate to allow orders that queue for open.",
            )
        return GuardResult(True)

    def _check_portfolio_concentration(self, symbol: str, side: str, value: float) -> GuardResult:
        """Re-check vinu-portfolio's current target weights and correlation
        matrix at order time — defense-in-depth against `OrderGuard`'s other
        checks, which only ever reason about this one order/symbol in
        isolation. Only applies to buy orders: a sell reduces exposure, so
        blocking it on concentration/correlation grounds would be actively
        harmful, not protective. Fails open (allows the order, logs a
        warning) if vinu-portfolio is unreachable, same posture as every
        other broker/service-dependent check in this class.
        """
        if side != "buy":
            return GuardResult(True)

        mandate = self._mandate
        try:
            resp = requests.get(f"{self._portfolio_api_url}/portfolio/state", timeout=10.0)
            resp.raise_for_status()
            portfolio = resp.json()
        except Exception as e:
            logger.warning("Could not check portfolio concentration for %s: %s", symbol, e)
            return GuardResult(True)

        weights = portfolio.get("weights") or []

        if mandate.max_symbol_concentration_pct < 1.0:
            existing_weight = sum(
                w.get("target_weight", 0.0) for w in weights if w.get("symbol") == symbol
            )
            if existing_weight > mandate.max_symbol_concentration_pct:
                return GuardResult(
                    False,
                    f"{symbol} already accounts for {existing_weight:.1%} of the portfolio's "
                    f"target weight, exceeding max_symbol_concentration_pct "
                    f"{mandate.max_symbol_concentration_pct:.0%} — vinu-portfolio and execution "
                    f"may have drifted out of sync.",
                )

        if mandate.max_pairwise_correlation < 1.0:
            matrix = portfolio.get("correlation_matrix")
            # correlation_matrix is keyed by strategy name, not symbol (see
            # vinu_portfolio.service.PortfolioService.build_portfolio) — map
            # through `weights`, which carries both, rather than assuming
            # strategy name == ticker symbol.
            strategy_symbol = {w.get("name"): w.get("symbol") for w in weights}
            if matrix:
                names = matrix.get("strategies", [])
                values = matrix.get("values", [])
                our_rows = [i for i, n in enumerate(names) if strategy_symbol.get(n) == symbol]
                held_cols = [
                    j for j, n in enumerate(names)
                    if strategy_symbol.get(n) not in (None, symbol)
                    and any(w.get("name") == n and w.get("target_weight", 0.0) > 0 for w in weights)
                ]
                for i in our_rows:
                    if i >= len(values):
                        continue
                    row = values[i]
                    for j in held_cols:
                        if j >= len(row):
                            continue
                        corr = row[j]
                        other_symbol = strategy_symbol.get(names[j])
                        if corr is not None and abs(corr) > mandate.max_pairwise_correlation:
                            return GuardResult(
                                False,
                                f"{symbol} has {corr:.2f} correlation with {other_symbol}, which "
                                f"already has portfolio weight — exceeds max_pairwise_correlation "
                                f"{mandate.max_pairwise_correlation:.2f}",
                            )

        return GuardResult(True)

    def pre_approve(self, symbol: str, side: str, qty: float, price: float | None = None) -> GuardResult:
        result = self.check(symbol, side, qty, price)
        if result:
            value = qty * (price or 0.0)
            self._increment_daily_count(symbol, value)
        return result
