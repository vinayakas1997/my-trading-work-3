# Complete Outstanding-Gaps List — Consolidated

Companion to [status-2.md](../status-2/status-2.md), [status-2-fix-plan.md](../status-2/status-2-fix-plan.md),
[status-3.md](../status-3/status-3.md), and [status-3-fix-plan.md](../status-3/status-3-fix-plan.md).
Those documents were written incrementally as each review surfaced new gaps, and by design each one
only covered what it found *at that time* — none of them was ever meant to be the final word. This
document exists because that incremental format made it hard to answer one direct question in one
place: **everything, all at once, what's actually still missing across the whole project, full stop.**

Nothing new was investigated to produce this document — it consolidates findings already verified
against real code in status-2 and status-3. What's new here is only the framing: one ranked list,
with an explicit note on what's already fixed so this isn't mistaken for a project that's made no
progress.

---

## What's actually done (verified, tested, not aspirational)

Adjusted prices everywhere in the data path, cumulative multiple-testing correction (deflated Sharpe
computed from the true cumulative trial count per symbol, not reset per research run), the
BENCHING→ACTIVE promotion gate (deflated Sharpe + holdout + stress test, actually enforced server-side
now, not a no-op route), stress testing against historical crisis windows, ADV-based liquidity-aware
order sizing in the simulator, the capital-utilization guardrail (`max_capital_utilization_pct`), the
artifact/analysis gate on `submit_order` (`require_active_artifact` — an order is rejected unless the
symbol has a strategy artifact with status `ACTIVE`), and a real volume/volatility check in the trade
plan (replacing what used to be a hardcoded `PENDING` stub). All of this is backed by passing test
suites, not just written code.

---

## Everything still missing, ranked

### 1. Survivorship bias in the analysis universe — not fixed
`vinu-initial-analysis` only ever analyzes 7 mega-cap survivors (AAPL, AMZN, GOOGL, META, MSFT, NVDA,
TSLA). Every strategy "validated" against this universe has only ever seen names that survived and
thrived — there are no delisted, bankrupt, or round-tripped names in the sample. Flagged as High
severity in status-2.md §1.2; never assigned a fix priority; zero work done on it since.

### 2. Point-in-time data discipline — never audited
No confirmation exists either way that fundamentals or corporate-action data used anywhere in the
pipeline reflects only what would have actually been known at the time a signal fired (e.g., a
restated earnings figure used before it was actually public). Flagged as Medium severity in status-2.md
§1.3; not confirmed broken, not confirmed safe — an explicit audit has never been done.

### 3. `vinu-portfolio` circuit breaker duplicates the kill-switch path — not fixed
`vinu-portfolio/vinu_portfolio/circuit_breakers.py` reimplements the halt-file logic directly instead
of importing `vinu_agent.broker.kill_switch`. If the two implementations ever drift, a halt triggered
through one path may not be visible to the other. Surfaced in the status-2 architecture write-up;
never fixed.

### 4. Portfolio-level correlation/concentration enforcement at order time — not built
`vinu-portfolio` computes correlation-aware target weights, but nothing re-checks correlation or
concentration limits at the moment an order is actually about to fire. `OrderGuard` reasons about one
order/one symbol; nothing reasons about the portfolio as a whole at execution time. Depends on
`vinu-live` being wired to real broker routes first (status-2-fix-plan.md Priority 6).

### 5. Stop-loss enforcement — not built
`vinu-agent/vinu_agent/broker/alpaca.py` has no bracket-order support (`order_class`, `stop_loss`,
`take_profit`). The trade plan's exit checklist ("stop-loss hit → EXIT") is documentation only — the
stop is never actually placed as a live order. It only "fires" if a human or the agent is watching and
manually submits the exit later.

### 6. Automated kill-switch triggers — not built
`vinu-agent/vinu_agent/broker/kill_switch.py` is a filesystem-flag mechanism — someone has to touch a
file. There is no automated trigger tied to realized P&L, drawdown, or anomalous order activity that
halts trading on its own.

### 7. Market-hours / stale-data check — not built
Nothing in the order path calls Alpaca's clock endpoint before submitting, and nothing checks the
freshness of the price data used to size an order.

### 8. `vinu-live` is broken, not just incomplete
From the earlier code review, still unresolved:
- Calls agent-api routes that don't exist
- No close-order generation
- Hardcoded portfolio-value fallback
- TWAP-only execution (no VWAP)
- Ignores the `--interval` flag

### 9. No broker/paper-trading account exists
This is the actual ceiling on "readiness," not just one item on the list. Every fix above — including
everything already done — has only ever run against backtests and simulated data. Zero real orders
have ever been submitted through this system. Items 4–8 specifically cannot be built against verified
real behavior (bracket-order semantics, the actual clock endpoint, real fills) until this exists.

---

## Summary table

| # | Gap | Severity | Status |
|---|---|---|---|
| 1 | Survivorship bias (7-symbol universe) | High | **Resolved** — accepted and explicitly documented (decision made 2026-07-20); watchlist mechanism already supports expanding later without code changes |
| 2 | Point-in-time data discipline audit | Medium | **Resolved** — audited; active pipeline (news angles, indicators) confirmed clean; unused fundamentals factors flagged as unverified but not live |
| 3 | `vinu-portfolio` kill-switch duplication | Medium | **Resolved** — turned out to be a real cross-container isolation bug, not just duplication; fixed via a networked `/broker/halt` endpoint on agent-api |
| 4 | Portfolio-level pre-trade correlation/concentration check | Medium-High | Needs `vinu-live` wired first |
| 5 | Stop-loss bracket orders | High | Needs broker account |
| 6 | Automated kill-switch triggers | Medium-High | Partially unblocked — `PortfolioDrawdownMonitor` now has a working transport (see item 3's fix) but is still never called by anything; wiring a scheduled loop to feed it live values does **not** need a broker account |
| 7 | Market-hours / stale-data check | Medium | Needs broker account |
| 8 | `vinu-live` execution bugs | High | Needs broker account |
| 9 | No broker/paper account | Blocks items 4, 5, 7, 8 | Your call — open the account |

See [status-4-fix-plan.md](./status-4-fix-plan.md) for what can be done now vs. what waits on the
broker account.
