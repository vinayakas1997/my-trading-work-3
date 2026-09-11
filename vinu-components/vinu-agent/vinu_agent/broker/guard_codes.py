"""Typed vocabulary for pre-trade decisions (Stage C, C9 + the enums C4/C17
build on).

Before this, every `OrderGuard` rejection was a free-text string and the
result was a plain allow/deny bool. That's fine for a human reading a log
but useless for anything that needs to *react differently* to different
rejection causes, audit transitions, or express "not a flat no". This
module is the shared enum set:

- `ReasonCode`   -- one stable code per decision cause (rejections + the
                    non-reject outcomes). String-valued so it serialises
                    straight into JSON audit rows.
- `GuardOutcome` -- ALLOW / REJECT / PAUSE_FOR_REAUTH (C17): a third state
                    for a breach that's near a hard limit but not over it,
                    routed to human confirmation rather than a flat reject.
- `OverrideState`-- per-symbol operator override (C4): UNTRADEABLE /
                    REDUCE_ONLY / IGNORED, with a precedence order for when
                    several apply and a valid-transition map (C9's
                    "valid-transition set").
"""

from __future__ import annotations

from enum import Enum


class GuardOutcome(str, Enum):
    ALLOW = "allow"
    REJECT = "reject"
    # C17: quantitatively near a hard limit (within the re-auth band) but
    # not past it -- the order is held for an explicit human confirmation
    # instead of being allowed through or hard-rejected. Distinct from the
    # mandate's unconditional `require_confirmation`, which pauses *every*
    # order regardless of how close to a limit it is.
    PAUSE_FOR_REAUTH = "pause_for_reauth"


class ReasonCode(str, Enum):
    OK = "ok"
    # --- hard safety ---
    KILL_SWITCH_HALT = "kill_switch_halt"
    ORDER_THROTTLE = "order_throttle"
    RISK_BUDGET_HALT = "risk_budget_halt"
    # --- mandate: static policy ---
    BLOCKED_TICKER = "blocked_ticker"
    TICKER_NOT_ALLOWED = "ticker_not_allowed"
    SHORT_NOT_PERMITTED = "short_not_permitted"
    MARKET_CLOSED = "market_closed"
    NO_ACTIVE_ARTIFACT = "no_active_artifact"
    MANDATE_EXPIRED = "mandate_expired"          # C18
    # --- mandate: numeric limits ---
    ORDER_VALUE_UNKNOWN = "order_value_unknown"
    MAX_ORDER_VALUE = "max_order_value"
    MAX_DAILY_ORDERS = "max_daily_orders"
    MAX_DAILY_ORDERS_PORTFOLIO = "max_daily_orders_portfolio"
    MAX_DAILY_TRADE_VOLUME = "max_daily_trade_volume"
    MAX_POSITION_PCT = "max_position_pct"
    MAX_CAPITAL_UTILIZATION = "max_capital_utilization"
    SYMBOL_CONCENTRATION = "symbol_concentration"
    PAIRWISE_CORRELATION = "pairwise_correlation"
    # --- per-symbol operator override (C4) ---
    OVERRIDE_UNTRADEABLE = "override_untradeable"
    OVERRIDE_REDUCE_ONLY = "override_reduce_only"
    # --- near-limit (C17) ---
    NEAR_MAX_ORDER_VALUE = "near_max_order_value"
    NEAR_MAX_POSITION_PCT = "near_max_position_pct"


class OverrideState(str, Enum):
    """Operator-set per-symbol override. `IGNORED` means "don't trade this
    at all, and don't even surface it" (distinct from `UNTRADEABLE`, which
    still reports a rejection an operator can see)."""

    UNTRADEABLE = "untradeable"      # reject all orders, with a visible reason
    REDUCE_ONLY = "reduce_only"      # allow risk-reducing orders only
    IGNORED = "ignored"             # silently drop; symbol is off the board


# Higher number = takes precedence when several overrides somehow coexist
# for one symbol. UNTRADEABLE is the most restrictive expressible-as-a-
# rejection; IGNORED sits above it only in the sense that it suppresses
# even the rejection.
OVERRIDE_PRECEDENCE: dict[OverrideState, int] = {
    OverrideState.REDUCE_ONLY: 1,
    OverrideState.UNTRADEABLE: 2,
    OverrideState.IGNORED: 3,
}


# C9: which override transitions are legitimate. An operator loosening
# UNTRADEABLE -> REDUCE_ONLY is fine; clearing (None) is always allowed and
# handled separately. Anything not listed here is refused by the store so a
# typo or a stale client can't put a symbol into an unexpected state.
ALLOWED_OVERRIDE_TRANSITIONS: dict[OverrideState | None, set[OverrideState]] = {
    None: {OverrideState.UNTRADEABLE, OverrideState.REDUCE_ONLY, OverrideState.IGNORED},
    OverrideState.REDUCE_ONLY: {OverrideState.UNTRADEABLE, OverrideState.IGNORED},
    OverrideState.UNTRADEABLE: {OverrideState.REDUCE_ONLY, OverrideState.IGNORED},
    OverrideState.IGNORED: {OverrideState.UNTRADEABLE, OverrideState.REDUCE_ONLY},
}


def transition_allowed(current: OverrideState | None, target: OverrideState | None) -> bool:
    """`target=None` (clear the override) is always allowed. Otherwise the
    (current -> target) pair must be in ALLOWED_OVERRIDE_TRANSITIONS."""
    if target is None:
        return True
    if current == target:
        return True
    return target in ALLOWED_OVERRIDE_TRANSITIONS.get(current, set())
