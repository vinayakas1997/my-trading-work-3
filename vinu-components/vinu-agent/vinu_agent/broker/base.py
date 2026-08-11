"""Broker abstraction (`component-consolidation-plan.md` follow-up,
raised alongside it): a `Broker` Protocol formalizing the interface
`AlpacaBroker` (`broker/alpaca.py`) already exposes, and
`HistoricalFillBroker` (`broker/historical_broker.py`) already informally
matches -- its own docstring already calls it a "drop-in
AlpacaBroker-compatible interface." This module makes that contract
explicit; `broker/factory.py` is the real extension point for a second
REAL broker provider (a live/paper account with a different broker).

Deliberately distinct from `HistoricalFillBroker`: that's a synthetic
replay broker always used for backtest sessions (selected by `as_of`
being set), independent of which real provider is configured -- not a
"provider" choice itself, so it's not part of `broker/factory.py`'s
registry.

`replace_order` is intentionally NOT part of this Protocol: confirmed by
grep, nothing outside `alpaca.py`'s own definition and its own test calls
it, and `HistoricalFillBroker` never implemented it -- it's not actually
part of the shared contract every broker needs to honor today. Add it
here (and to every implementation) if a real caller needs it later.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .alpaca import Account, Order, Position


@runtime_checkable
class Broker(Protocol):
    def is_configured(self) -> bool: ...

    def get_account(self) -> Account: ...

    def get_positions(self) -> list[Position]: ...

    def get_orders(self, status: str = "open", limit: int = 50) -> list[Order]: ...

    def get_clock(self) -> dict: ...

    def submit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = "market",
        limit_price: float | None = None,
        stop_price: float | None = None,
        time_in_force: str = "day",
        take_profit_price: float | None = None,
        stop_loss_price: float | None = None,
        stop_loss_limit_price: float | None = None,
    ) -> dict: ...

    def cancel_order(self, order_id: str) -> dict: ...
