"""Historical-fill broker — drop-in AlpacaBroker-compatible interface for replay sessions.

Answers "if the agent decided to buy 10 AAPL on this historical date, what would it
fill at and what happens to the paper portfolio" using real historical OHLCV, never
Alpaca's live/paper account (which cannot execute an order "in the past").

Replay discipline (mirrors vinu-simulator's WeightSimulator T+1 rule):
  - An order decided on day D (as_of) fills at the OPEN of the next trading day
    (D+1). Never the same price that produced the decision — that is look-ahead bias.
  - Execution cost uses vinu_simulator.engine.costs.FlatCostModel-equivalent math
    (cost_pct + slippage_pct), not free execution.

State (cash, positions, trade ledger) is persisted per session_id so positions
accumulate across the whole replay month and survive message-to-message and
restart — one durable source of truth, not in-memory only.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from .alpaca import Account, Order, Position

logger = logging.getLogger(__name__)

DEFAULT_INITIAL_CASH = 100_000.0


def _iso_to_dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc)


def _iso_now(iso: str) -> datetime:
    return _iso_to_dt(iso)


class _FlatCost:
    """FlatCostModel-equivalent (cost_pct + slippage_pct). Mirrors
    vinu_simulator.engine.costs.FlatCostModel so replay isn't free execution."""

    def __init__(self, cost_pct=0.001, slippage_pct=0.0005):
        self.cost_pct = cost_pct
        self.slippage_pct = slippage_pct

    def buy_cost(self, price, shares):
        eff = price * (1 + self.slippage_pct)
        return eff * shares * (1 + self.cost_pct)

    def sell_proceeds(self, price, shares):
        eff = price * (1 - self.slippage_pct)
        return max(0.0, eff * shares * (1 - self.cost_pct))


class HistoricalFillBroker:
    def __init__(
        self,
        as_of: str,
        initial_cash: float = DEFAULT_INITIAL_CASH,
        stock_api_url: str | None = None,
        state_path: str | None = None,
    ) -> None:
        import os as _os
        self._as_of = as_of
        self._initial_cash = initial_cash
        self._stock_api_url = stock_api_url or _os.environ.get(
            "VINU_STOCK_PRICE_API_URL", "http://localhost:8081"
        )
        self._state_path = state_path
        self._cost = _FlatCost()

    # --- AlpacaBroker-compatible interface -----------------------------------

    def is_configured(self) -> bool:
        return True

    def get_account(self) -> Account:
        state = self._load_state()
        equity = self._equity(state)
        return Account(
            account_id="replay-account",
            status="ACTIVE",
            currency="USD",
            cash=round(state["cash"], 2),
            portfolio_value=round(equity, 2),
            buying_power=round(state["cash"], 2),
            equity=round(equity, 2),
            daytrade_count=0,
            pattern_day_trader=False,
        )

    def get_positions(self) -> list[Position]:
        state = self._load_state()
        out = []
        for sym, pos in state["positions"].items():
            qty = pos["qty"]
            if abs(qty) < 1e-9:
                continue
            last = pos.get("last_close") or 0.0
            cb = pos.get("cost_basis", 0.0)
            out.append(Position(
                symbol=sym, qty=qty, market_value=qty * last,
                cost_basis=cb, unrealized_pl=qty * last - cb,
                unrealized_plpc=(qty * last / cb - 1.0) if cb else 0.0,
                current_price=last, avg_entry_price=pos.get("avg_entry", 0.0),
            ))
        return out

    def get_orders(self, status="open", limit=50) -> list[Order]:
        state = self._load_state()
        rows = state["orders"][-limit:]
        out = []
        for o in rows:
            out.append(Order(
                order_id=o.get("id", ""), symbol=o.get("symbol", ""),
                side=o.get("side", ""), type=o.get("type", "market"),
                status=o.get("status", ""), qty=o.get("qty", 0),
                filled_qty=o.get("filled_qty", 0),
                limit_price=o.get("limit_price"), stop_price=o.get("stop_price"),
                created_at=o.get("created_at", ""), updated_at=o.get("updated_at", ""),
            ))
        return out

    def get_clock(self) -> dict:
        d0 = _iso_now(self._as_of)
        return {
            "is_open": d0.weekday() < 5 and 13 <= d0.hour < 20,
            "timestamp": d0.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "next_open": d0.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "next_close": d0.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "replay": True,
        }

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
        symbol = symbol.upper()
        state = self._load_state()
        fill = self._next_open(symbol)
        if fill is None:
            return {"status": "error", "error": "no fillable next-day bar"}
        fill_price = float(fill["open"])
        fill_date = fill["date"]
        order_id = "replay-" + uuid.uuid4().hex[:12]
        created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if side == "buy":
            cost = self._cost.buy_cost(fill_price, qty)
            if state["cash"] < cost:
                return {"status": "rejected", "reason": "insufficient_cash",
                        "cash": round(state["cash"], 2), "cost": round(cost, 2)}
            state["cash"] -= cost
            pos = state["positions"].setdefault(symbol, {
                "qty": 0.0, "avg_entry": 0.0, "cost_basis": 0.0, "last_close": 0.0
            })
            pos["cost_basis"] += cost
            new_qty = pos["qty"] + qty
            pos["avg_entry"] = pos["cost_basis"] / new_qty if new_qty else 0.0
            pos["qty"] = new_qty
            pos["last_close"] = fill_price
        else:  # sell
            pos = state["positions"].get(symbol)
            held = pos["qty"] if pos else 0.0
            if held < qty:
                return {"status": "rejected", "reason": "insufficient_position",
                        "held": held, "qty": qty}
            proceeds = self._cost.sell_proceeds(fill_price, qty)
            state["cash"] += proceeds
            pos["qty"] = held - qty
            pos["cost_basis"] = pos["cost_basis"] * (pos["qty"] / held) if held else 0.0
            pos["last_close"] = fill_price
            if pos["qty"] <= 1e-9:
                state["positions"].pop(symbol, None)

        order = {
            "id": order_id, "symbol": symbol, "qty": qty, "side": side,
            "type": order_type, "status": "filled", "filled_qty": qty,
            "fill_price": round(fill_price, 2), "fill_date": fill_date,
            "limit_price": limit_price, "stop_price": stop_price,
            "created_at": created, "updated_at": created,
        }
        state["orders"].append(order)
        state["ledger"].append({
            "date": fill_date, "symbol": symbol, "side": side, "qty": qty,
            "fill_price": round(fill_price, 2), "cash_after": round(state["cash"], 2),
        })
        self._save_state(state)
        return order

    def cancel_order(self, order_id: str) -> dict:
        return {"status": "cancelled", "order_id": order_id}

    # --- persistence + pricing -------------------------------------------------

    def _state_path_arg(self) -> str:
        return self._state_path or ""

    def _load_state(self) -> dict:
        if not self._state_path:
            return self._fresh_state()
        p = Path(self._state_path)
        if p.exists():
            try:
                return json.loads(p.read_text("utf-8"))
            except Exception:
                logger.warning("Replay state unreadable, resetting: %s", self._state_path)
        return self._fresh_state()

    def _fresh_state(self) -> dict:
        return {
            "cash": self._initial_cash,
            "positions": {},
            "orders": [],
            "ledger": [],
        }

    def _save_state(self, state: dict) -> None:
        if not self._state_path:
            return
        p = Path(self._state_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, indent=2, default=str), "utf-8")

    def _equity(self, state: dict) -> float:
        total = state["cash"]
        for sym, pos in state["positions"].items():
            total += pos["qty"] * (pos.get("last_close") or 0.0)
        return total

    def _next_open(self, symbol: str) -> dict | None:
        """Next trading day's daily bar open after as_of (T+1 discipline)."""
        d0 = _iso_now(self._as_of)
        for i in range(1, 8):
            d = (d0 + timedelta(days=i)).date().isoformat()
            y, m, dd = (int(x) for x in d.split("-"))
            from_ts = int(datetime(y, m, dd, tzinfo=timezone.utc).timestamp())
            try:
                resp = httpx.get(
                    f"{self._stock_api_url}/stock/candles/{symbol}",
                    params={"interval": "1D", "from": from_ts, "to": from_ts + 86400},
                    timeout=30,
                )
                resp.raise_for_status()
                body = resp.json()
                rows = body.get("data") or []
                if rows and rows[0].get("open") not in (None, 0):
                    return {"open": float(rows[0]["open"]), "date": d}
            except Exception as e:
                logger.warning("Replay fill fetch failed %s on %s: %s", symbol, d, e)
                continue
        return None