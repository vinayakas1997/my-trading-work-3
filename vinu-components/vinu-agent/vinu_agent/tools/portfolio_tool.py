import json
import logging

from ..broker.alpaca import AlpacaBroker
from ..agent.tools import BaseTool

logger = logging.getLogger(__name__)


class PortfolioTool(BaseTool):
    name = "get_portfolio"
    description = "Fetch the current Alpaca paper trading portfolio: account summary, open positions, and pending orders"
    parameters = {
        "section": {
            "type": "string",
            "description": "Which section to fetch: account, positions, orders, or all (default: all)",
            "enum": ["account", "positions", "orders", "all"],
        },
    }
    is_readonly = True

    def execute(self, **kwargs) -> str:
        section = kwargs.get("section", "all")
        broker = AlpacaBroker()

        if not broker.is_configured():
            return json.dumps({
                "status": "error",
                "error": "Alpaca API credentials not configured. Set ALPACA_API_KEY and ALPACA_API_SECRET environment variables.",
            })

        try:
            result: dict[str, object] = {"status": "ok"}

            if section in ("account", "all"):
                account = broker.get_account()
                result["account"] = {
                    "status": account.status,
                    "currency": account.currency,
                    "cash": account.cash,
                    "portfolio_value": account.portfolio_value,
                    "buying_power": account.buying_power,
                    "equity": account.equity,
                    "daytrade_count": account.daytrade_count,
                    "pattern_day_trader": account.pattern_day_trader,
                }

            if section in ("positions", "all"):
                positions = broker.get_positions()
                result["positions"] = [
                    {
                        "symbol": p.symbol,
                        "qty": p.qty,
                        "market_value": p.market_value,
                        "cost_basis": p.cost_basis,
                        "unrealized_pl": p.unrealized_pl,
                        "unrealized_plpc": round(p.unrealized_plpc * 100, 2),
                        "current_price": p.current_price,
                        "avg_entry_price": p.avg_entry_price,
                    }
                    for p in positions
                ]
                result["positions_summary"] = {
                    "count": len(positions),
                    "total_market_value": sum(p.market_value for p in positions),
                    "total_unrealized_pl": sum(p.unrealized_pl for p in positions),
                }

            if section in ("orders", "all"):
                orders = broker.get_orders()
                result["orders"] = [
                    {
                        "order_id": o.order_id,
                        "symbol": o.symbol,
                        "side": o.side,
                        "type": o.type,
                        "status": o.status,
                        "qty": o.qty,
                        "filled_qty": o.filled_qty,
                        "limit_price": o.limit_price,
                        "stop_price": o.stop_price,
                        "created_at": o.created_at,
                    }
                    for o in orders
                ]

            return json.dumps(result, indent=2, default=str)

        except Exception as exc:
            logger.error("Portfolio fetch failed: %s", exc)
            return json.dumps({"status": "error", "error": str(exc)})
