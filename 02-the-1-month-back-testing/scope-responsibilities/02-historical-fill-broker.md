---
name: historical-fill-broker
component: vinu-agent
status: not-started
---

# Item 2 — Historical-Fill Broker Stub

## What this is

A drop-in replacement for `AlpacaBroker` that a replay session's
`TradeTool` uses instead of the real one. It answers "if the agent
decided to buy 10 shares of AAPL on this historical date, what would it
actually have filled at, and what does the resulting paper portfolio look
like" — using real historical OHLCV, not Alpaca's real live/paper account
(which cannot execute an order "in the past").

## Why not reuse `AlpacaBroker` with a fake date

Alpaca's REST API has no concept of "submit this order as of a past
date" — every endpoint operates on the account's real current state.
There is no way to make `POST /v2/orders` believe it's July 2026. A
separate implementation is required, not a parameter change.

## Design — mirror `AlpacaBroker`'s public interface exactly

`vinu_agent/tools/trade_tool.py` calls `AlpacaBroker()` and then methods
like `.get_account()`, `.get_positions()`, `.submit_order(...)`,
`.get_clock()`. The replacement must expose the **same method
signatures** so `TradeTool` doesn't need to branch its own logic — only
which broker class it instantiates changes.

New file: `vinu_agent/broker/historical_broker.py`

```python
class HistoricalFillBroker:
    """AlpacaBroker-compatible interface, backed by historical OHLCV
    instead of a real account. One instance per replay session,
    persisted for the session's lifetime (not re-created per message) so
    positions/cash accumulate across the simulated month."""

    def __init__(self, as_of: str, initial_cash: float = 100_000.0,
                 price_client=None):
        ...

    def get_account(self) -> Account: ...       # cash/equity from internal ledger
    def get_positions(self) -> list[Position]: ...
    def get_orders(self, status="open", limit=50) -> list[Order]: ...
    def submit_order(self, symbol, qty, side, order_type="market", ...) -> dict: ...
    def get_clock(self) -> dict: ...             # derived from as_of + market calendar, not real time
    def cancel_order(self, order_id) -> dict: ...
```

## Fill logic — the part that must be correct

- **No same-bar fills.** An order "submitted" at `as_of` must fill at the
  **next** available bar's open after `as_of`, mirroring
  `WeightSimulator`'s `ws_aligned.shift(1)` discipline
  (`vinu-simulator/engine/simulator.py:100-106`) — the comment there
  explains exactly why: filling at the same price that triggered the
  decision is look-ahead bias. Reuse this reasoning; don't re-derive a
  different rule.
- **Reuse `vinu_simulator.engine.costs`** (`AlmgrenChrissCostModel` or
  `FlatCostModel`) for slippage/transaction cost instead of a flat
  0%-cost assumption — a replay with free execution will overstate P&L.
  Import directly from `vinu_simulator.engine.costs`; do not copy the
  math into `vinu-agent`.
- **Price source**: pull historical bars from `vinu-stock-price`'s
  existing API (same one `vinu_agent/tools/stock_price_tool.py` already
  calls), clamped to `as_of` via item 1's guard — the broker is itself
  effectively a tool consumer, subject to the same no-lookahead rule.
- **Market-closed handling**: `get_clock()` must return `is_open: false`
  correctly for weekends/holidays within the replay window (reuse
  whatever trading-calendar logic `vinu-stock-price` or `vinu-simulator`
  already has — do not hand-roll a new one that might miss a holiday and
  silently "fill" on a day the market was actually closed).

## Persistence

- One `HistoricalFillBroker` instance must live for the **entire replay
  session** (all simulated days), not be re-created fresh per message —
  otherwise positions and cash reset every day and P&L can never
  accumulate. Store it keyed by `session_id` in the same place
  `AgentService._active_loops` or similar per-session state already
  lives (`session/service.py`) — check the existing per-session state
  pattern before inventing a new one.
- Record every simulated fill to a running trade log (symbol, side, qty,
  fill price, fill date, simulated cash/equity after) — item 4's P&L
  report reads this log directly; don't make item 4 reverse-engineer
  trades from Alpaca-shaped `Order` objects alone.

## Files to touch

- New: `vinu_agent/broker/historical_broker.py`
- `vinu_agent/tools/trade_tool.py` (lines 69, 162): replace the inline
  `broker = AlpacaBroker()` with a small factory check:
  ```python
  broker = HistoricalFillBroker(self._as_of, ...) if self._as_of else AlpacaBroker()
  ```
  (exact seam depends on how item 1 wires `_as_of` onto this tool —
  coordinate with that item, don't duplicate the attribute-injection
  logic).
- Reference only: `vinu-simulator/vinu_simulator/engine/simulator.py`
  (fill/T+1 discipline), `vinu-simulator/vinu_simulator/engine/costs.py`
  (cost models), `vinu_agent/broker/alpaca.py` (the interface being
  mirrored).

## Expected output / how to verify

- Unit-level: feed `HistoricalFillBroker` a known historical price series
  (e.g. AAPL around a date with a known move) and a scripted sequence of
  buy/sell calls; confirm fills land at the next bar's open (not the
  decision-bar close), confirm cash/equity math is internally consistent
  (cash + holdings*price == equity, every step).
- Confirm `get_account()` starts at the configured initial cash
  (recommend $100k, matching the real paper account's balance so replay
  and live results are comparable) and evolves correctly after fills.
- Confirm `get_clock()` correctly reports `is_open: false` on a weekend
  date inside the replay window.
- Confirm a live (non-replay) session is completely unaffected — `TradeTool`
  still instantiates `AlpacaBroker()` exactly as before when `_as_of` is
  unset.
