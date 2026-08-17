---
name: decimal-audit
closes: "production-grade" gap raised in conversation (2026-08-17) — zero files use Decimal for financial math
status: done — real gap found on the order-quantity/cash-ledger path and fixed with Decimal; analytics left on float
priority: lower urgency than 10/11 — does not block or get retrofitted by other tasks the way auth/logging do
---

# Task: audit and fix float-vs-Decimal precision on the real money path

## Goal

Determine whether real order quantities and cash-ledger bookkeeping ever use raw `float` (rounding-error
risk with real financial consequences), as opposed to configuration thresholds and statistical analytics
(where `float` is normal and fine), and fix whichever parts actually touch money.

## Why

Grepped the whole tree for `from decimal import Decimal` — zero hits anywhere. Grepped `vinu-portfolio`
and `vinu-live` for `float(` — 19 hits. On inspection, the ones found so far are config parsing
(`VINU_PORTFOLIO_MAX_PER_STRATEGY`, `VINU_PORTFOLIO_DRAWDOWN_HALT`) and statistical analytics (returns,
volatility, regime classification) — normal, fine uses of `float`. **What wasn't confirmed in this pass**
is whether the actual order-quantity and account-equity ledger code (wherever real position sizes and
cash balances are stored and summed) also uses `float`. That's the part where compounding rounding error
becomes real lost or gained money, not just noisy statistics.

## Current state (verified 2026-08-17 — this is a starting point, not a conclusion)

- Zero `Decimal` usage anywhere in `vinu-components`.
- `vinu-portfolio/vinu_portfolio/config.py`, `regime.py`, `shock_correlation.py`, `drawdown_scheduler.py`,
  `risk_budget.py`, `historical_simulation.py` all use `float()` — confirmed these specific lines are
  config/analytics, not ledger arithmetic (verified by reading the actual lines, not just the grep hit).
- The actual order-execution and cash-ledger code path was **not located** in this pass — first step
  below is finding it.

## Steps

1. Locate the actual code that computes and stores: order quantities sent to a broker, account equity/
   cash balance, and any running P&L totals. Likely candidates based on naming conventions seen elsewhere
   in this plan: something under `vinu-live` near the broker-execution code, or `vinu-portfolio`'s
   position-tracking modules. Confirm the real location before assuming.
2. For each piece found, determine: is this genuinely money (a specific number of shares/contracts, a
   specific dollar amount) or is it a ratio/weight/statistical estimate (where `float` is appropriate)?
   Only convert the former.
3. Where real money math is found using `float`, convert to `Decimal` with an explicit, documented
   rounding/quantization rule (e.g. round to the instrument's actual tradeable increment — whole shares,
   or whatever fractional-share precision the broker actually supports).
4. Add a regression test that would have caught the specific class of bug `Decimal` prevents — e.g. sum a
   sequence of values that produces visible float drift (`0.1 + 0.2 != 0.3`-style) through the real
   ledger code path, confirm it's now exact.
5. Where `float` genuinely is fine (config thresholds, weights, statistical outputs like Sharpe/volatility),
   leave it — don't convert code that was never actually handling literal money. Over-converting adds
   friction (Decimal doesn't interoperate cleanly with numpy/pandas, which the analytics code clearly
   relies on) for no real benefit.

## Acceptance criteria

- A clear, documented answer to "does the real order-quantity/cash-ledger path use float or Decimal
  today" — this alone might be the most valuable output if the answer turns out to be "it was already
  fine, the float usage found was all analytics."
- If a real gap is found: the specific money-handling code is converted to `Decimal`, with a test proving
  the specific rounding-error scenario it fixes.
- No unnecessary conversion of legitimately-float analytics code.

## Dependencies

None. Independent of every other task.
