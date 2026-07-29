# Remaining Gaps After Status-4 — What's Actually Left

Companion to [status-4.md](../status-4/status-4.md) and [status-4-fix-plan.md](../status-4/status-4-fix-plan.md).
Those documents listed 9 gaps; 3 are now closed (survivorship bias — accepted and documented,
point-in-time data discipline — audited clean, `vinu-portfolio` kill-switch — fixed, and turned out to
be a real cross-container isolation bug, not just code duplication). This document is the remaining 6,
renumbered, so there is one current list instead of a mix of done/not-done items inside an older
document.

**Update: all 5 code-level items below are now resolved.** What originally looked like "needs the
broker account to build" turned out, on closer inspection, to mostly mean "needs the broker account to
*verify against real behavior*" — the code itself could be written and tested against Alpaca's
documented, stable API contracts (bracket orders, the clock endpoint) using mocked responses, the same
way every other broker-dependent check in this codebase already is. The one thing that genuinely
cannot be built by writing more code is item 6 — the account itself.

---

## 1. No stop-loss enforcement — RESOLVED
`AlpacaBroker.submit_order()` now supports Alpaca's documented `bracket`/`oto` order classes via new
`take_profit_price`/`stop_loss_price` params, exposed through `TradeTool`. Implemented and tested
against Alpaca's documented API contract; not yet exercised against a live account (see item 6).

## 2. Automated kill-switch trigger — RESOLVED
Wired up: a new `portfolio-drawdown-monitor` service polls account equity from a new
`GET /broker/account` route on agent-api every 300s and feeds it to `PortfolioDrawdownMonitor`, which
halts trading via the already-fixed `/broker/halt` transport on breach. Runs end-to-end today,
reporting `no_broker_account` as its status until a broker account exists rather than doing nothing.
See [status-5-fix-plan.md](./status-5-fix-plan.md) Priority 1.

## 3. No market-hours / stale-data check — RESOLVED
`AlpacaBroker.get_clock()` plus a new `OrderGuard._check_market_open()` (gated by
`TradingMandate.require_market_open`, default on) reject orders while the market is closed. Implemented
and tested against Alpaca's documented clock contract; not yet exercised live (see item 6).

## 4. No portfolio-level correlation/concentration check at order time — RESOLVED
New `OrderGuard._check_portfolio_concentration()` re-fetches `vinu-portfolio`'s live target weights and
correlation matrix at order time and rejects buy orders that would breach configured concentration or
correlation limits — genuine defense-in-depth against `vinu-portfolio` and execution drifting out of
sync, not just a duplicate of `max_position_pct`.

## 5. `vinu-live` was broken, not just incomplete — RESOLVED
All five sub-bugs fixed and tested, see status-5-fix-plan.md Priority 4 for the detail on each:
- Calls to nonexistent agent-api routes — fixed by adding `/broker/positions` and `/broker/order` (the
  latter deliberately delegates to `TradeTool`, so `vinu-live` orders get the same `OrderGuard`
  protections as the LLM path, not a bypass), and pointing price fetches at `vinu-stock-price` directly.
- No close-order generation — `SignalTranslator.translate()` now generates a real close instruction for
  positions dropped from target weights, not just rebalances of positions still present.
- Hardcoded portfolio-value fallback — now reads real account equity via `/broker/account`, with an
  explicit, logged, configurable fallback instead of a silent magic number.
- TWAP-only — added `plan_vwap()`/`compute_volume_profile()`, selectable via `execution_style` config.
- `--interval` flag ignored — root-caused to a second console-script entry point
  (`vinu-live-worker` → `worker_main` directly) that never parsed `sys.argv`; fixed.

## 6. No broker/paper-trading account exists
The one item that isn't a code gap. Every fix across status-2 through status-5 — including everything
in this document — has only ever run against backtests, simulated data, or Alpaca's documented API
contracts verified via mocked tests. Zero real orders have been submitted through this system. This
was never something further code changes could close; it's an external prerequisite, and it's your
call when to open it.

---

## Summary table

| # | Gap | Severity | Status |
|---|---|---|---|
| 1 | Stop-loss bracket orders | High | **Resolved** |
| 2 | Automated kill-switch trigger (scheduler) | Medium-High | **Resolved** |
| 3 | Market-hours / stale-data check | Medium | **Resolved** |
| 4 | Portfolio-level pre-trade correlation/concentration check | Medium-High | **Resolved** |
| 5 | `vinu-live` execution bugs (5 sub-bugs) | High | **Resolved** |
| 6 | No broker/paper account | Blocks nothing left to build — only real-world verification | Your call — open the account |

See [status-5-fix-plan.md](./status-5-fix-plan.md) for the full detail on each fix.
