"""Pre-trade safety checks — validates orders against mandate + kill switch."""

from __future__ import annotations

import logging
import os
import time
from collections import deque
from dataclasses import dataclass

import requests

from .base import Broker
from .daily_limits import DEFAULT_DAILY_LIMIT_DB_PATH, DailyLimitStore
from .factory import get_live_broker
from .guard_codes import GuardOutcome, ReasonCode
from .kill_switch import is_trading_halted
from .mandate import TradingMandate

logger = logging.getLogger(__name__)

# C17: an order whose value / position size lands in the top
# (1 - fraction) band below a hard mandate limit is held for explicit human
# confirmation rather than allowed straight through. 1.0 (default) disables
# the band -- nothing is "near" a limit -- so this is opt-in, same posture
# as every other new numeric knob in this file.
REAUTH_BAND_FRACTION = float(os.environ.get("VINU_AGENT_GUARD_REAUTH_FRACTION", "1.0"))


def _halt_policy_allows_reduce_only() -> bool:
    """Same knob vinu-live's orchestrator.py reads for its own local
    breaker (_halt_allows_exit) -- one env var controls both halt layers,
    so operators only have one policy to reason about, not two that can
    silently disagree. Default "entries_only" matches the documented
    default in .env-example / VINU_LIVE_HALT_POLICY."""
    return os.environ.get("VINU_LIVE_HALT_POLICY", "entries_only") == "entries_only"


@dataclass
class GuardResult:
    allowed: bool
    reason: str = ""
    # C9/C17: a stable machine code for the decision cause, and a
    # three-valued outcome. Both are optional and default consistently with
    # `allowed`, so every existing `GuardResult(True)` / `GuardResult(False,
    # "...")` call site keeps working unchanged.
    code: ReasonCode | None = None
    outcome: GuardOutcome | None = None

    def __post_init__(self) -> None:
        if self.outcome is None:
            self.outcome = GuardOutcome.ALLOW if self.allowed else GuardOutcome.REJECT
        if self.code is None:
            self.code = ReasonCode.OK if self.allowed else None

    def __bool__(self) -> bool:
        return self.allowed

    @property
    def needs_reauth(self) -> bool:
        """True when the order isn't a flat reject but must be held for an
        explicit human confirmation (C17). `allowed` is False for these, so
        a caller that only checks the bool still fails safe."""
        return self.outcome == GuardOutcome.PAUSE_FOR_REAUTH


def _reauth(reason: str, code: ReasonCode) -> GuardResult:
    return GuardResult(False, reason, code=code, outcome=GuardOutcome.PAUSE_FOR_REAUTH)


# C8: soft-limit sizing. Opt-in -- when off (default), the quantitative
# mandate limits hard-reject as before. When on, a caller asks
# `OrderGuard.position_size_multiplier(...)` for a [0, 1] scalar first,
# shrinks the order by it, then submits the smaller order through the
# still-fail-closed `check()`. Mirrors pysystemtrade's "min of N independent
# risk multipliers" instead of "first failing check rejects".
SOFT_LIMITS_ENABLED = os.environ.get("VINU_AGENT_GUARD_SOFT_LIMITS", "false").lower() in ("1", "true", "yes")


@dataclass
class MultiplierResult:
    multiplier: float            # min of every component, clamped to [0, 1]
    components: dict             # {check_name: its own [0,1] multiplier}
    binding: str | None          # the check that produced the min (None if multiplier == 1.0)


class OrderGuard:
    def __init__(
        self,
        mandate: TradingMandate | None = None,
        broker: Broker | None = None,
        portfolio_api_url: str | None = None,
        daily_limit_store: DailyLimitStore | None = None,
        override_store=None,
        limit_store=None,
    ) -> None:
        self._mandate = mandate or TradingMandate.load()
        self._broker = broker or get_live_broker()
        # C4: per-symbol operator overrides (untradeable / reduce_only /
        # ignored). Consulted before any mandate check. Lazy import + lazy
        # singleton so constructing an OrderGuard never touches disk for a
        # feature nobody has used.
        self._override_store = override_store
        self._override_store_explicit = override_store is not None
        # C7: per-symbol *limit-value* overrides (tighter max_order_value /
        # max_position_pct / max_capital_utilization_pct than the mandate's
        # global defaults) -- same lazy-singleton posture as override_store.
        self._limit_store = limit_store
        self._limit_store_explicit = limit_store is not None
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
        # In-process throttle window (B20): sliding-window order-rate limiter,
        # deque of monotonic timestamps. Fresh instance per execute() means
        # window is per-process burst, not persisted — sufficient to block
        # runaway loop (the #1 live blow-up per QuantMemo) without DB.
        #
        # Stage A (A15): rate + window are env-configurable so an operator
        # can tighten the runaway-loop breaker without a code change, same
        # posture as every other numeric limit in this file. Boot-time only
        # (read once here), NOT a live RuntimeSettings knob — this is a hard
        # safety ceiling, not a tuning dial, and belongs in the same
        # "restart to change" category as the mandate's pass/fail switches.
        self._throttle_window: deque[float] = deque()
        self._throttle_limit_per_sec = int(
            os.environ.get("VINU_AGENT_ORDER_THROTTLE_PER_SEC", "10")
        )
        self._throttle_window_sec = float(
            os.environ.get("VINU_AGENT_ORDER_THROTTLE_WINDOW_SEC", "1.0")
        )
        # _risk_budget_multiplier (called from position_size_multiplier, when
        # soft-limits are on) and _check_risk_budget (called from check())
        # used to each independently GET /portfolio/risk/status -- both run
        # against the same OrderGuard instance for the one symbol a single
        # trade_tool.py execute() call is ever about, so a per-instance
        # memo here is exactly enough to turn two network round-trips per
        # order into one, with no cross-order staleness risk (the instance
        # doesn't outlive one execute() call).
        self._risk_budget_cache: dict[str, dict | None] = {}

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
        reduce_only: bool = False,
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
        #
        # Stage 1 (how-to-make-it-live.md): this used to block ALL orders
        # unconditionally on halt, including exits -- meaning a position
        # could get trapped mid-crash by the exact -20% drawdown breaker
        # that was supposed to be protecting it. vinu-live's local breaker
        # (orchestrator.py's _halt_allows_exit()) already made this
        # distinction for its own HALT check; this mirrors the same
        # VINU_LIVE_HALT_POLICY policy at the real order-execution
        # boundary so a reduce-only order (an exit or a position decrease,
        # never a new/increasing position) still clears the global kill
        # switch when the policy is entries-only.
        if is_trading_halted(scope=symbol):
            if reduce_only and _halt_policy_allows_reduce_only():
                logger.warning(
                    "Kill switch halted for %s, but allowing reduce-only order "
                    "(side=%s qty=%s) through -- VINU_LIVE_HALT_POLICY=entries_only",
                    symbol, side, qty,
                )
            else:
                return GuardResult(False, "Trading is halted by kill switch", code=ReasonCode.KILL_SWITCH_HALT)

        # B20 — message throttle (10 orders/sec per instance)
        now = time.monotonic()
        while self._throttle_window and now - self._throttle_window[0] > self._throttle_window_sec:
            self._throttle_window.popleft()
        if len(self._throttle_window) >= self._throttle_limit_per_sec:
            # A15: a tripped throttle means something upstream is submitting
            # in a tight loop — the exact failure mode this breaker exists
            # for. Log it at WARNING (the kill-switch path already does the
            # same) so it surfaces in alerting instead of being a silent
            # rejection buried in one caller's return value.
            logger.warning(
                "Order throttle tripped for %s (%s): >= %d orders in %.2fs — "
                "possible runaway submission loop",
                symbol, side, self._throttle_limit_per_sec, self._throttle_window_sec,
            )
            return GuardResult(
                False,
                f"Order throttle: {self._throttle_limit_per_sec} orders / "
                f"{self._throttle_window_sec:g}s limit exceeded",
                code=ReasonCode.ORDER_THROTTLE,
            )
        self._throttle_window.append(now)

        # C4: per-symbol operator override, ahead of any mandate check.
        override_result = self._check_symbol_override(symbol, reduce_only)
        if not override_result:
            return override_result

        mandate = self._mandate

        # C18: a stale mandate is not a mandate. Block new/increasing
        # positions once operator consent has expired -- reduce_only orders
        # (de-risking) are always exempt, same posture as the kill switch.
        if not reduce_only and mandate.consent_expired():
            return GuardResult(
                False,
                f"Trading mandate consent expired at {mandate.consent_expires_at} — "
                f"renew it (edit consent_expires_at in mandate.yaml, or "
                f"POST /agent/broker/mandate/renew) before opening or increasing positions. "
                f"Risk-reducing orders are still allowed.",
                code=ReasonCode.MANDATE_EXPIRED,
            )

        if symbol in mandate.blocked_tickers:
            return GuardResult(False, f"{symbol} is in the blocked tickers list", code=ReasonCode.BLOCKED_TICKER)

        if "*" not in mandate.allowed_tickers and symbol not in mandate.allowed_tickers:
            return GuardResult(False, f"{symbol} is not in the allowed tickers list", code=ReasonCode.TICKER_NOT_ALLOWED)

        if side == "sell" and not mandate.allow_short:
            return GuardResult(False, "Short selling is not permitted by mandate", code=ReasonCode.SHORT_NOT_PERMITTED)

        # Stage A (A36, Vibe-Trading `order_guard.py`): take the LARGER of the
        # caller's explicit notional and qty*price, never just whichever was
        # passed -- an under-stated `estimated_value` must not be able to slip
        # a too-big order past the cap. And fail CLOSED when neither yields a
        # usable number: a blind `estimated_value or qty*(price or 0)` used to
        # collapse to 0.0 for an unpriceable order, which then trivially
        # cleared `value > max_order_value`. reduce_only is exempt -- a
        # risk-reducing order should still go through even if we can't price
        # it, same posture as the kill-switch / risk-budget exemptions below.
        value = max(estimated_value or 0.0, qty * (price or 0.0))
        if value <= 0.0 and not reduce_only:
            return GuardResult(
                False,
                "Cannot determine order value — no usable price or estimated_value. "
                "Supply a limit price (or estimated_value) so the notional cap can be enforced.",
                code=ReasonCode.ORDER_VALUE_UNKNOWN,
            )
        # C7: a per-symbol max_order_value override, if one is set, replaces
        # the mandate's global default for every check below.
        max_order_value = self._effective_limit(symbol, "max_order_value", mandate.max_order_value)
        if value > max_order_value:
            return GuardResult(
                False,
                f"Order value {value:.2f} exceeds max_order_value {max_order_value:.2f}",
                code=ReasonCode.MAX_ORDER_VALUE,
            )
        # C17: within the top band below the hard cap -> hold for confirmation.
        if (
            not reduce_only
            and REAUTH_BAND_FRACTION < 1.0
            and value > max_order_value * REAUTH_BAND_FRACTION
        ):
            return _reauth(
                f"Order value {value:.2f} is within {(1 - REAUTH_BAND_FRACTION):.0%} of the hard "
                f"max_order_value {max_order_value:.2f} — confirm to proceed",
                ReasonCode.NEAR_MAX_ORDER_VALUE,
            )

        daily_count = self._count_daily_orders(symbol)
        if daily_count >= mandate.max_daily_orders:
            return GuardResult(
                False,
                f"Daily order limit ({mandate.max_daily_orders}) reached for {symbol}",
                code=ReasonCode.MAX_DAILY_ORDERS,
            )

        # Stage 2 (how-to-make-it-live.md #8): max_daily_orders above is
        # per-symbol only -- 10/symbol x 20 traded symbols is 200 orders/day
        # with nothing capping the total. Exempt reduce_only: a portfolio-
        # wide overtrading cap must never be the thing that stops you from
        # de-risking on a bad day, same posture as the kill-switch and
        # risk-budget reduce_only exemptions above.
        if mandate.max_daily_orders_portfolio > 0 and not reduce_only:
            total_count = self._daily_limit_store.count_today_total()
            if total_count >= mandate.max_daily_orders_portfolio:
                return GuardResult(
                    False,
                    f"Portfolio-wide daily order limit ({mandate.max_daily_orders_portfolio}) "
                    f"reached across all symbols",
                    code=ReasonCode.MAX_DAILY_ORDERS_PORTFOLIO,
                )

        # C7: per-symbol overrides for the remaining two soft limits, same
        # "override replaces the mandate default wherever it's read" rule.
        max_position_pct = self._effective_limit(symbol, "max_position_pct", mandate.max_position_pct)
        max_capital_utilization_pct = self._effective_limit(
            symbol, "max_capital_utilization_pct", mandate.max_capital_utilization_pct
        )

        # Fetch the account once and reuse it for both percentage checks
        # below, instead of each independently calling get_account() --
        # also means both checks reason about the same point-in-time
        # snapshot rather than two calls microseconds apart that could
        # observe a fill landing in between.
        account = None
        if max_position_pct < 1.0 or max_capital_utilization_pct < 1.0:
            try:
                account = self._broker.get_account()
            except Exception as e:
                logger.warning("Could not fetch account for position/utilization checks: %s", e)

        if max_position_pct < 1.0 and account is not None:
            try:
                equity = float(account.equity)
                if equity > 0:
                    frac = value / equity
                    if frac > max_position_pct:
                        return GuardResult(
                            False,
                            f"Position {value:.2f} would be {frac:.1%} of equity "
                            f"({equity:.2f}), exceeding max_position_pct {max_position_pct:.0%}",
                            code=ReasonCode.MAX_POSITION_PCT,
                        )
                    if (
                        not reduce_only
                        and REAUTH_BAND_FRACTION < 1.0
                        and frac > max_position_pct * REAUTH_BAND_FRACTION
                    ):
                        return _reauth(
                            f"Position would be {frac:.1%} of equity — within "
                            f"{(1 - REAUTH_BAND_FRACTION):.0%} of the hard max_position_pct "
                            f"{max_position_pct:.0%} — confirm to proceed",
                            ReasonCode.NEAR_MAX_POSITION_PCT,
                        )
            except Exception as e:
                logger.warning("Could not check max_position_pct: %s", e)

        if max_capital_utilization_pct < 1.0 and account is not None:
            try:
                equity = float(account.equity)
                # equity - cash = current market value of everything already
                # held, i.e. capital already deployed before this order.
                deployed = equity - float(account.cash)
                if equity > 0:
                    projected_utilization = (deployed + value) / equity
                    if projected_utilization > max_capital_utilization_pct:
                        return GuardResult(
                            False,
                            f"This order would bring total deployed capital to "
                            f"{projected_utilization:.1%} of equity ({equity:.2f}), exceeding "
                            f"max_capital_utilization_pct {max_capital_utilization_pct:.0%}",
                            code=ReasonCode.MAX_CAPITAL_UTILIZATION,
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

        if not reduce_only:
            risk_budget_result = self._check_risk_budget(symbol, side)
            if not risk_budget_result:
                return risk_budget_result

        if mandate.max_daily_trade_volume > 0:
            daily_total = self._daily_limit_store.volume_today(symbol)
            if daily_total + value > mandate.max_daily_trade_volume:
                return GuardResult(
                    False,
                    f"Daily trade volume {daily_total + value:.2f} would exceed "
                    f"max_daily_trade_volume {mandate.max_daily_trade_volume:.2f}",
                    code=ReasonCode.MAX_DAILY_TRADE_VOLUME,
                )

        return GuardResult(True)

    def _get_limit_store(self):
        if self._limit_store is None and not self._limit_store_explicit:
            try:
                from .symbol_limits import get_limit_store

                self._limit_store = get_limit_store()
            except Exception as e:  # noqa: BLE001 -- limit overrides are optional
                logger.warning("Could not load the symbol-limit store: %s", e)
                self._limit_store_explicit = True  # don't retry every call
        return self._limit_store

    def _effective_limit(self, symbol: str, field: str, default: float) -> float:
        """C7: a per-symbol override for `field` (one of `max_order_value`,
        `max_position_pct`, `max_capital_utilization_pct`), else the
        mandate's global `default`. Fails open to `default` on any store
        error -- same posture as `_check_symbol_override`: a limit-store
        hiccup must not change trading behaviour, it just means no
        per-symbol tightening is applied for this check."""
        try:
            store = self._get_limit_store()
            if store is None:
                return default
            rec = store.get(symbol)
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not check symbol limit override for %s.%s: %s", symbol, field, e)
            return default
        if rec is None:
            return default
        value = getattr(rec, field, None)
        return value if value is not None else default

    def _get_override_store(self):
        if self._override_store is None and not self._override_store_explicit:
            try:
                from .symbol_overrides import get_override_store

                self._override_store = get_override_store()
            except Exception as e:  # noqa: BLE001 -- overrides are optional
                logger.warning("Could not load the symbol-override store: %s", e)
                self._override_store_explicit = True  # don't retry every call
        return self._override_store

    def _check_symbol_override(self, symbol: str, reduce_only: bool) -> GuardResult:
        """C4: honour a per-symbol operator override. Fails OPEN (allows the
        order) if the store can't be read -- an override store hiccup must
        not halt all trading; the mandate + kill switch are still in force."""
        try:
            store = self._get_override_store()
            if store is None:
                return GuardResult(True)
            rec = store.get(symbol)
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not check symbol override for %s: %s", symbol, e)
            return GuardResult(True)

        if rec is None:
            return GuardResult(True)

        from .guard_codes import OverrideState

        note = f" (set by {rec.set_by})" if rec.set_by else ""
        if rec.state is OverrideState.IGNORED:
            return GuardResult(
                False,
                f"{symbol} is IGNORED by operator override{note}: {rec.reason or 'no reason given'}",
                code=ReasonCode.OVERRIDE_UNTRADEABLE,
            )
        if rec.state is OverrideState.UNTRADEABLE:
            return GuardResult(
                False,
                f"{symbol} is marked UNTRADEABLE by operator override{note}: "
                f"{rec.reason or 'no reason given'}",
                code=ReasonCode.OVERRIDE_UNTRADEABLE,
            )
        if rec.state is OverrideState.REDUCE_ONLY and not reduce_only:
            return GuardResult(
                False,
                f"{symbol} is REDUCE-ONLY by operator override{note}: "
                f"{rec.reason or 'no reason given'} — only risk-reducing orders are allowed",
                code=ReasonCode.OVERRIDE_REDUCE_ONLY,
            )
        return GuardResult(True)

    def position_size_multiplier(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float | None = None,
        estimated_value: float | None = None,
    ) -> MultiplierResult:
        """C8: a [0, 1] scalar to shrink an order so it *fits* the soft
        quantitative limits, instead of the order being hard-rejected for
        breaching one. Only the limits where "trade smaller" is a sensible
        response contribute -- `max_order_value`, `max_position_pct`,
        `max_capital_utilization_pct`, and vinu-portfolio's per-symbol
        risk-budget `suggested_size_multiplier`. Hard gates (kill switch,
        blocked ticker, market closed, operator override, ...) are NOT here
        -- `check()` still enforces those unconditionally. Every lookup
        failure contributes 1.0 (no constraint), same fail-open posture as
        the individual checks."""
        comps: dict[str, float] = {}
        mandate = self._mandate
        value = max(estimated_value or 0.0, qty * (price or 0.0))

        # C7: same per-symbol override lookup `check()` uses -- a tighter
        # symbol-specific limit must shrink the suggested size the same way
        # the hard mandate limit would, or C4/C7 and C8 would silently
        # disagree about how big an order for this symbol is allowed to be.
        max_order_value = self._effective_limit(symbol, "max_order_value", mandate.max_order_value)
        max_position_pct = self._effective_limit(symbol, "max_position_pct", mandate.max_position_pct)
        max_capital_utilization_pct = self._effective_limit(
            symbol, "max_capital_utilization_pct", mandate.max_capital_utilization_pct
        )

        if max_order_value > 0 and value > 0:
            comps["max_order_value"] = min(1.0, max_order_value / value)

        if value > 0 and (max_position_pct < 1.0 or max_capital_utilization_pct < 1.0):
            try:
                account = self._broker.get_account()
                equity = float(account.equity)
                cash = float(account.cash)
                if equity > 0:
                    if max_position_pct < 1.0:
                        frac = value / equity
                        if frac > 0:
                            comps["max_position_pct"] = min(1.0, max_position_pct / frac)
                    if max_capital_utilization_pct < 1.0:
                        deployed = equity - cash
                        headroom = max_capital_utilization_pct * equity - deployed
                        comps["max_capital_utilization"] = max(0.0, min(1.0, headroom / value))
            except Exception as e:
                logger.warning("Could not compute equity-based size multipliers for %s: %s", symbol, e)

        rb = self._risk_budget_multiplier(symbol)
        if rb is not None:
            comps["risk_budget"] = max(0.0, min(1.0, rb))

        if not comps:
            return MultiplierResult(1.0, {}, None)
        m = max(0.0, min(1.0, min(comps.values())))
        binding = min(comps, key=lambda k: comps[k]) if m < 1.0 else None
        return MultiplierResult(m, comps, binding)

    def _fetch_risk_budget(self, symbol: str) -> dict | None:
        """GET /portfolio/risk/status, memoized per instance (see __init__)
        so _risk_budget_multiplier and _check_risk_budget -- both of which
        may run for the same symbol within one order's check -- only ever
        hit the network once. None on any lookup problem (fail-open;
        callers already treat None as "no data")."""
        if symbol in self._risk_budget_cache:
            return self._risk_budget_cache[symbol]
        try:
            try:
                from vinu_infra.auth import internal_auth_headers as _iah
                _h = _iah() or None
            except Exception:
                _h = None
            resp = requests.get(f"{self._portfolio_api_url}/portfolio/risk/status", headers=_h, timeout=10.0)
            resp.raise_for_status()
            budget = resp.json()
        except Exception as e:
            logger.warning("Could not fetch risk budget for %s: %s", symbol, e)
            self._risk_budget_cache[symbol] = None
            return None
        self._risk_budget_cache[symbol] = budget
        return budget

    def _risk_budget_multiplier(self, symbol: str) -> float | None:
        """vinu-portfolio's per-symbol `suggested_size_multiplier` for the
        warning/reduce tiers (the halt tier is handled as a hard reject in
        `_check_risk_budget`). None on any lookup problem."""
        budget = self._fetch_risk_budget(symbol)
        if budget is None:
            return None
        for s in budget.get("symbols", []):
            if s.get("symbol") == symbol:
                mult = s.get("suggested_size_multiplier")
                try:
                    return float(mult) if mult is not None else None
                except (TypeError, ValueError):
                    return None
        return None

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
            code=ReasonCode.NO_ACTIVE_ARTIFACT,
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
                code=ReasonCode.MARKET_CLOSED,
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
            try:
                from vinu_infra.auth import internal_auth_headers as _iah
                _h = _iah() or None
            except Exception:
                _h = None
            resp = requests.get(f"{self._portfolio_api_url}/portfolio/state", headers=_h, timeout=10.0)
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
                    code=ReasonCode.SYMBOL_CONCENTRATION,
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
                                code=ReasonCode.PAIRWISE_CORRELATION,
                            )

        return GuardResult(True)

    def _check_risk_budget(self, symbol: str, side: str) -> GuardResult:
        """Stage 2 (how-to-make-it-live.md #22): vinu-portfolio's
        compute_risk_budget() already computes a correct per-symbol tier
        (warning/-1%, reduce/-2%, halt/-3% of equity) and a
        suggested_size_multiplier, but nothing downstream ever enforced it
        -- it was a decision-support number on a dashboard, not a guard. A
        symbol at TIER_HALT (suggested_size_multiplier 0.0) could still
        receive new orders because OrderGuard never asked.

        Only blocks NEW/increasing exposure (reduce_only orders skip this
        check entirely, same posture as the kill-switch exemption above --
        risk-reducing an already-halted symbol is exactly what should still
        be allowed). Fails open on any lookup problem, same posture as
        _check_portfolio_concentration.
        """
        budget = self._fetch_risk_budget(symbol)
        if budget is None:
            return GuardResult(True)

        for s in budget.get("symbols", []):
            if s.get("symbol") != symbol:
                continue
            if s.get("halted"):
                return GuardResult(
                    False,
                    f"{symbol} is at risk-budget TIER_HALT (daily P&L "
                    f"{s.get('daily_pnl_pct', 0):.2f}% of equity) — new/increasing "
                    f"orders blocked until the next trading day; risk-reducing "
                    f"orders are still allowed.",
                    code=ReasonCode.RISK_BUDGET_HALT,
                )
            break

        return GuardResult(True)

    def pre_approve(
        self, symbol: str, side: str, qty: float, price: float | None = None, reduce_only: bool = False,
    ) -> GuardResult:
        result = self.check(symbol, side, qty, price, reduce_only=reduce_only)
        if result:
            value = qty * (price or 0.0)
            self._increment_daily_count(symbol, value)
        return result
