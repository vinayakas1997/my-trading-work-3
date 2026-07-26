from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal


@dataclass
class Position:
    position_id: str
    symbol: str
    side: Literal["long", "short"]
    qty: float
    avg_entry: float
    realized_pnl: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None
    opened_at: str = ""
    updated_at: str = ""
    closed_at: str | None = None
    is_open: bool = True
    # Links back to the Phase 4 frozen TradePlan artifact that authored this position, if
    # any -- empty for positions opened outside the Phase 6 trade-plan orchestrator. Phase 7's
    # feedback loop needs this to know which forecast to score when the position closes.
    artifact_id: str = ""

    def current_value(self, current_price: float) -> float:
        return self.qty * current_price * (1 if self.side == "long" else -1)

    def unrealized_pnl(self, current_price: float) -> float:
        if self.side == "long":
            return (current_price - self.avg_entry) * self.qty
        return (self.avg_entry - current_price) * self.qty

    def total_pnl(self, current_price: float) -> float:
        return self.realized_pnl + self.unrealized_pnl(current_price)

    def pnl_pct(self, current_price: float) -> float:
        cost = self.avg_entry * self.qty
        if cost <= 0:
            return 0.0
        return self.unrealized_pnl(current_price) / cost


@dataclass
class Fill:
    fill_id: str
    symbol: str
    side: Literal["buy", "sell"]
    qty: float
    price: float
    filled_at: str
    position_id: str | None = None
    commission: float = 0.0


OPEN_POSITIONS_TABLE = "open_positions"
CLOSED_POSITIONS_TABLE = "closed_positions"
FILLS_TABLE = "fills"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
