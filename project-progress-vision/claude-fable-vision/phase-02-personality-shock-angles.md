# Phase 2 — Personality / Shock-Clustering Angles

Status: **not started** · Depends on: Phase 1 (risk-math library) · Blocks: Phase 4, Phase 7

## What it is

New angle folders inside `vinu-initial-analysis`, following the exact pattern its existing 19
angles already use (self-contained folder, own `compute.py`, schema-agnostic storage, discovered
dynamically by `runner.py` — no registration needed, deleting the folder removes everything with
no side effects). These angles characterize **behavior**, not just history: how a symbol tends
to act after a shock.

A prerequisite sub-task: a **shock-tagging step** that joins `vinu-stock-price` (price gaps,
volatility z-score spikes) with news events, producing a labeled set of "shock dates" per
symbol — nothing in the codebase currently defines what counts as a shock or cross-references
these two sources.

The fields this phase produces:

- `gap_fill_rate` — how often, and how much, a gap closes within N sessions after a shock.
- `vol_persistence` — derived from Phase 1's fitted GARCH/EGARCH persistence parameter for this
  symbol, not a separately hand-rolled decay estimate, so this angle and Phase 1's live risk
  numbers never disagree about how "sticky" the symbol's volatility is.
- `drift_persistence_days` — how long a post-shock directional drift tends to last.
- `shock_cluster_membership` — which *other* symbols this one tends to shock together with,
  derived from Phase 1's dynamic covariance sampled specifically at shock dates (a symbol's
  normal-day correlation to its sector and its shock-day correlation can differ meaningfully).

Every field carries a sample size and confidence interval, never a bare point estimate — a
symbol with two historical shocks does not have a reliable "personality" yet, and the schema
must make that visible rather than hide it behind a confident-looking number.

## Impact

**Before this phase:** Initial-Analysis's `regime_analysis`, `drawdown_deep_dive`, and
`event_study_methodology` angles characterize historical distributions and events, but nothing
answers "how does this specific symbol behave in the window right after a shock" or "which other
symbols tend to move with it when a shock hits."

**After this phase:** Research-Simulations (Phase 4) can query these angles the same way it
already queries `trend_lifecycle`/`trend_session_structure`/`news_price_causality` via
`angle_context.py`, and use them as real features for both the forecast and the trade-plan's
risk bands — instead of the LLM guessing at a symbol's behavioral tendencies from raw price/news
context alone.

**What still won't work after this phase alone:** These are descriptive statistics, not a
forecast or a trading decision — turning them into "which way tomorrow" is Phase 4's job, and
using `shock_cluster_membership` to actually limit exposure is Phase 5's job.

## Where changes occur

- New folders under `vinu-initial-analysis/vinu_initial_analysis/angles/` (e.g.
  `shock_personality/`, `shock_clustering/`), each with `spec.yaml` (including `time_formats`,
  matching existing angles) and `compute.py` calling into Phase 1's `vinu-tools` risk formulas.
- No changes to `runner.py`'s discovery mechanism — new angles are picked up the way any new
  angle folder already is.
- Read-side dependency on `vinu-stock-price` and news data, exactly like existing angles
  (`news_first_analysis`, `news_price_causality`) already consume both.

## Why we need this

This is the direct implementation of "the market has a personality, we're saving memory, trying
to find the after-shock movements" — done as new angles in the package built for exactly this
kind of per-symbol characterization, rather than as a new, disconnected memory system. Deriving
`vol_persistence` from Phase 1's GARCH fit (rather than a separate heuristic) and requiring a
confidence interval on every field also directly answers the overfitting risk flagged earlier in
this vision: a handful of shock observations isn't a real personality any more than a handful of
lucky backtests is a real edge, and the schema is designed to make that visible instead of
hiding it.

## How to test it

- Unit test: seed synthetic shock events for a symbol, confirm `gap_fill_rate`/
  `drift_persistence_days` compute correctly against hand-derived expected values.
- Cross-check test: confirm `vol_persistence` matches Phase 1's GARCH persistence parameter for
  the same symbol/window exactly — any divergence is a bug, not an acceptable difference in
  estimation method.
- Low-sample test: a symbol with only 1–2 shock events produces an explicit "insufficient
  sample" marker or a wide confidence interval — never a confident-looking point estimate.
- Cluster-membership test: seed synthetic shock events across a basket of symbols where a subset
  moves together on shock dates only (not on normal days); confirm `shock_cluster_membership`
  identifies that subset and excludes symbols that only correlate on non-shock days.
- Join-correctness test: shock-tagging output matches manually-identified shock dates for a
  handful of known historical events (e.g. a known earnings gap) in existing price/news
  fixtures.
