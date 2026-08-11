"""Pre-trade safety checks — validates orders against mandate + kill switch."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import requests

from .base import Broker
from .daily_limits import DEFAULT_DAILY_LIMIT_DB_PATH, DailyLimitStore
from .factory import get_live_broker
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
        broker: Broker | None = None,
        portfolio_api_url: str | None = None,
        daily_limit_store: DailyLimitStore | None = None,
    ) -> None:
        self._mandate = mandate or TradingMandate.load()
        self._broker = broker or get_live_broker()
        # No research_api_url anymore -- the active-artifact check reads
        # vinu-research's strategy_store.db directly, in-process (see
        # _check_active_artifact / .research_link).
        self._portfolio_api_url = portfolio_api_url or os.environ.get(
            "VINU_PORTFOLIO_API_URL", "http://localhost:8090"
        )
        # Persistent, shared, SQLite-backed -- NOT a plain in-process dict.
        # OrderGuard is constructed fresh on every trade_tool.py execute()
        # call; a dict here would silently reset to empty every time,
        # which is exactly the bug this store closes (see
        # daily_limits.py's module docstring).
        self._daily_limit_store = daily_limit_store or DailyLimitStore(DEFAULT_DAILY_LIMIT_DB_PATH)

    def _count_daily_orders(self, symbol: str) -> int:
        return self._daily_limit_store.count_today(symbol)

    def _increment_daily_count(self, symbol: str, value: float = 0.0) -> None:
        self._daily_limit_store.record_order(symbol, value)

    def check(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float | None = None,
        estimated_value: float | None = None,
    ) -> GuardResult:
        # Phase 3 (New-talk-agents/new-thinking/new-restructure/phases/
        # phase-3-kill-switch/): scope convention is the ticker symbol --
        # matches what's available on both sides (a halt issuer scopes to
        # a symbol; this check has `symbol` right here). Before this,
        # is_trading_halted() was called with no scope at all, so a
        # symbol-scoped halt (as opposed to a global one) never actually
        # blocked anything at the real order-execution boundary -- this is
        # that boundary, shared by both the LLM's submit_order tool and
        # vinu-live's order placement (both route through /broker/order).
        # is_trading_halted(scope=...) already checks the global halt
        # first internally, so this one call covers both.
        if is_trading_halted(scope=symbol):
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
            daily_total = self._daily_limit_store.volume_today(symbol)
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

        Reads vinu-research's real strategy_store.db directly, in-process
        (see .research_link) -- no network call, since vinu-research is no
        longer assumed to be running as a separate service. Still fails
        open (allows the order, logs a warning) on any exception: a
        missing/corrupt local DB shouldn't silently block all trading any
        more than a downstream outage used to.
        """
        try:
            from vinu_research.models import ArtifactStatus

            from .research_link import get_strategy_store

            store = get_strategy_store()
            artifacts = store.list_artifacts_for_symbol(symbol, statuses=[ArtifactStatus.ACTIVE])
        except Exception as e:
            logger.warning("Could not check active-artifact status for %s: %s", symbol, e)
            return GuardResult(True)

        if artifacts:
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
