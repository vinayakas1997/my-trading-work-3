# Phase 1 — Shared Risk-Math Library

Status: **not started** · Depends on: — · Blocks: Phase 2, Phase 4, Phase 5

## What it is

A new computation category inside `vinu-tools` (`compute/risk`, alongside the existing
`compute/{formulas, bench, ml, factors}`), providing: realized volatility, **conditional
volatility (GARCH(1,1)/EGARCH)**, Value-at-Risk, greeks (delta/gamma/vega/theta — requires an
options data/pricing source; confirm whether one exists before starting, since greeks cannot be
computed without it), expected move, position-sizing formulas, and a **dynamic,
shrinkage-estimated (e.g. Ledoit-Wolf) covariance matrix** across an arbitrary symbol set. This
is pure, deterministic arithmetic — no LLM, no storage dependency beyond reading price/options
data — and is built as a shared library specifically so no other phase or package reimplements
volatility or VaR math independently.

## Why conditional volatility and dynamic covariance, not flat versions

A flat "realized vol over the last N days" treats every day in the window as equally
informative. It isn't: volatility clusters in time — a large move raises the odds of another
large move before decaying on a known curve — so this phase must forecast *conditional*
volatility, not just measure historical volatility. Separately, shocks and correlations cluster
**across** symbols too: a sector/factor shock can hit several positions that look diversified by
static sector label, and correlation itself spikes in a crisis ("correlations go to 1"). A naive
sum of independent per-symbol risk numbers misses this entirely, so this phase must also produce
a live, regime-aware covariance estimate, not a static one. Both are first-implementation
requirements here, not later hardening — a version shipped without them would need to be rebuilt,
not extended, once the gap surfaced in Phase 5's circuit breaker.

## Impact

**Before this phase:** No component in the system produces a live, reusable risk number.
Initial-Analysis's existing risk angles (`drawdown_deep_dive`, `regime_analysis`,
`deflated_sharpe_ratio`) characterize historical strategy/stock behavior; none compute current
VaR, greeks, or a clustered covariance estimate usable at decision time.

**After this phase:** Any consumer — Phase 2's shock-tagging angles, Phase 4's trade-plan
authoring, Phase 5's circuit breaker — can call one shared, tested implementation for these
numbers instead of each re-deriving its own, avoiding the exact duplication problem
`02-storage-memory` flagged when `vinu-stock-price` and `vinu-news` each hand-rolled their own
catalog/watermark logic instead of sharing `vinu-lib`.

**What still won't work after this phase alone:** These are library functions, not a running
system — nothing calls them yet, nothing enforces limits from them, nothing sizes off them.
That's Phases 2, 4, and 5.

## Where changes occur

- `vinu-tools/vinu_tools/compute/risk/` (new) — formulas module, mirroring the existing
  `compute/{formulas, bench, ml, factors}` layout and its catalog/spec conventions.
- If no options data/pricing path currently exists anywhere in the codebase, that data source
  and a pricing model (e.g. Black-Scholes + an IV surface) is a prerequisite sub-task here — verify
  this first; it changes this phase's scope substantially if it must be built from scratch.
- No write dependency on any other package.

## How to test it

- Unit tests: known-input/known-output cases for VaR, realized vol, and expected-move formulas
  against hand-computed or reference-library values.
- Golden-file tests: greeks computed against a reference options-pricing library for a fixed set
  of strikes/expiries/underlying prices.
- Conditional-vol test: fit the GARCH/EGARCH model against a known clustered-volatility
  historical series (a period with a known vol spike followed by decay) and confirm the fitted
  conditional vol tracks the clustering pattern, not a flat average.
- Dynamic-correlation test: seed a synthetic basket with low correlation in a "calm" window and
  a spike in a "crisis" window; confirm the covariance estimate picks up the regime shift.
- Shrinkage test: with a small symbol set (where a naive sample covariance would be
  unstable/singular), confirm the shrinkage estimator still produces a well-conditioned matrix.
- Property test: position-size output never recommends a size exceeding a stated risk budget,
  across randomized budget/vol/price combinations.
