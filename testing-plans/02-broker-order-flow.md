# 02 — Broker & Order Flow Test Plan

> **Status**: ⏳ Placeholder — will be detailed after Phase 1 is complete.

## Objective

Test the order placement pipeline: from agent decision → order guard checks → kill switch → confirmation dialog → Alpaca API call → order status tracking.

---

## Scope (To Be Detailed)

### Tests to Cover

1. **Portfolio Tool (Read-Only)**
   - `get_portfolio` with section=account/positions/orders/all
   - Verify returned data matches Alpaca API output
   - Error handling when Alpaca keys missing

2. **Order Guard**
   - Blocked ticker → rejection
   - Allowed ticker → pass
   - Kill switch active → rejection
   - Kill switch inactive → pass
   - Daily order limit → rejection after N orders
   - `max_order_value` exceeded → rejection
   - Short selling disabled → rejection on sell

3. **Kill Switch**
   - `halt_trading()` → `/tmp/vinu-trading-halt` exists
   - `resume_trading()` → file removed
   - `is_trading_halted()` correct state

4. **Mandate**
   - Load from `~/.vinu/mandate.yaml`
   - Default values when file missing
   - Field update via `mandate set`

5. **Confirmation Flow**
   - `request_confirmation()` with timeout
   - `resolve_confirmation()` approve/deny
   - Timeout behavior

6. **Order Placement Tool**
   - `submit_order` with guard passing → order placed
   - `submit_order` with guard failing → rejected with reason
   - `cancel_order` → order cancelled
   - `replace_order` → order modified

7. **End-to-End**
   - Agent decides to trade → guard check → confirmation → order placed
   - Agent decides to trade → guard blocks → rejection returned

---

## Dependencies

- Alpaca paper trading account configured
- `~/.vinu/mandate.yaml` created
- Kill switch testable via filesystem

---

## Success Criteria

- All order guard rules enforced correctly
- Confirmation flow completes or times out properly
- Orders placed via Alpaca paper API are visible in Alpaca dashboard
- Agent correctly reports order status back to user
