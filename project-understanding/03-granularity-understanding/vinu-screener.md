# vinu-screener

## What it is

Two related but distinct capabilities in one service: **rule-based
watchlist scanning** (condition-triggered alerts) and **universe
ranking** (a configurable-weight scored/sorted candidate list). Feeds
`vinu-agent`'s Telegram `/rank` command and (not yet wired into any live
trading decision — confirmed decoupled, see `vinu-research.md`'s "2 of
28 angles" finding for the analogous gap here) is not currently consumed
by `vinu-live`.

## Trigger / cadence

One process, `vinu-screener scan`, runs **two independently-scheduled
loops sharing one HTTP client**, deliberately not two separate OS
processes since neither is expensive enough alone to justify it
(`cli.py::scan_main`):

1. **Rule scheduler** (`scheduler.py::Scheduler.run_forever`, foreground)
   — condition checks, poll floor **30 seconds** (`--poll-sec`).
2. **Ranker scheduler** (`rankers/scheduler.py::RankerScheduler.run_forever`,
   background daemon thread) — full-universe multi-factor ranking, poll
   floor **300 seconds**, default interval **24 hours** (rank once at day
   start) — much heavier per cycle (fetches + scores the whole universe),
   so both the floor and the default are an order of magnitude coarser
   than the rule scheduler's.

A separate `vinu-screener serve` process runs the always-up HTTP API
(rule CRUD, on-demand rank, pairlist).

## Pipeline

**Rule-check cycle** (`Scheduler.tick()` → `ScanMonitor.run_cycle()`, per
active rule, every 30s+):
1. `CoarseFilter`/`coarse_select` — a cheap pre-filter over the universe
   before the expensive per-symbol fetch+evaluate (avoids paying full
   cost on symbols that can't possibly match).
2. `call_with_timeout`-guarded fetch — one HTTP call per symbol via
   `HttpStockDataSource` (`POST /stock/candles/batch` when available,
   chunked; falls back to per-symbol `GET` otherwise) against
   `vinu-stock-price`.
3. Warm-up check — a symbol without enough history yet is skipped, not
   force-evaluated on partial data.
4. `evaluator.py` — the actual condition evaluation: leaf conditions
   (crossing/level-touch/direction operators) combined via AND/OR,
   fails-closed on any unevaluable operand (an indicator that couldn't
   compute never silently passes).
5. `CooldownGate` — edge-gated (only fires on a transition into "true",
   not every cycle it stays true) + a configured cooldown before the same
   rule can fire again for the same symbol.
6. A fire is recorded to `WatchAuditStore` (permanent audit table) and
   dispatched via `rules/actions.py::resolve_targets` (fan-out to
   configured notification targets — never sends anything itself, just
   resolves who should be told).

**Ranker cycle** (`RankerRunner.run(ranker_config)`, per enabled ranker,
every 24h default):
1. Fetch the whole universe's OHLCV via the same batch-capable data
   source, one `IndicatorFactory.latest()` broadcast per configured
   factor across the whole universe (not per-symbol) — always carries
   price/volume/dollar_volume alongside whatever custom factors the
   ranker config declares (needed for `HardFilterConfig` downstream).
2. `pipeline/scorer.py::make_weighted_scorer(FactorSpecs)` — a
   declarative weighted sum over the fetched factors; this is the actual
   "set the ranks" configuration the user asked for (name/indicator/weight/
   params/output_field/offset per factor).
3. `ScreenPipeline.run()` (`pipeline/pipeline.py`), in exact order:
   - `FilterChain([HardFilterRule, RiskVetoRule])` — hard filter first
     (fail-closed reasons list), then a bounded additive-penalty risk
     overlay with an optional hard veto (`supports_backtesting: BIASED`,
     since some risk signals like LLM confidence have no guaranteed
     historical record).
   - Survivors get `factor_score` from the weighted scorer above (a bad
     scorer input drops just that one candidate, `-inf` score, never
     aborts the whole run).
   - `apply_concentration_overlay` — graduated sector/bucket concentration
     penalty (not a hard cap, a score penalty that grows with
     concentration).
   - Sort by `final_score` descending.
   - `near_score_rotation` — deterministic, seeded rotation among
     near-tied candidates at the cutoff, so the same tie doesn't always
     resolve the same way run after run.
   - Optional `apply_turnover_gate` (Qlib's `n_drop`/`hold_thresh`
     pattern) — holds a currently-ranked symbol in place unless the
     replacement's edge clears a threshold, damping churn; re-ranks
     within the held set using the pipeline's own score order (the gate
     only decides membership, not order).
   - Top-N enrichment (`enrich_fn`, only called for the final top-N, not
     every survivor) — enrichment failing drops just that symbol's extra
     fields, never the candidate itself from the shortlist.
4. `RankedSnapshotStore.set_latest(ranker_id, ...)` persists the result
   (score breakdown + raw `fields` — added specifically so `vinu-agent`'s
   `/rank` command has real indicator values to show, not just the
   score).
5. `record_ranking()` (`rankers/churn.py`) — the one shared path both this
   scheduled run and the on-demand `POST .../rank` route call — diffs
   against the previous snapshot: `entered`/`exited` events with 1-based
   rank positions. Reordering within unchanged membership is NOT churn. A
   ranker's first-ever run produces no events (no real prior state to
   diff against).

**On-demand** (`POST /screener/rankers/{id}/rank`) runs the same
`RankerRunner.run()` immediately, outside the schedule — used for a
manual re-rank; still goes through `record_ranking()` so it can't create
a gap in the churn history relative to the scheduled runs.

## Storage

- `RuleStore`/`RankerStore` (SQLite, CRUD + enable/disable) — rule and
  ranker configuration.
- `RankedSnapshotStore` — the latest ranked result per ranker (a read is
  never a re-run).
- `RankerChurnStore` — permanent entered/exited history.
- `WatchAuditStore` — permanent fired-watch history (separate from the
  live `CooldownGate`, shares no code with it — the live gate decides
  whether to fire again; the audit store just permanently records that it
  did).

## Talks to

- **Outbound**: `vinu-stock-price` only (`HttpStockDataSource`) — the
  whole `pipeline/` subpackage has zero imports from `vinu-agent`/
  `vinu-research`/`vinu-live`, a deliberately held decoupling boundary
  (confirmed still true as of the last check against Stage C's C1/C14/C19).
- **Inbound**: `vinu-agent`'s Telegram `/rank <ranker_id>` reads
  `GET /screener/rankers/{id}/latest`; `/track <TICKER>` doesn't call
  this service at all (goes straight to `vinu-news`/`vinu-stock-price`
  watchlists). `GET /screener/pairlist/{rule_id}` (bearer+TTL+fail-open)
  is the one other exposed read, mirroring Freqtrade's `RemotePairList`
  pattern, not yet consumed by anything in this codebase.
