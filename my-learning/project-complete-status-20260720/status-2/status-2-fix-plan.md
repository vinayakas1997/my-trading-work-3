# Pre-Trading Readiness — Fix Plan

Companion to [status-2.md](./status-2.md) (the assessment). This is the prioritized plan for
closing the gaps identified there, before paper trading is treated as a meaningful validation step.
Ordered by what would silently corrupt everything downstream if left unfixed, not by what's easiest.

---

## Priority 1 — Turn on adjusted prices everywhere

**Why first:** this is a data-correctness bug, not a design gap. Every other fix in this plan
inherits whatever bias this leaves in place — fixing statistical rigor or risk gates on top of
unadjusted prices just produces more precisely wrong answers.

**What to do:**
1. In `vinu-stock-price/vinu_stock/service.py`, confirm whether the underlying Alpaca client
   actually supports fetching split/dividend-adjusted series (it should — verify the parameter
   Alpaca expects).
2. Change the default for the `adjusted` parameter to `True` at the service layer, OR — safer,
   since flipping a shared default can silently change historical comparisons — explicitly pass
   `adjusted=True` at each call site: `vinu-tools/vinu_tools/client/stock_price.py`,
   any direct price fetches in `vinu-simulator`, and `vinu-research`.
3. Re-run/re-validate any existing pre-computed `initial-analysis` parquet data for the 7 tracked
   tickers (AAPL, AMZN, GOOGL, META, MSFT, NVDA, TSLA) against adjusted prices — the currently
   stored angle data was computed on the old (unadjusted) series and should be treated as stale
   once this changes.

**Effort:** small (a handful of call sites + one re-computation pass). **Do this before anything
else on this list.**

---

## Priority 2 — Wire the shadow-evaluator → promotion gate

**Why:** this is the actual mechanism that was supposed to answer "has this strategy proven itself
in a paper/shadow context before I trust it with capital." Right now it's built and dangling.

**What to do:**
1. Read `vinu-research/vinu_research/shadow/reporter.py` and `backtester.py` to confirm what
   signal they already produce (presumably a shadow-account P&L/metrics summary per BENCHING
   artifact).
2. Define an explicit, simple promotion threshold (e.g., shadow Sharpe > X over N days, max
   drawdown under Y%, deflated Sharpe still positive) — this is a decision only you can make, not
   something to silently default.
3. Add a new CLI subcommand or worker loop (following the repo's established
   `while True: cycle(); time.sleep(interval)` pattern, same as `decay-scan`/`schedule-decay`) that:
   - lists BENCHING artifacts,
   - runs the shadow backtester on each,
   - calls `POST /research/artifacts/{id}/promote` when the threshold is cleared.
4. Register it as a service in `docker-compose.yml`, following the same pattern as the
   `research-decay-scan`-style worker already planned in the Phase A/B roadmap.

**Effort:** medium — mostly wiring existing pieces together, plus one real decision (the threshold).

---

## Priority 3 — Make multiple-testing correction cumulative per symbol

**Why:** without this, the automated re-research loop manufactures false statistical confidence
over time by construction — every re-research session "forgets" every prior trial taken against
that symbol.

**What to do:**
1. Add a persistent counter (in the strategy store, keyed by symbol or by
   symbol+universe) tracking the cumulative number of research candidates ever generated and
   evaluated for that symbol — not just within the current loop.
2. In `vinu-research/vinu_research/comparison.py::rank_candidates`, replace
   `n_trials = max(len(candidates), 1)` with the cumulative count fetched from that counter (current
   loop's candidates + all prior candidates for the symbol).
3. Increment the counter each time a research loop runs for that symbol, regardless of outcome.

**Effort:** small-medium — one new store method, one call-site change, plus a migration to
backfill/estimate the counter for symbols already researched before this change lands.

---

## Priority 4 — Add a stress-test / scenario check before ACTIVE promotion

**Why:** walk-forward and Monte Carlo permutation validate a strategy's *historical* edge; neither
answers "what happens to this position/portfolio in a known crisis window."

**What to do:**
1. Pick 2-3 reference historical windows already known to be stress periods (e.g., the 2020-03
   COVID crash, the 2022 rate-hike drawdown) — as date ranges, no new data source needed if
   `vinu-stock-price` already has coverage back that far.
2. Add a function to `vinu-simulator` (alongside `monte_carlo_permutation`,
   `bootstrap_sharpe_ci`, `walk_forward_consistency` in `engine/validation.py`) that replays a
   strategy/portfolio's weights through those windows and reports max drawdown, worst single-day
   loss, and recovery time.
3. Surface this in the run card (`engine/run_card.py`) as a new "Stress Test" section, and make it
   part of the promotion-threshold check from Priority 2 — not just informational.

**Effort:** medium — the mechanics mirror what `walk_forward_consistency` already does, just against
fixed historical windows instead of a rolling split.

---

## Priority 5 — Liquidity/capacity-aware position sizing

**Why:** a strategy can look profitable at backtest scale and be unexecutable, or self-defeating via
its own market impact, at the size it would actually be traded.

**What to do:**
1. `vinu-simulator/engine/costs.py` already has an Almgren-Chriss-style market-impact model — check
   whether average daily volume (ADV) is already available per symbol from `vinu-stock-price`.
2. Add a position-sizing cap expressed as "% of ADV" (a common, simple starting point: cap any
   single order at 1-5% of recent 20-day ADV) in `vinu-simulator/engine/sizing.py`.
3. Feed the same cap into `OrderGuard.check()` in `vinu-agent/vinu_agent/broker/order_guard.py` so
   backtest-time sizing and live pre-trade checks agree — this closes the same class of gap as the
   `max_position_pct` fix already applied, but for liquidity rather than equity concentration.

**Effort:** medium — needs ADV data available first; check that before estimating further.

---

## Priority 6 — Portfolio-level correlation/concentration enforcement at order time

**Why:** correlation-aware weights are computed in `vinu-portfolio`, but nothing re-checks them at
the moment an order is about to fire — if `vinu-portfolio` and the execution path ever drift out of
sync, nothing at the order layer catches it.

**What to do (parked until `vinu-live` execution work resumes, per your stated broker-account
constraint — listed here for sequencing, not to be started now):**
1. Once `vinu-live`'s signal-to-order translation is actually wired to real agent-api/broker routes
   (see the separately tracked `vinu-live` bugs in `trade-plan-and-fixes-plan.md` §2.2), add a
   pre-trade check that re-fetches (or receives) the current correlation/concentration state from
   `vinu-portfolio` and rejects/flags orders that would breach a configured limit, independent of
   whatever target weights were computed upstream.
2. This is a genuine defense-in-depth addition, not a duplicate of existing `OrderGuard` checks —
   `OrderGuard` reasons about one order/one symbol; this reasons about portfolio-level correlation.

**Effort:** medium, but correctly sequenced *after* `vinu-live` execution work — do not build this
in isolation before the execution path it's meant to protect actually exists.

---

## Suggested order of work

1. **Priority 1** (adjusted prices) — immediately, blocks trusting anything else.
2. **Priority 3** (cumulative multiple-testing correction) — small, prevents the re-research loop
   from digging the statistical-confidence hole deeper while the rest of this plan is in progress.
3. **Priority 2** (shadow-evaluator wiring) — this is the actual gate the paper-trading plan depends
   on; do this before spending more time generating strategies that have nowhere real to graduate to.
4. **Priority 4** (stress testing) — feeds into the same promotion threshold from Priority 2, so
   sequence it right after.
5. **Priority 5** (liquidity-aware sizing) — needed before any live order sizing is meaningful, but
   not urgent while still paper-trading-only.
6. **Priority 6** (portfolio-level pre-trade enforcement) — stays parked with the rest of the
   `vinu-live` execution work until the paper-trading broker account exists, per your existing
   direction on that.
