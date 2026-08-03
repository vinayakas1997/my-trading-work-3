---
name: pnl-and-decision-reporting
component: vinu-agent (new report script, reads item 3's output)
status: not-started
---

# Item 4 — P&L + Decision-Transcript Reporting

## What this is

Turns item 3's raw per-day JSON transcripts into the two things the user
actually asked for: "how much money is this worth" (a number, with
context) and a readable account of what the agent did and why, day by
day.

## Don't reimplement metrics

`vinu_simulator.engine.metrics.compute_full_metrics` /
`compute_performance_metrics` already compute Sharpe, CAGR, max drawdown,
etc. from an equity curve + daily returns series
(`vinu-simulator/vinu_simulator/engine/simulator.py:277-283` shows the
call shape). Build the replay's equity curve (from item 2's historical
broker's daily account snapshots) into the same `pd.Series` shape those
functions expect, and call them directly — do not write a second, parallel
Sharpe/drawdown implementation.

## Report contents

1. **Headline number**: total P&L in dollars and %, over the replay
   window, starting from the same $100k baseline as the real paper
   account (see item 2) — the direct answer to "how much money would this
   have made."
2. **Standard metrics**: Sharpe, max drawdown, win rate, number of
   trades — via `compute_full_metrics`, so these are comparable to every
   other backtest/simulation number already produced in this project
   (Stage 1's Sharpe 0.65 / CAGR 14.8%, for scale).
3. **Trade log**: every simulated fill (date, symbol, side, qty, price,
   resulting position) — from item 2's trade ledger, not reconstructed
   from transcripts.
4. **Day-by-day narrative**: for each day, a short extract of what the
   agent decided and why (pulled from its final assistant message and any
   notable tool calls) — this is what item 5 actually reads to answer the
   behavioral questions; keep it structured (JSON or a consistent
   markdown table), not free-form prose that's hard to grep later.
5. **Honesty flags**: explicitly call out any day where the agent's
   decision looks like it's calling direction from `significance_score`
   or sentiment (see `full-plan.md`'s warning) — a good month driven by
   a mechanism proven not to work is not a good result, it's a lucky
   coincidence that needs to be reported as such, not celebrated.

## Files to touch

- New: `vinu-components/vinu-agent/scripts/report_month_replay.py` (or a
  notebook, if that's easier to iterate on for the day-by-day narrative —
  either is fine as long as the headline metrics come from
  `vinu_simulator.engine.metrics`, not hand-rolled).
- Output: `the-1-month-back-testing/results/<run-id>/report.md` (or
  `.html` if a notebook is used) — human-readable, checked into this
  folder so the result is preserved the same way `the-stage-2-claude`'s
  `test-log.md` files preserve verification evidence.

## Expected output / how to verify

- Headline P&L number that is internally consistent with the trade log
  (sum of trade-level realized/unrealized P&L reconciles with the
  starting-vs-ending account equity — if it doesn't, something in item 2
  or this report has a bug, find it before trusting the number).
- Metrics computed via the actual `vinu_simulator.engine.metrics` call,
  confirmed by comparing one hand-computed data point (e.g. total return
  over the window) against the library's own output.
- A report that a non-technical reader (the user) can read top-to-bottom
  and understand: what happened, whether it made money, and whether
  anything looked like it was cheating (lookahead, direction-calling from
  a proven-negative signal, or otherwise).
