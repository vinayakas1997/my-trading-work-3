---
name: full-plan
status: definition-phase
purpose: single source of truth for the four post-Stage-1 improvement items — what gets built, in which files, what "done" looks like — before any implementation starts
---

# Post-Stage-1 Improvement Plan (2026-08-02 draft)

**This is a definition document, not an implementation log.** Nothing
described here has been built yet. Same discipline as
`e2e-test-0731/full-plan.md` used for Stage 1: scope and file targets
fixed up front so an agent picking this up doesn't have to re-derive
architecture decisions or re-discover what's already been tried.

## Why this exists

Stage 1 (`e2e-test-0731/`) is complete and independently verified — real
Sharpe (0.65), CAGR (14.8%), backed by a stored, checksummed simulation
run. During that work and the follow-on `news_price_causality`
integration (market-model abnormal returns, FinBERT sentiment, novelty
score, XGBoost significance classifier — all now in production in
`vinu-initial-analysis`), four concrete gaps were identified and scoped
for direct improvement. This plan defines all four before any of them
get built, same reasoning as Stage 1's own definition-first approach.

## The four items — one-line summary, full detail in scope-responsibilities/

| # | Item | Where it lives | Status |
|---|---|---|---|
| 1 | Peer/cross-asset comparison | `vinu-initial-analysis` (new angle logic) | Not started |
| 2 | Significance classifier coverage improvement | `vinu-initial-analysis` (extend existing) | Not started |
| 3 | Stage 2 live-trading readiness — real smoke test | `vinu-live` + `vinu-agent` (verification only, no new code expected) | Not started |
| 4 | Live options Greeks/IV tool | `vinu-agent` (new tool) | Not started |

Items 1 and 2 are **historical/batch** — they can run against the full
2022-2026 window like everything else already in `vinu-initial-analysis`.
Items 3 and 4 are **present/forward-time only** — item 3 because paper
trading is inherently live, item 4 because Alpaca's options data doesn't
reach back to 2022 (historical option bars only exist since Feb 2024;
Greeks/IV are a live-snapshot-only endpoint with no historical lookup at
all). Don't try to backfill 3 or 4 historically — it isn't possible with
the data source available.

## Important context already established — don't re-derive this

- **Two "Stage 2 blocker" claims in `e2e-test-0731/scope-responsibilities/`
  (vinu-agent.md, vinu-live.md) were checked and found FALSE, corrected
  2026-08-02** (see those files' correction notes and
  `e2e-test-0731/stage-2-plan.md`): the Alpaca broker is already
  configured and connected to a live $100k paper account
  (`GET http://localhost:8086/agent/broker/account` →
  `{"configured":true,"equity":100000.0,...}`), and `vinu-live`'s
  position tracking is a real SQLite-backed store
  (`vinu_live/book/positions.py`, `BookBackend`) on a genuine host
  bind-mount (`./data/live:/data`), not in-memory. Item 3 in this plan is
  a *verification* task (prove it survives a real restart), not a build
  task — don't re-implement something that already works.
- **The significance classifier already has a documented leakage lesson**
  (see `vinu_initial_analysis/angles/news_price_causality/
  significance_model.py`'s module docstring): the original research
  script's feature set included `impact_label`, which is derived from the
  same post-event price window as the prediction target (`ar_significant`)
  — a leak that inflated the reported lift from ~5-6x (real, verified) to
  a false ~7-8x. Any new feature added for item 2 must be checked against
  this same standard: is it knowable at the instant the article
  publishes, or does it depend on post-event price data? If the latter,
  it cannot go into the classifier's feature set.
- **Direction prediction does not work** — confirmed twice (once with
  rule-based `sentiment_score`, once with FinBERT `finbert_score`), both
  at ~50% coin-flip accuracy on already-significant events across
  AAPL/TSLA/JNJ. None of the four items in this plan are direction
  prediction attempts. Item 4 (options data) might plausibly help
  direction prediction later via put/call skew, but that is explicitly
  out of scope here — untested speculation, not a task.
- **`AngleStorage.read()` was fixed 2026-08-02** to return only the
  latest run per symbol+angle instead of concatenating every retained run
  (was silently double-counting events on every re-run). Anything new
  written to `vinu-initial-analysis`'s parquet storage automatically
  benefits from this fix — no action needed, just don't reintroduce the
  old concatenate-all pattern.

## Data sources — what's available, what isn't (checked against real docs 2026-08-02)

- **Alpaca stock/candle data**: full historical depth to 2022-01-01,
  already used throughout. Sufficient for items 1 and 2.
- **Alpaca options data**: real Greeks (delta/gamma/theta/vega/rho) and
  implied volatility, pre-computed, via the option chain endpoint — but
  it is a **live snapshot only, today's data, no historical lookup**.
  Separate historical option bars/trades exist but **only since February
  2024** — cannot cover 2022 to early-2024. This is why item 4 is a
  present-time tool, not a batch angle.
- **yfinance**: already used in `vinu-agent/vinu_agent/tools/
  fundamentals_tool.py` for fundamentals. Unofficial scraper, no SLA —
  fine for on-demand lookups (that's what it's already used for), do not
  use it as a new options data source when Alpaca's official API already
  covers it.

## Execution order — recommended, not mandatory

1. **Item 3 first** (verification only, cheapest, de-risks the Stage 2
   go/no-go the user actually cares about next).
2. **Item 1 and item 2** in either order — both are self-contained
   `vinu-initial-analysis` work, independently testable per ticker
   (AAPL/TSLA/JNJ), no cross-dependency between them.
3. **Item 4 last** — a new, isolated `vinu-agent` tool, no dependency on
   1/2/3.

## How to verify each item — general rule

Every item must be checked against **real, live data** in the running
`vinu-components` stack, the same way Stage 1 was verified (not just unit
tests against synthetic fixtures). Sequence requests to `news-api` and
`initial-analysis-api` one at a time — concurrent heavy requests against
the shared SQLite-backed services previously crashed `news-api`'s
`/news/health` entirely (see prior incident, `news.db` WAL-mode fragility
under concurrent load over a Windows Docker bind mount). This constraint
still applies to any new work here.

## Related documents

- [scope-responsibilities/](scope-responsibilities/) — one file per item,
  exact files to touch, function-level detail, expected output.
- [testing-status/](testing-status/) — same convention as
  `e2e-test-0731/testing-status/`: one `test-log.md` per item, "what will
  be tested" filled in now, "Bug/Fix Log" starts empty.
- [../e2e-test-0731/full-plan.md](../e2e-test-0731/full-plan.md) — Stage 1
  definition (complete).
- [../e2e-test-0731/stage-2-plan.md](../e2e-test-0731/stage-2-plan.md) —
  Stage 2 (paper trading) definition, item 3 here feeds directly into it.
