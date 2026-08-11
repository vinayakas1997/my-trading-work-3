import json
import logging

from ..broker.factory import get_live_broker
from ..broker.historical_broker import HistoricalFillBroker
from ..agent.tools import BaseTool

logger = logging.getLogger(__name__)


def _make_broker(as_of: str | None, session_id: str = ""):
    if as_of:
        return HistoricalFillBroker(as_of=as_of, state_path=f"/data/replay_state/{session_id}.json")
    return get_live_broker()


class PortfolioTool(BaseTool):
    name = "get_portfolio"
    description = "Fetch the current Alpaca paper trading portfolio: account summary, open positions, and pending orders"
    parameters = {
        "type": "object",
        "properties": {
            "section": {
                "type": "string",
                "description": "Which section to fetch: account, positions, orders, or all (default: all)",
                "enum": ["account", "positions", "orders", "all"],
            },
        },
        "required": [],
    }
    is_readonly = True
    _as_of: str | None = None
    _session_id: str = ""

    def execute(self, **kwargs) -> str:
        section = kwargs.get("section", "all")
        broker = _make_broker(self._as_of, getattr(self, "_session_id", ""))

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
