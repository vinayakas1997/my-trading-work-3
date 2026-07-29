# Analysis-to-Execution Gate — Senior-Quant Review

Companion to [status-2.md](../status-2/status-2.md), [status-2-fix-plan.md](../status-2/status-2-fix-plan.md),
and [status-2-architecture-and-status.md](../status-2/status-2-architecture-and-status.md). Those
documents cover the data/statistical/promotion-gate gaps in the *research* pipeline and confirm all
five priorities from the status-2 fix plan are now implemented. This document asks a narrower,
different question: **once a strategy has been researched and even promoted to ACTIVE, is anything
actually stopping the agent from submitting an order for a symbol that was never analyzed at all, or
whose strategy never cleared the promotion gate?**

Verdict up front: **no.** The research pipeline (16 analysis angles, deflated Sharpe, holdout,
stress testing, BENCHING→ACTIVE promotion) and the risk pipeline (`OrderGuard` — position size,
capital utilization, daily caps, ticker allow/blocklist, kill switch) are both individually solid,
verified working code. They are simply **not connected to each other.** Nothing in the order-submission
path reads analysis status, artifact status, or validation results. The "research desk" and the
"risk desk" both function; there is no compliance checkpoint between them.

---

## 1. The core gap — `submit_order` has no idea whether analysis happened

`vinu-agent/vinu_agent/tools/trade_tool.py::TradeTool.execute()` calls `OrderGuard.check()` and
nothing else before submitting to Alpaca. `OrderGuard.check()`
(`vinu-agent/vinu_agent/broker/order_guard.py`) checks, in order: kill switch, blocked/allowed
tickers, short-selling permission, order value, daily order count, position-percentage of equity,
capital-utilization percentage, daily trade volume. **Every one of these is a risk/sizing check.
None of them ask "has this symbol been analyzed" or "is the strategy behind this order ACTIVE."**

Separately, `vinu-agent/vinu_agent/tools/trade_plan_tool.py::generate_trade_plan` exists and does
real work — pulling 4 timeframe-relevant angles, a feature preset, and the latest matching backtest's
validation metrics (Monte Carlo p-value, deflated Sharpe, holdout/stress-test status where available)
into a structured entry/exit checklist. But calling it before calling `submit_order` is entirely up
to the LLM's own judgment. The system prompt
(`vinu-agent/vinu_agent/agent/context.py::_SYSTEM_PROMPT`) instructs the model to load a skill before
backtest/research tasks — it says nothing about analysis being a precondition for trading. There is
no code path that makes `generate_trade_plan` (or an artifact's `ACTIVE` status) a prerequisite for
`submit_order` succeeding.

**Concretely, today, the agent can submit a market order for a symbol that has zero rows of
`initial-analysis` data, zero backtest runs, and zero connection to any research artifact — and
`OrderGuard` will approve it as long as it fits inside the position-size/capital/order-count limits.**

---

## 2. A known stub inside the trade plan itself

`trade_plan_tool.py::_render_entry_checklist`, item 4 ("Volume / volatility within normal range") is
hardcoded to always render `PENDING` — it is never actually computed from real volume or volatility
data (lines ~306-309). Even when a human or the LLM does read the generated trade plan before
deciding to trade, this specific checklist row carries no signal at all; it looks like a real check
but isn't one.

---

## 3. Downstream of the order — the exit side has the same disconnection problem

Two more gaps found while tracing what happens *after* an order would be approved, listed here for
completeness even though they sit downstream of the analysis-gate question this document is centered
on:

- **No stop-loss enforcement mechanism.** `vinu-agent/vinu_agent/broker/alpaca.py` has no bracket-order
  support (no `order_class`, `stop_loss`, `take_profit` parameters anywhere in the submit path). The
  trade plan's exit checklist ("stop-loss hit → EXIT") is documentation only — the stop is never
  actually placed as a live order. It only "fires" if a human or the agent is watching and manually
  submits the exit later.
- **The kill switch is fully manual.** `vinu-agent/vinu_agent/broker/kill_switch.py` is a
  filesystem-flag mechanism (`is_trading_halted()`/`halt_trading()`) — someone has to touch a file.
  There is no automated trigger tied to realized P&L, drawdown, or anomalous order activity that
  halts trading on its own.
- **No market-hours / stale-data check.** Nothing in the order path calls Alpaca's clock endpoint
  before submitting, so an order can be built and sent using data of unknown freshness relative to
  whether the market is even open.

These three are real, but — unlike the analysis-gate gap in §1 — they inherently require a live
paper-trading broker account to build *and test* meaningfully, so they're tracked here but correctly
deferred, consistent with the existing standing decision to park `vinu-live`/broker-dependent work
until that account exists.

---

## 4. Summary table

| Area | Status | Severity | Needs broker account to fix? |
|---|---|---|---|
| Analysis/promotion status checked before `submit_order` | Does not exist | **Critical — the actual gate is a no-op** | No |
| Volume/volatility checklist item | Hardcoded stub, never computed | Medium — false sense of a real check | No |
| Stop-loss enforcement at order time | Documentation only, no bracket orders | High | Yes — parked |
| Automated kill-switch triggers | Manual file flag only | Medium-High | Yes — parked |
| Market-hours / stale-data check pre-order | Does not exist | Medium | Yes — parked |

See [status-3-fix-plan.md](./status-3-fix-plan.md) for the prioritized plan to close the two gaps
that can be fixed now.
