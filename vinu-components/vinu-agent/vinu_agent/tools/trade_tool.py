import json
import logging

from ..agent.tools import BaseTool
from ..broker.alpaca import AlpacaBroker
from ..broker.mandate import TradingMandate
from ..broker.order_guard import OrderGuard

logger = logging.getLogger(__name__)


class TradeTool(BaseTool):
    name = "submit_order"
    description = "Submit a trade order to Alpaca paper trading. Every order is validated against the trading mandate before execution."
    parameters = {
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
    }
    is_readonly = False

    def execute(self, **kwargs) -> str:
        symbol = kwargs["symbol"].upper()
        qty = float(kwargs["qty"])
        side = kwargs["side"]
        order_type = kwargs.get("order_type", "market")
        limit_price = kwargs.get("limit_price")
        stop_price = kwargs.get("stop_price")
        time_in_force = kwargs.get("time_in_force", "day")

        broker = AlpacaBroker()
        if not broker.is_configured():
            return json.dumps({
                "status": "error",
                "error": "Alpaca API credentials not configured",
            })

        mandate = TradingMandate.load()
        guard = OrderGuard(mandate=mandate, broker=broker)

        estimated_value = qty * (limit_price or 0.0) if limit_price else qty * 100.0

        result = guard.check(symbol, side, qty, estimated_value=estimated_value)
        if not result:
            return json.dumps({
                "status": "rejected",
                "reason": result.reason,
                "mandate": mandate.to_dict(),
            })

        if mandate.require_confirmation:
            return json.dumps({
                "status": "pending_confirmation",
                "message": "Awaiting user confirmation before executing order",
                "proposal": {
                    "symbol": symbol,
                    "side": side,
                    "qty": qty,
                    "order_type": order_type,
                    "limit_price": limit_price,
                    "stop_price": stop_price,
                    "estimated_value": estimated_value,
                },
                "mandate": mandate.to_dict(),
            })

        try:
            guard.pre_approve(symbol, side, qty)
            order = broker.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                order_type=order_type,
                limit_price=limit_price,
                stop_price=stop_price,
                time_in_force=time_in_force,
            )
            return json.dumps({
                "status": "submitted",
                "order_id": order.get("id", ""),
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "type": order_type,
                "status": order.get("status", ""),
            }, indent=2)

        except Exception as exc:
            logger.error("Order submission failed: %s", exc)
            return json.dumps({"status": "error", "error": str(exc)})


class CancelOrderTool(BaseTool):
    name = "cancel_order"
    description = "Cancel an open order by its order ID"
    parameters = {
        "order_id": {"type": "string", "description": "The order ID to cancel"},
    }
    is_readonly = False

    def execute(self, **kwargs) -> str:
        order_id = kwargs["order_id"]
        broker = AlpacaBroker()

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
