# Cluster 2 — Regime & Risk Coverage: B, E, N, V

See `00-index.md` for the four-part format and the "no hand-picked
numbers" rule every Condition below follows.

---

## B. Regime × strategy coverage map

**Source stores**: `artifacts.regime_tag`, `artifacts.type` /
`signal_definition` (used to derive `strategy_family`) ·
`bench_history` (`ic, ir, ic_positive, sharpe`) · `decay_snapshots` ·
`trade_audit_log.jsonl` entries (realized outcomes).

**Fetch**: cross-tab `strategy_family` (derived from `artifacts.type`)
× `regime_tag` × outcome (`realized_pnl` sign, `sharpe`), across every
artifact.

**Condition**: a `(strategy_family, regime_tag)` cell's `evidence_count`
crosses from below a minimum real-sample floor (e.g. <5 real closed
trades) to above it for the first time (newly covered) — **or**
`sharpe`/`ic` for that cell moves outside its own trailing band (newly
degraded or newly improved coverage quality), computed fresh from
`bench_history`/`trade_audit_log.jsonl` every cycle.

**Storage**: `scope_type=strategy_family`, `scope_key=strategy_family`
(regime breakdown nested inside `signal_json`:
`{regime_tag: {n, sharpe, ic}}`). `evidence_count` = total real trades
across all regimes for this family.

**Manageability**: bounded by the number of strategy families (small,
fixed), independent of watchlist size — **not** per-ticker. A consumer
wanting a per-ticker answer joins at read time: look up which
`(strategy_family, regime_tag)` a candidate ticker matches, then read
B's belief for that cell.

**Not attempted, 2026-09-19 — needs a new categorical scheme first.**
Grepped the whole codebase for `strategy_family`/`family`: no such
categorical concept exists anywhere. `Artifact.type` is a coarse
artifact-kind flag (`"strategy"`/`"trade_plan"`/etc, not a style
taxonomy); `signal_definition` is free text, not categorical. Building
B would mean inventing a brand-new classification scheme (e.g.
keyword-parsing `signal_definition`) from scratch, not reading one that
already exists -- a different, bigger decision than the "drop the field
that has no real substitute" scoping-downs already applied to C/H. Left
for a dedicated design pass, not silently invented here.

---

## E. Cross-package systemic risk (correlation + concentration) — the one real scaling risk in the whole set

**Source stores (pair piece)**: `CorrelationMonitorStore`
(`vinu-live/trade_plan/correlation_monitor_store.py`:
`correlation_monitor_history` — `checked_at, n_flagged, flagged JSON,
reductions JSON`), restricted to pairs where **both** symbols are
currently in vinu-live's `open_positions`.

**Source stores (concentration piece)**: `AllocationHistoryStore`
(`vinu-portfolio/storage/allocation_history.py`: `allocation_history` —
`weights JSON` incl. per-strategy `vol_annualized`, `sleeves JSON`) ×
`decay_snapshots` for regime cross-reference.

**Fetch (pair)**: for each pair of symbols **both currently held**
(never the full watchlist — see Manageability), pull
`correlation_monitor_history`'s trend over the trailing N weekly checks.

**Condition (pair)**: pairwise correlation has increased across 3+
consecutive weekly checks by more than this pair's own trailing 8-week
P90 delta — computed directly from `correlation_monitor_history`'s full
unbroken raw history, **never** from `reflection_beliefs`'/
`reflection_findings_history`'s own already-gated rows (the rule fixed
in `../05-to-do.md` #3 specifically to stop this exact analysis's own
detection method from reintroducing the slow-boil blind spot it exists
to catch).

**Fetch/Condition (concentration)**: per sleeve, `vol_annualized` or
weight concentration (from `allocation_history`'s full daily series)
crosses that sleeve's own trailing P90.

**Storage (pair)**: `scope_type=ticker_pair`, `scope_key` a sorted pair
string (`"AAPL|MSFT"`). `signal_json`: `{correlation_trend,
weeks_climbing}`. `evidence_count` = # weekly checks in the climbing
streak.

**Storage (concentration)**: `scope_type=strategy_family` (or
`system`), `scope_key=sleeve_name`. `signal_json`:
`{vol_annualized_trend, weight_trend}`.

**Concentration piece built 2026-09-19**: `vinu-reflection/vinu_reflection/
reflection/concentration_coverage.py`. **Real data-shape correction**:
checked `AllocationHistoryStore`'s one real writer
(`vinu-portfolio/vinu_portfolio/service.py`'s `compute_daily_allocation()`)
— `sleeves` is `{style_tag: summed_target_weight}`, a real persisted
weight-concentration series; no per-sleeve `vol_annualized` is tracked
anywhere. Implemented against the weight-concentration signal (the
design doc's own "`vol_annualized` or weight concentration" already
anticipated this). New `vinu-portfolio` dependency + `./data/portfolio`
mount added to `vinu-reflection`.

**Manageability — read this one carefully**: a naive "check every pair
in the watchlist" is quadratic — 200 tickers is ~20,000 possible pairs.
**The mitigation, load-bearing, not optional**: scope pair-checks to
pairs the portfolio actually holds simultaneously, never the full
watchlist — typically 10–30 concurrent positions, so
`(portfolio_size choose 2)` instead of `(watchlist_size choose 2)`, a
difference of orders of magnitude. The concentration piece is separately
bounded by sleeve count (small, fixed) regardless.

**Pair piece built 2026-09-19**: `vinu-reflection/vinu_reflection/reflection/correlation_coverage.py`.
Concentration piece also built, same day (see its own entry below).
**Real data-shape correction found while implementing the pair piece**:
`correlation_monitor_history`'s `flagged` JSON list only ever contains a
pair's correlation value for cycles where that pair had already crossed
`runtime_corr_threshold` — a pair sitting below threshold leaves no
value in this store at all, so a pair's true continuous correlation
history (what "trailing 8-week P90" implies) can't be reconstructed,
only the sequence of already-flagged values. Implemented against that
real signal instead (most recent 3 flagged occurrences vs. prior up to
8, reusing the design's own numbers as occurrence-counts rather than
calendar weeks) — this **cannot** catch the literal "slow boil while
staying under threshold" scenario the analysis exists for; that would
need a new writer recording every pair's raw correlation every cycle,
not just flagged ones. Left as a real, documented gap, not silently
papered over. New `vinu-live` dependency added to `vinu-reflection`
(mount-and-import, same posture as vinu-agent) — no new docker-compose
mount needed, reuses the `/live-data` mount `loss_attribution.py`
already added for C.

---

## N. Kill-switch retrospective

**Source stores**: `safety_ledger.jsonl` (`vinu_agent/broker/audit_ledger.py`'s
`HashChainedLedger` — `seq, ts, event_type, payload, prev_hash, hash`)
for halt/emergency-flatten events · `shock_clustering`/`shock_personality`
angle result Parquet files · realized volatility from the OHLCV 1-minute
bar Parquet files.

**Fetch**: for each halt event timestamp in `safety_ledger.jsonl`, pull
`shock_clustering`/`shock_personality` readings and realized volatility
in the trailing window immediately before that timestamp.

**Condition**: `shock_*` readings crossed their own historical P90 in
the window before a halt that wasn't acted on until later — a
detectable-in-hindsight lead time exists. **Event-triggered, not
cycle-gated** — this only runs when a new halt event appears in the
ledger, not on a recurring schedule.

**Storage**: `scope_type=system`, `scope_key="kill_switch"`.
`signal_json`: `{halt_ts, lead_time_detected_hours,
shock_reading_at_lead}`. `evidence_count` = # halt events analyzed to
date.

**Manageability**: negligible volume — driven by rare real events, not
a cadence.

**Deferred, 2026-09-19 — not attempted this pass.** `safety_ledger.jsonl`
(`HashChainedLedger`, `vinu_agent/broker/audit_ledger.py`) is confirmed
real and genuinely append-only (hash-chained, fsync'd, a real reader
already exists) -- not the blocker. The blocker is the same one already
flagged for Q: `shock_clustering`/`shock_personality` angle results live
as Parquet files under vinu-initial-analysis, the one service too
dependency-heavy (torch/xgboost/chronos/timesfm) to mount-and-import the
way every other analyst in this service does. Building N would
reintroduce that exact cost. Worth a deliberate decision (a lightweight
Parquet-only reader that doesn't import the full package? a new
producer-side projection into the ticker-profile mechanism?) before
building, not a default.

---

## V. Paper-vs-live performance predictor

**Source stores**: `paper_performance` (vinu-agent,
`broker/performance_store.py`: `artifact_id PK, returns_json,
updated_at, meta_json`) × `trade_score_calibration_history.jsonl` /
`calibration_entries` realized returns for the same artifact
post-promotion.

**Fetch**: per `strategy_family`, correlate each promoted artifact's
trailing paper-period average return against its own subsequent
live-period average return.

**Condition**: the correlation coefficient across all promoted
artifacts in this `strategy_family` — recomputed each cycle from the
full history — moves outside its own trailing band, **or** crosses the
domain-meaningful line of `correlation ≤ 0` (paper performance predicts
nothing) for the first time, gated by a minimum-sample floor (e.g. ≥5
promoted artifacts) mirroring Shadow's own `min_paper_days`-style
gating philosophy.

**Storage**: `scope_type=strategy_family`, `scope_key=strategy_family`.
`signal_json`: `{paper_live_correlation, n_promoted_artifacts}`.
`evidence_count` = # artifacts with both paper and live history.

**Manageability**: bounded by the number of strategy families.

**Not attempted, 2026-09-19 — needs more investigation, not blocked.**
Checked `paper_performance` (`vinu-agent/vinu_agent/broker/performance_store.py`)
directly: PK is `artifact_id`, both `record_daily_returns`/`record_meta`
upsert on it, confirming it's overwrite-only (the full `returns_json`
accumulates under one row, but only a single last-write-wins
`updated_at` -- no per-return timestamps). No `promoted_at` marker
exists in this file, and a grep for a real promotion-timestamp field
elsewhere (`ArtifactStatus.ACTIVE` transitions in
`trade_plan_authoring.py`/`service.py`) found only inline `artifact.status
= ArtifactStatus.ACTIVE` assignments with no dedicated timestamp write —
`Artifact.updated_at` is the closest proxy but isn't exclusive to
promotion (other updates bump it too), so it's not yet clear this
cleanly splits "paper-period" from "live-period" returns. Also still
needs a real Pearson-correlation helper (nothing in this codebase
computes one yet — every analyst so far only needed PSI). Worth a
closer look before building, not attempted this pass.
