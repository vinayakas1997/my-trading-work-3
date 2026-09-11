import json
import logging
import os

from ..agent.tools import BaseTool
from ..broker.factory import get_live_broker
from ..broker.historical_broker import HistoricalFillBroker
from ..broker.kill_switch import AuditLogger
from ..broker.mandate import TradingMandate
from ..broker.order_guard import OrderGuard

logger = logging.getLogger(__name__)


def _replay_state_path(session_id: str) -> str:
    root = os.environ.get("VINU_AGENT_DATA_ROOT", "/data")
    return os.path.join(root, "replay_state", f"{session_id}.json")


def _make_broker(as_of: str | None, session_id: str = ""):
    if as_of:
        return HistoricalFillBroker(
            as_of=as_of,
            state_path=_replay_state_path(session_id),
        )
    return get_live_broker()


class TradeTool(BaseTool):
    name = "submit_order"
    description = "Submit a trade order to Alpaca paper trading. Every order is validated against the trading mandate before execution."
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Ticker symbol (e.g., AAPL)"},
            "qty": {"type": "number", "description": "Number of shares"},
            "side": {
                "type": "string",
                "description": "Order side",
                "enum": ["buy", "sell"],
            },
            "order_type": {
                "type": "string",
                "description": "Order type (default: market)",
                "enum": ["market", "limit", "stop", "stop_limit"],
            },
            "limit_price": {
                "type": "number",
                "description": "Limit price (required for limit/stop_limit orders)",
            },
            "stop_price": {
                "type": "number",
                "description": "Stop price (required for stop/stop_limit orders)",
            },
            "time_in_force": {
                "type": "string",
                "description": "Time in force (default: day)",
                "enum": ["day", "gtc", "opg", "cls", "ioc", "fok"],
            },
            "take_profit_price": {
                "type": "number",
                "description": "Optional profit-target exit price. With stop_loss_price, attaches a real bracket order at entry so the exit is a resting order, not a manual follow-up.",
            },
            "stop_loss_price": {
                "type": "number",
                "description": "Optional stop-loss trigger price. Attaches a real stop order at entry so the exit is a resting order, not a manual follow-up.",
            },
            "stop_loss_limit_price": {
                "type": "number",
                "description": "Optional limit price for the stop-loss leg (stop-limit instead of stop-market). Only used if stop_loss_price is set.",
            },
            "reduce_only": {
                "type": "boolean",
                "description": "True if this order only closes or shrinks an existing position (an exit or a partial reduce), never opens/increases one. Reduce-only orders are still allowed through a kill-switch halt when VINU_LIVE_HALT_POLICY=entries_only (default); a mis-flagged increasing order is caught downstream by OrderGuard's other checks, not by this flag alone.",
            },
        },
        "required": ["symbol", "qty", "side"],
    }
    is_readonly = False
    _as_of: str | None = None
    _session_id: str = ""

    def execute(self, **kwargs) -> str:
        symbol = kwargs["symbol"].upper()
        qty = float(kwargs["qty"])
        side = kwargs["side"]
        order_type = kwargs.get("order_type", "market")
        limit_price = kwargs.get("limit_price")
        stop_price = kwargs.get("stop_price")
        time_in_force = kwargs.get("time_in_force", "day")
        take_profit_price = kwargs.get("take_profit_price")
        stop_loss_price = kwargs.get("stop_loss_price")
        stop_loss_limit_price = kwargs.get("stop_loss_limit_price")
        reduce_only = bool(kwargs.get("reduce_only", False))
        client_order_id = kwargs.get("client_order_id") or None
        session_id = getattr(self, "_session_id", "")

        broker = _make_broker(self._as_of, session_id)
        if not broker.is_configured():
            return json.dumps({
                "status": "error",
                "error": "Alpaca API credentials not configured",
            })

        # Replay mode: fill against the historical broker directly. No mandate /
        # guard / confirmation — this is a simulation into a past date, not a live
        # order, so real-time side-effects (kill switch, market clock, active
        # artifact, human confirmation) are not applicable.
        if self._as_of:
            try:
                order = broker.submit_order(
                    symbol=symbol, qty=qty, side=side, order_type=order_type,
                    limit_price=limit_price, stop_price=stop_price,
                    time_in_force=time_in_force,
                    take_profit_price=take_profit_price,
                    stop_loss_price=stop_loss_price,
                    stop_loss_limit_price=stop_loss_limit_price,
                )
                account = broker.get_account()
                positions = broker.get_positions()
                return json.dumps({
                    "status": "replay_filled",
                    "order": order,
                    "account": {
                        "cash": account.cash,
                        "equity": account.equity,
                        "portfolio_value": account.portfolio_value,
                    },
                    "positions": [
                        {
                            "symbol": p.symbol, "qty": p.qty,
                            "market_value": round(p.market_value, 2),
                            "unrealized_pl": round(p.unrealized_pl, 2),
                        }
                        for p in positions
                    ],
                }, indent=2)
            except Exception as exc:
                logger.error("Replay order failed: %s", exc)
                return json.dumps({"status": "error", "error": str(exc)})

        mandate = TradingMandate.load()
        guard = OrderGuard(mandate=mandate, broker=broker)

        # A36: a market order carries no limit price, and the old fallback here
        # was a hardcoded `qty * 100.0` -- a fictional $100/share that made the
        # OrderGuard notional cap meaningless for any market order. Use a real
        # reference price when the symbol is already held (broker reports
        # current_price on the position); otherwise pass 0 and let OrderGuard
        # fail closed (Vibe-Trading's "DENY when unpriceable"). A market entry
        # into a fresh name now needs a limit_price to clear the cap.
        if limit_price:
            estimated_value = qty * limit_price
        else:
            ref_price = 0.0
            try:
                for _p in broker.get_positions():
                    if _p.symbol == symbol and float(getattr(_p, "current_price", 0.0)) > 0:
                        ref_price = float(_p.current_price)
                        break
            except Exception:
                ref_price = 0.0
            estimated_value = qty * ref_price

        # C8: soft-limit sizing (opt-in via VINU_AGENT_GUARD_SOFT_LIMITS).
        # Ask for a [0,1] scalar that shrinks the order to *fit* the soft
        # quantitative limits, apply it, and submit the smaller order --
        # instead of the order being hard-rejected for breaching one. The
        # hard gates still run in guard.check() below on the scaled qty.
        size_scaled = None
        from ..broker.order_guard import SOFT_LIMITS_ENABLED

        if SOFT_LIMITS_ENABLED and not reduce_only and qty > 0:
            mult = guard.position_size_multiplier(
                symbol, side, qty, price=(limit_price or None), estimated_value=estimated_value,
            )
            if mult.multiplier < 1.0:
                new_qty = int(qty * mult.multiplier)
                if new_qty <= 0:
                    AuditLogger.log("order_rejected", {
                        "symbol": symbol, "side": side, "qty": qty,
                        "reason": f"risk multiplier {mult.multiplier:.3f} ({mult.binding}) scales the order to zero",
                        "reason_code": "risk_multiplier_zero",
                    }, session_id=session_id, symbol=symbol)
                    return json.dumps({
                        "status": "rejected",
                        "reason": f"risk size multiplier {mult.multiplier:.3f} (binding: {mult.binding}) "
                                  f"would scale this order below one share",
                        "reason_code": "risk_multiplier_zero",
                        "multipliers": mult.components,
                    })
                size_scaled = {
                    "from_qty": qty, "to_qty": new_qty,
                    "multiplier": round(mult.multiplier, 4), "binding": mult.binding,
                    "components": {k: round(v, 4) for k, v in mult.components.items()},
                }
                AuditLogger.log(
                    "order_size_scaled", size_scaled | {"symbol": symbol, "side": side},
                    session_id=session_id, symbol=symbol,
                )
                qty = new_qty
                estimated_value = (qty * limit_price) if limit_price else (
                    estimated_value * (new_qty / size_scaled["from_qty"]) if size_scaled["from_qty"] else estimated_value
                )

        result = guard.check(
            symbol, side, qty, price=(limit_price or None),
            estimated_value=estimated_value, reduce_only=reduce_only,
        )
        # C17: a PAUSE_FOR_REAUTH result is not a flat reject -- the order is
        # quantitatively near a hard limit but not over it. Route it to the
        # same confirmation flow as `require_confirmation`, but with a
        # message that says *why* it's being held, and a distinct
        # `reason_code` so the caller/audit can tell it apart from an
        # unconditional confirmation pause.
        needs_reauth = getattr(result, "needs_reauth", False)
        if not result and not needs_reauth:
            AuditLogger.log("order_rejected", {
                "symbol": symbol, "side": side, "qty": qty,
                "reason": result.reason,
                "reason_code": getattr(getattr(result, "code", None), "value", None),
            }, session_id=session_id, symbol=symbol)
            return json.dumps({
                "status": "rejected",
                "reason": result.reason,
                "reason_code": getattr(getattr(result, "code", None), "value", None),
                "mandate": mandate.to_dict(),
            })

        if needs_reauth or mandate.require_confirmation:
            AuditLogger.log("order_pending_confirmation", {
                "symbol": symbol, "side": side, "qty": qty,
                "order_type": order_type, "estimated_value": estimated_value,
                "reason_code": getattr(getattr(result, "code", None), "value", None) if needs_reauth else None,
            }, session_id=session_id, symbol=symbol)
            return json.dumps({
                "status": "pending_confirmation",
                "message": (
                    result.reason if needs_reauth
                    else "Awaiting user confirmation before executing order"
                ),
                "reason_code": getattr(getattr(result, "code", None), "value", None) if needs_reauth else None,
                "proposal": {
                    "symbol": symbol,
                    "side": side,
                    "qty": qty,
                    "order_type": order_type,
                    "limit_price": limit_price,
                    "stop_price": stop_price,
                    "take_profit_price": take_profit_price,
                    "stop_loss_price": stop_loss_price,
                    "estimated_value": estimated_value,
                },
                "size_scaled": size_scaled,
                "mandate": mandate.to_dict(),
            })

        try:
            AuditLogger.log("order_executing", {
                "symbol": symbol, "side": side, "qty": qty,
                "order_type": order_type, "estimated_value": estimated_value,
                "take_profit_price": take_profit_price, "stop_loss_price": stop_loss_price,
                "client_order_id": client_order_id,
            }, session_id=session_id, symbol=symbol)

            from ..broker.kill_switch import kill_switch_lock

            # pre_approve()'s fresh re-check (including kill switch) and the
            # actual order submission are both inside this lock --
            # halt_trading() acquires the same lock, so a halt issued here
            # either lands before this block starts or after it finishes,
            # never in the gap between the check and the real order. Before
            # this fix, pre_approve()'s result was also silently discarded --
            # a halt engaged between the earlier guard.check() (line ~141)
            # and this point would correctly report not-allowed here, but
            # the order was submitted anyway.
            with kill_switch_lock():
                pre_result = guard.pre_approve(symbol, side, qty, reduce_only=reduce_only)
                if not pre_result:
                    AuditLogger.log("order_rejected", {
                        "symbol": symbol, "side": side, "qty": qty,
                        "reason": pre_result.reason,
                    }, session_id=session_id, symbol=symbol)
                    return json.dumps({
                        "status": "rejected",
                        "reason": pre_result.reason,
                        "mandate": mandate.to_dict(),
                    })
                order = broker.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    order_type=order_type,
                    limit_price=limit_price,
                    stop_price=stop_price,
                    time_in_force=time_in_force,
                    take_profit_price=take_profit_price,
                    stop_loss_price=stop_loss_price,
                    stop_loss_limit_price=stop_loss_limit_price,
                    client_order_id=client_order_id,
                )
            # The one entry that actually answers "what order did this
            # session/symbol produce" -- before this, "order_executing" was
            # logged pre-submission but the broker's real order id (the id
            # a fill/cancel/position would later reference) was never
            # written anywhere in the audit trail at all.
            AuditLogger.log("order_placed", {
                "symbol": symbol, "side": side, "qty": qty,
                "order_id": order.get("id", ""), "client_order_id": client_order_id,
                "broker_status": order.get("status", ""),
            }, session_id=session_id, symbol=symbol)
            return json.dumps({
                "status": "submitted",
                "order_id": order.get("id", ""),
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "size_scaled": size_scaled,
                "type": order_type,
                # Was a duplicate "status" key before this fix -- silently
                # overwrote "submitted" with the broker's raw order status
                # (e.g. "accepted"/"filled"/"pending_new"), so callers
                # checking status == "submitted" to confirm a new order was
                # created never actually saw that value once a real order
                # came back. Broker's own status is real, separate
                # information -- kept, under its own key.
                "broker_status": order.get("status", ""),
            }, indent=2)

        except Exception as exc:
            AuditLogger.log("order_error", {
                "symbol": symbol, "side": side, "qty": qty, "error": str(exc),
            }, session_id=session_id, symbol=symbol)
            logger.error("Order submission failed: %s", exc)
            return json.dumps({"status": "error", "error": str(exc)})


class CancelOrderTool(BaseTool):
    name = "cancel_order"
    description = "Cancel an open order by its order ID"
    parameters = {
        "type": "object",
        "properties": {
            "order_id": {"type": "string", "description": "The order ID to cancel"},
        },
        "required": ["order_id"],
    }
    is_readonly = False
    _as_of: str | None = None
    _session_id: str = ""

    def execute(self, **kwargs) -> str:
        order_id = kwargs["order_id"]
        broker = _make_broker(self._as_of, getattr(self, "_session_id", ""))

        if not broker.is_configured():
            return json.dumps({
                "status": "error",
                "error": "Alpaca API credentials not configured",
            })

        try:
            result = broker.cancel_order(order_id)
            return json.dumps({
                "status": "cancelled",
                "order_id": order_id,
            })
        except Exception as exc:
            return json.dumps({"status": "error", "error": str(exc)})
