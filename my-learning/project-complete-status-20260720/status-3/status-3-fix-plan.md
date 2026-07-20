# Analysis-to-Execution Gate — Fix Plan

Companion to [status-3.md](./status-3.md) (the assessment). This is the prioritized plan for closing
the gaps identified there. Two of the five findings can be fixed now, without a broker/paper-trading
account; three are correctly parked until that account exists, consistent with the existing standing
decision on `vinu-live`/broker-dependent work.

---

## Priority A — Gate `submit_order` on artifact/analysis status

**Why first:** this is the finding that actually answers the original question ("is anything stopping
an unresearched trade"). Everything else in this plan is secondary to closing this.

**What to do:**
1. `OrderGuard` currently takes only `mandate` and `broker`. Give it a way to resolve the strategy
   artifact behind an order — either pass an `artifact_id`/`symbol` lookup through
   `TradeTool.execute()` into `OrderGuard.check()`, or have `OrderGuard` query
   `vinu-research`'s `/research/artifacts` endpoint by symbol (same pattern
   `portfolio_comparison_tool.py` already uses: `params={"status": "ACTIVE,MONITORING,BENCHING"}`).
2. Add a new check in `OrderGuard.check()`, alongside the existing `max_position_pct` /
   `max_capital_utilization_pct` blocks: if no artifact exists for the symbol, or the artifact's
   status is not `ACTIVE`, return `GuardResult(False, ...)` with a clear reason — unless a mandate
   field explicitly opts out (see step 3).
3. Add `require_active_artifact: bool = True` to `TradingMandate` (same pattern as
   `max_capital_utilization_pct`) so this can be deliberately relaxed for manual/discretionary trades
   without weakening the default.
4. Follow the existing fail-open-with-warning pattern used by every other broker-dependent check in
   `OrderGuard` (`try/except ... logger.warning(...)`) if the research-api call fails — consistent
   with how `max_position_pct` already handles broker-call failures, so one unreachable service
   doesn't turn into a silent bypass in one direction or a hard outage in the other.

**Effort:** small-medium — one new check function, one new mandate field, one HTTP call using an
existing client pattern already present elsewhere in vinu-agent.

---

## Priority B — Compute the volume/volatility checklist item for real

**Why:** it currently renders as a real-looking `PENDING` row with no signal behind it — worse than
omitting it, because it implies a check is happening when it isn't.

**What to do:**
1. In `trade_plan_tool.py::_render_entry_checklist`, replace the hardcoded `PENDING` for item 4 with
   an actual computation: fetch recent volume/ATR (or similar) from the `features` payload already
   being pulled for the plan (or a small additional call to `vinu-tools`), compare against a trailing
   average, and render `MET`/`CAUTION` based on a real threshold — mirroring how item 5 (drawdown
   context) already does this from `angles.get("drawdown_deep_dive", ...)`.
2. If the needed volume/volatility series isn't already available in `features`, this needs a small
   client-side fetch to `vinu-stock-price` for recent bars before it can be computed — check that
   first before assuming a preset field already has it.

**Effort:** small — the pattern to follow (item 5) already exists in the same file.

---

## Parked — needs a broker/paper account to build and test meaningfully

### Priority C — Stop-loss enforcement via bracket orders
Add `order_class`/`stop_loss`/`take_profit` support to `vinu-agent/vinu_agent/broker/alpaca.py`, and
have `TradeTool` place the exit levels the trade plan already computes as an actual bracket order at
entry time, not just as text in a generated document.

### Priority D — Automated kill-switch triggers
Add a monitor (mirroring the `while True: cycle(); time.sleep(interval)` worker pattern already used
by `research-decay-scan`) that watches realized P&L/drawdown against a configured threshold and calls
`halt_trading()` automatically, instead of relying on a human to touch the flag file.

### Priority E — Market-hours / stale-data check
Call Alpaca's clock endpoint from `OrderGuard.check()` (or `TradeTool.execute()`) and reject orders
when the market is closed, alongside a staleness check on the price data used to size the order.

**All three require live Alpaca API access to implement against real behavior (clock endpoint,
bracket-order semantics, real fill/P&L data) — building them now would mean coding against
assumptions instead of verified API behavior. Sequenced here for when the paper-trading account
exists, per your existing direction on `vinu-live`.**

---

## Suggested order of work

1. **Priority A** (artifact/analysis gate) — the actual fix this review was about; do this first.
2. **Priority B** (real volume/volatility check) — small, self-contained, removes a false-signal stub
   while touching the same file.
3. **Priorities C/D/E** — stay parked until the paper-trading broker account exists.
