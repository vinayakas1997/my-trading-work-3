---
name: daily-allocation
description: How vinu-portfolio's regime-aware, outcome-confidence-weighted daily allocation actually works (PortfolioService.compute_daily_allocation) — what it computes itself vs. reuses, its known blind spots, and why it's on-demand, not scheduled.
category: reference
---

## Daily Allocation — Focus 3's v1, and its honest limitations

This is Step 10's substeps 2-4 deliverable: `PortfolioService
.compute_daily_allocation()` (`vinu_portfolio/service.py`), built on top of
the now-corrected risk-parity baseline (`build_portfolio()` — see this
plan's Step 10 file for the volatility-calculation bug found and fixed in
substep 1). It is a **defensible v1**, not a solved probability model —
substep 4 explicitly flagged the probability question as this step's core
research question, deserving its own pass rather than a bullet point. Read
this before assuming the allocation weights mean more than they do, or
before extending the tilts below without re-reading the limitations.

### What it computes

Two bounded multiplicative tilts applied to `build_portfolio()`'s existing
risk-parity `target_weight`, then renormalized to sum to 1.0:

```
target_weight = base_weight × regime_multiplier × outcome_multiplier
```

Both multipliers are `1.0 ± tilt_bound` (config: `regime_tilt_bound`,
`outcome_tilt_bound`, default 0.3 each) — a strategy can be tilted up or
down by at most 30% from its risk-parity base weight, not zeroed or
doubled. The response includes `base_weight`, `regime_multiplier`,
`outcome_multiplier`, and `outcome_source` per strategy — the reasoning is
inspectable, not just the final number.

### Regime — self-computed, not read from the `regime_analysis` angle

`vinu_portfolio/regime.py::classify_current_regime()` **reimplements**
`vinu-initial-analysis`'s `regime_analysis` angle's own `classify_regime()`
thresholding (21-day rolling vol, 0.7 quantile threshold, same
bull/bear/high_vol/sideways labels) against a benchmark symbol's (default
`SPY`) most recent daily return, fetched fresh via `vinu-stock-price`.

**Why reimplement instead of calling the angle's stored output:** read
`regime_analysis/compute.py` in full before assuming otherwise. Its stored
parquet output is a **window-aggregate** — for the whole analyzed history
it buckets days into regimes and reports per-bucket stats (win rate,
Sharpe, `pct_of_time`) plus an unordered transition-count table. There is
no row meaning "today's regime is X." Extracting a live single-day regime
from that stored shape isn't possible without recomputing it — so this
recomputes it directly, applied to just the latest observation, rather
than force-fitting an aggregate table into something it doesn't contain.

This read is **fail-open**: any fetch/compute failure returns
`{"status": "unavailable", "regime": None}`, which both multipliers treat
as neutral (`1.0`). This is a weighting tilt, not a safety gate — it must
never block allocation the way `OrderGuard`'s checks correctly block
orders (see `live-safety/SKILL.md`).

### Regime ↔ tag vocabulary mismatch (real, documented, not hidden)

`strategy-tags/tags.yaml`'s `regime:` field uses `trending`/`ranging`/
`mean_reverting`. `regime_analysis` (and this module) uses
`bull`/`bear`/`high_vol`/`sideways`. **These are two different, previously
unreconciled vocabularies** — confirmed by reading `tags.yaml` itself,
whose own per-strategy `notes` already reference
`regime_analysis.regime == "bear"`/`"sideways"`/`"high_vol"` directly
inside each strategy's own signal-zeroing logic (in `vinu-strategy`'s YAML
pipeline), a vocabulary `tags.yaml`'s `regime:` field never uses. So the
strategies' own internal gating already speaks the angle's vocabulary; only
the cross-strategy alignment-matching tags (Step 04's purpose) used the
other one.

`_REGIME_TO_TAGS` in `service.py` is the explicit, documented mapping this
step adds:
```
bull, bear  -> {"trending"}      # tags.yaml doesn't encode direction
sideways    -> {"ranging", "mean_reverting"}
high_vol    -> (no mapping — multiplier stays neutral)
```
`bull`/`bear` both mapping to `"trending"` is a real ambiguity, not a clean
1:1 match — `tags.yaml` doesn't record which direction a "trending" tag
means. `high_vol` deliberately gets no tag comparison: every one of the 4
currently-tagged strategies already zeros or cuts its own signal under
`high_vol` internally (per their own `notes` in `tags.yaml`) — adding a
second, portfolio-level high_vol penalty on top would double-penalize
rather than add information.

A strategy with no `tags.yaml` entry (any LLM/`trade_plan` artifact — that
file is keyed to the 4 YAML strategies only, per `strategy-tags/SKILL.md`)
gets a neutral `1.0` regime multiplier, not a guessed one.

### Outcome-memory — reuses `vinu-research`'s calibration store, doesn't add new storage

`_fetch_outcome_confidence()` calls the new
`GET /research/trade-plan/{artifact_id}/calibration` route
(`vinu_research/server/routes_trade_plan.py`), which reads
`calibration_entries` (`vinu_research/storage/strategy_store.py`) via the
existing `compute_calibration()` (`forecast_skill.py`) — no new
computation, just the first read path onto data that was previously
write-only (only consumed in-process by `approve_trade_plan`'s gate).

This table is already wired end-to-end and real: `vinu-live`'s
`FeedbackLoopWorker` posts every closed position's realized return to
`POST .../record-outcome` when it has an `artifact_id`. The `accuracy`
field (fraction of directionally-correct forecasts, `[0,1]`) is what
`_outcome_confidence_multiplier()` uses — `1.0` at `accuracy=0.5`
(coin-flip, neutral), tilting toward `1 + outcome_tilt_bound` as accuracy
approaches 1.0 and `1 - outcome_tilt_bound` as it approaches 0.0.

**Two real, load-bearing limitations, not silently inherited:**

1. **`type == "trade_plan"` artifacts only.** `record_realized_outcome()`
   requires `trade_plan_data` to be populated — a `type == "strategy"`
   research artifact (the older research-loop pipeline) never gets
   calibration entries. It falls back to `min_calibration_entries_for_tilt`
   (default 5) and reports `"insufficient_data"` — neutral, not penalized.
2. **YAML strategies have zero outcome tracking anywhere in this
   codebase.** Confirmed via `MetaStorage`'s schema (`name, description,
   schedule, enabled` only, no P&L/accuracy column). `_fetch_outcome_
   confidence()` always returns `"not_tracked"` for `kind == "yaml"` —
   never fabricated. A YAML strategy's daily weight is therefore driven
   only by risk-parity + regime alignment, never by its own track record,
   until something adds outcome tracking for that path (out of scope here).

An untracked/insufficient-data strategy keeps its risk-parity base weight
unmodified — new strategies are not penalized for lacking history, matching
`allocate_risk_parity()`'s own existing "fall back to neutral when data is
missing" convention.

### What this does NOT fix: Stage 2 (`ShadowEvaluator`) is still dormant

Per `live-safety/SKILL.md`: no ACTIVE strategy has ever been checked
against real paper-trading performance, because `ShadowEvaluator.
evaluate_all()` is never called by anything. This design **partially
compensates, not fixes**: calibration track-record (above) is a weaker
proxy for "has this strategy been checked against reality since
promotion" — it reflects forecast accuracy on whatever positions were
actually taken, not a dedicated paper-trading comparison against backtest
expectations the way Stage 2 was designed to provide. An artifact with
zero calibration history is more suspect than one with a real track
record, but this is not the same signal Stage 2 would produce if wired up.
Treat closing Stage 2 as still open, independent work.

### Position sizing — `sizing.py` wired in, previously dead code

`vinu_portfolio/sizing.py::apply_position_sizing()` existed, tested-shape
compatible, but was never called from anywhere in `vinu_portfolio` before
this step. `compute_daily_allocation()` now calls it — but only when live
equity is available (`GET {agent_api_url}/agent/broker/account`, the same
call `drawdown_scheduler.py` already makes). Without a configured broker
account, the response has weights only, no `position_size` — this mirrors
`drawdown_scheduler.py`'s own "not configured yet is expected, not an
error" handling.

### Why this is on-demand only, not scheduled

`GET /portfolio/daily-allocation` and `vinu-portfolio daily-allocation`
(CLI) exist; neither is started from `entrypoint.sh`. This mirrors
`vinu_research/cli.py::promote_scan_main`'s own precedent — its comment
explains that auto-promoting a strategy to ACTIVE is "a bigger consequence
than auto-triggering more research," so it stays a command a human or
agent invokes on purpose rather than a silent background loop. Allocation
weight changes are comparably consequential; hooking this into an
automatic scheduler is a deliberate, separate, higher-scrutiny decision —
not something this step does implicitly by building the logic.
