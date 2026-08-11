"""Read-only Alpaca broker connector — portfolio, positions, orders."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from typing import Any

import requests

logger = logging.getLogger(__name__)

ALPACA_PAPER_URL = "https://paper-api.alpaca.markets"
ALPACA_LIVE_URL = "https://api.alpaca.markets"

API_KEY = os.environ.get("ALPACA_API_KEY", "")
API_SECRET = os.environ.get("ALPACA_API_SECRET", "")
USE_PAPER = os.environ.get("ALPACA_PAPER", "true").lower() == "true"

BASE_URL = ALPACA_PAPER_URL if USE_PAPER else ALPACA_LIVE_URL

# How many recent closed orders debrief.py's fill-based close detection pulls
# per poll (broker/debrief.py::PositionCloseDetector). Needs to comfortably
# exceed the number of fills expected between two consecutive polls -- too
# low and a fill can scroll off the page before it's ever seen, silently
# skipping that close's evidence write (same shape as any limit-based poll).
DEBRIEF_ORDER_LOOKBACK = int(os.environ.get("VINU_DEBRIEF_ORDER_LOOKBACK", "50"))


@dataclass
class Account:
    account_id: str
    status: str
    currency: str
    cash: float
    portfolio_value: float
    buying_power: float
    equity: float
    daytrade_count: int
    pattern_day_trader: bool

    @classmethod
    def from_api(cls, data: dict) -> Account:
        return cls(
            account_id=data.get("id", ""),
            status=data.get("status", ""),
            currency=data.get("currency", "USD"),
            cash=float(data.get("cash", 0)),
            portfolio_value=float(data.get("portfolio_value", 0)),
            buying_power=float(data.get("buying_power", 0)),
            equity=float(data.get("equity", 0)),
            daytrade_count=int(data.get("daytrade_count", 0)),
            pattern_day_trader=bool(data.get("pattern_day_trader", False)),
        )


@dataclass
class Position:
    symbol: str
    qty: float
    market_value: float
    cost_basis: float
    unrealized_pl: float
    unrealized_plpc: float
    current_price: float
    avg_entry_price: float

    @classmethod
    def from_api(cls, data: dict) -> Position:
        return cls(
            symbol=data.get("symbol", ""),
            qty=float(data.get("qty", 0)),
            market_value=float(data.get("market_value", 0)),
            cost_basis=float(data.get("cost_basis", 0)),
            unrealized_pl=float(data.get("unrealized_pl", 0)),
            unrealized_plpc=float(data.get("unrealized_plpc", 0)),
            current_price=float(data.get("current_price", 0)),
            avg_entry_price=float(data.get("avg_entry_price", 0)),
        )


@dataclass
class Order:
    order_id: str
    symbol: str
    side: str
    type: str
    status: str
    qty: float
    filled_qty: float
    limit_price: float | None
    stop_price: float | None
    created_at: str
    updated_at: str
    # Alpaca's real fill price for this order once status == "filled" -- the
    # order-level fields above never carried this, so anything keying off a
    # fill's actual price (e.g. debrief.py's close detection) had no way to
    # get it except a separate current-price lookup.
    filled_avg_price: float | None = None

    @classmethod
    def from_api(cls, data: dict) -> Order:
        return cls(
            order_id=data.get("id", ""),
            symbol=data.get("symbol", ""),
            side=data.get("side", ""),
            type=data.get("type", ""),
            status=data.get("status", ""),
            qty=float(data.get("qty", 0)),
            filled_qty=float(data.get("filled_qty", 0)),
            limit_price=float(data["limit_price"]) if data.get("limit_price") else None,
            stop_price=float(data["stop_price"]) if data.get("stop_price") else None,
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            filled_avg_price=float(data["filled_avg_price"]) if data.get("filled_avg_price") else None,
        )


class AlpacaBroker:
    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "APCA-API-KEY-ID": API_KEY,
            "APCA-API-SECRET-KEY": API_SECRET,
        })

    def is_configured(self) -> bool:
        return bool(API_KEY and API_SECRET)

    def _get(self, path: str) -> dict:
        resp = self._session.get(f"{BASE_URL}{path}", timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _delete(self, path: str) -> dict:
        resp = self._session.delete(f"{BASE_URL}{path}", timeout=30)
        resp.raise_for_status()
        return resp.json() if resp.text else {}

    def _post(self, path: str, payload: dict) -> dict:
        resp = self._session.post(f"{BASE_URL}{path}", json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _patch(self, path: str, payload: dict) -> dict:
        resp = self._session.patch(f"{BASE_URL}{path}", json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_account(self) -> Account:
        data = self._get("/v2/account")
        return Account.from_api(data)

    def get_positions(self) -> list[Position]:
        data = self._get("/v2/positions")
        return [Position.from_api(p) for p in data]

    def get_orders(self, status: str = "open", limit: int = 50) -> list[Order]:
        data = self._get(f"/v2/orders?status={status}&limit={limit}")
        return [Order.from_api(o) for o in data]

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
    ) -> dict:
        """Submit an order. Passing take_profit_price and/or stop_loss_price
        attaches Alpaca's native bracket-order legs (order_class "bracket" when
        both are given, "oto" when only one is — see Alpaca's order-class docs),
        so the exit is a real resting order placed at entry time, not something
        that has to be watched and submitted manually later.
        """
        payload: dict[str, object] = {
            "symbol": symbol.upper(),
            "qty": str(qty),
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
        }
        if limit_price is not None:
            payload["limit_price"] = str(limit_price)
        if stop_price is not None:
            payload["stop_price"] = str(stop_price)

        if take_profit_price is not None and stop_loss_price is not None:
            payload["order_class"] = "bracket"
            payload["take_profit"] = {"limit_price": str(take_profit_price)}
            payload["stop_loss"] = self._stop_loss_leg(stop_loss_price, stop_loss_limit_price)
        elif take_profit_price is not None:
            payload["order_class"] = "oto"
            payload["take_profit"] = {"limit_price": str(take_profit_price)}
        elif stop_loss_price is not None:
            payload["order_class"] = "oto"
            payload["stop_loss"] = self._stop_loss_leg(stop_loss_price, stop_loss_limit_price)

        return self._post("/v2/orders", payload)

    @staticmethod
    def _stop_loss_leg(stop_price: float, limit_price: float | None) -> dict[str, str]:
        leg: dict[str, str] = {"stop_price": str(stop_price)}
        if limit_price is not None:
            leg["limit_price"] = str(limit_price)
        return leg

    def get_clock(self) -> dict:
        """Alpaca's market clock — {is_open, timestamp, next_open, next_close}."""
        return self._get("/v2/clock")

    def cancel_order(self, order_id: str) -> dict:
        return self._delete(f"/v2/orders/{order_id}")

    def replace_order(
        self,
        order_id: str,
        qty: float | None = None,
        limit_price: float | None = None,
        stop_price: float | None = None,
    ) -> dict:
        payload: dict[str, object] = {}
        if qty is not None:
            payload["qty"] = str(qty)
        if limit_price is not None:
            payload["limit_price"] = str(limit_price)
        if stop_price is not None:
            payload["stop_price"] = str(stop_price)
        return self._patch(f"/v2/orders/{order_id}", payload)
