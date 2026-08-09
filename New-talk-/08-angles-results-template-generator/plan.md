---
name: angles-results-template-generator-plan
status: built
purpose: plan for a deterministic (no-LLM) generator that turns each angle's real stored backtest rows into a plain factual document — every statement a bare "field = value (n=..., computed_at=...)" line, zero comparison/ranking/adjectives — so a future LLM agent reading it gets clean facts to reason over instead of pre-baked judgments.
---

# 08 — Angle Results Template Generator — Plan

## Why this exists

Every angle now writes real result rows through `AngleStorage`/`RunLog`
(see `07-orchestration-suite-test/`). The next gap: nothing turns those
rows into something a future *reading* agent can consume directly. The
instinct would be "have an LLM write a summary" — but that bakes in
judgment at write time ("ARIMA looked weak on TSLA") that the reading
agent can't undo, verify, or recompute from. The alternative decided here:
a plain, deterministic **fact sheet** generator — no LLM anywhere in this
path — that states every number literally, with its sample size, and
nothing else. Interpretation (is 0.54 good, which angle to trust more)
stays entirely with whatever agent reads the fact sheet later, using its
own skill/prompt at that time. This keeps the fact layer stable and
re-usable across however many different future reasoning passes want to
read it, instead of re-baking one reading's opinion into the record.

## The core rule

> A fact sheet may only ever say `{field} = {value} (n={n}, computed_at={ts})`.
> Never a comparison, a ranking, a qualitative word ("weak", "strong",
> "good", "better than"), or an implied recommendation.

Analogy the rule is named after: "apples were found at the cost of 12
dollars" — a bare fact, not "apples were expensive."

## Two ways a fact sheet could quietly lose this property, and the fix for each

1. **Comparative/qualitative language creeping into the sentence
   template.** Fixed by keeping the sentence generator a pure
   string-interpolation template (name, value, n, timestamp only) — there
   is no code path that branches on the *value* to pick a word, so there's
   nowhere for "weak"/"strong" to enter. Enforced, not just designed:
   every generated document is run through a banned-word check
   (`good|bad|weak|strong|better|worse|outperform|underperform|best|worst|
   improve|decline|...`) before being returned — if the check ever fires,
   generation fails loudly rather than silently shipping judgment-language.
2. **Comparison-by-omission** — quietly picking which fields to show
   (e.g. showing `hit_rate` but not `baseline_hit_rate`) is an editorial
   framing even with zero adjectives. Fixed with a **field manifest**: one
   fixed, exhaustive list of fields per angle, written once against that
   angle's actual real stored schema (not decided ad hoc at generation
   time), and checked against the real DataFrame's columns at generation
   time — if a run's actual columns contain a field the manifest doesn't
   know about, generation fails loudly instead of silently dropping it.
   This also catches schema drift: if an angle's own backtest code grows a
   new column later, the fact sheet build breaks until the manifest is
   updated, instead of quietly falling behind.

## What "not losing structure" also requires

- **Reuse each angle's own already-validated grouping**, not new slicing
  invented here. E.g. ARIMA's own `02-real-scenario.md` already proved
  `query_slice(df, ["day_of_week"], {"ci_coverage": ("hit", "mean")})`
  matches a hand-written pandas groupby exactly — the fact sheet reuses
  that exact grouping, not a new one picked now.
- **`n` is never optional.** `query.query_slice()` already always attaches
  `n` (see `storage/query.py`) — every aggregate line in a fact sheet
  carries it for free, so a thin slice can never silently look as
  trustworthy as a well-supported one.
- **Fixed document order.** Angles are always listed in one fixed order
  (registry order — see `orchestration_registry.ANGLE_REGISTRY`), never
  "best first" or any other value-derived order, since ordering itself can
  read as an implied ranking to a future agent.
- **One fact sheet = one real run.** A fact sheet is generated from one
  `(symbol, angle_name, granularity, tier)` real run resolved through
  `RunLog.get_latest_run()` — the same "latest" resolution rule every
  other part of this project already uses (never picked by file mtime).
  No angle's fact sheet ever references another angle's numbers inline —
  cross-angle comparison is exactly the thing this format refuses to do.

## Where this lives, and why

| Piece | Location | Why |
|---|---|---|
| Field-manifest data + banned-word list | `vinu-initial-analysis/vinu_initial_analysis/storage/_factsheet_manifests.py` (new) | Pure data, no logic — kept separate from the generator so adding an angle's manifest later never touches generator code. |
| Fact sheet generator | `vinu-initial-analysis/vinu_initial_analysis/storage/factsheet.py` (new, sibling to `query.py`/`parquet.py`/`meta.py`) | Directly consumes `RunLog` (run metadata) + `AngleStorage` (result rows) + `query.query_slice` (grouped aggregates) — the same three modules `query.py` itself already sits next to and depends on. |

A generator function returns a plain string (markdown) — it does not
decide where to write it. Callers (a CLI, the orchestrator, a future
batch-report step) decide the destination; this keeps the function itself
trivially unit-testable byte-for-byte against fixture input.

## Build order

1. **Phase 1 — prove the mechanism on one angle, for real.** ARIMA, for
   the same reason it was documented well first elsewhere in this project
   (real, fully validated `02-real-scenario.md` with an exact worked
   example and an already-proven `day_of_week` grouping to reuse
   directly). Build:
   - `FieldSpec` (name, source column, kind: `"value"` for run-level
     metadata, `"mean"` for a numeric field to average via `query_slice`,
     `"count_by"` for a categorical/status field to tally).
   - `FIELD_MANIFESTS["arima"]` — every real field from ARIMA's actual
     output row (`symbol`, `timeframe`, `bar_ts`, `step_index`, `session`,
     `subsession`, `day_of_week`, `week_of_month`, `month`, `quarter`,
     `status`, `n_observations`, `order`, `aic`, `forecast`,
     `confidence_interval`, `confidence_level`, `actual_price`, `hit`,
     `abs_error`, `squared_error` — confirmed against
     `06-implementation-of-each-angles/01-arima/02-real-scenario.md`'s
     actual worked JSON row, not guessed).
   - `generate_factsheet(symbol, angle_name, granularity, tier, run_log,
     storage, group_cols)` — resolves the real latest run, reads the real
     stored rows, emits run-level facts + grouped field facts, runs the
     banned-word check, returns the markdown string.
   2. **Prove it for real**: run a real ARIMA backtest against real cached
      AAPL bars (`vinu-components/data/stock-price`, the same real 1-minute
      archive `LocalPriceClient`/every other real-data pass in this project
      already reads), write it through `AngleStorage`+`RunLog` for real,
      generate its fact sheet, and show the actual output.
3. **Phase 2 (explicit follow-up, not done in this pass)** — extend
   `FIELD_MANIFESTS` to the remaining 29 registry entries, one at a time,
   each grounded in that angle's own real-scenario doc's actual output
   shape, same discipline as phase 1. Not attempted here — pretending
   broader coverage than what's actually built and proven would repeat the
   exact mistake this project has caught and corrected before (see
   `07-orchestration-suite-test/plan.md`'s classification-correction
   story).

## What this deliberately does not do

- **No LLM anywhere in this path.** The whole point is a stable,
  re-derivable fact layer a future LLM agent can read — generating it
  *with* an LLM would reintroduce the exact variability/judgment problem
  this is meant to remove.
- **No cross-angle or cross-symbol comparison inside one fact sheet.**
  Each fact sheet is scoped to one real run. Any future "compare angle X
  vs Y" reasoning is a job for whatever agent reads two fact sheets later,
  not something baked into either document.
- **No recommendation, verdict, or "is this good" framing anywhere.**
  Reinforced by the banned-word check, not just a style guideline.

## Verification plan

- Unit tests for `factsheet.py`: fixed fixture rows in, exact expected
  markdown string out (byte-for-byte, since the generator is pure/
  deterministic); a manifest/column-mismatch test (extra real column not
  in the manifest raises); a banned-word-check test (a deliberately
  injected judgment word in a field's raw string value must still trip
  the check, proving the check runs over the *rendered* text, not just
  the template).
- Real end-to-end proof: real ARIMA backtest on real AAPL bars, real
  storage/RunLog round-trip, real generated fact sheet shown in
  `01-implementation.md`.
- Full `vinu-initial-analysis` test suite run after, confirming zero
  regressions, before calling phase 1 done.

## Update — phase 5: a real, explicit, shared date range

Every prior real run's date window (e.g. "2022-05-25 to 2022-10-17") was
never a deliberate choice -- each stage script called `fetch_candles(...,
limit=N)`, and `limit` returns the **first** N bars from the real
archive's earliest date, not the most recent N (confirmed directly
against `vinu_stock/query/engine.py`). Replaced with an explicit,
version-controlled `date-range.txt` (plain `key=value` lines) plus a tiny
`read_date_range.py` reader, both in this folder -- every stage script now
calls `fetch_candles(from_ts=..., to_ts=...)` with the same real dates
instead of guessing via `limit`. One real bug surfaced while wiring this
in: the first real value picked for `chronos_kronos_end_date` (2023-04-01)
only covered 313 real trading days, under the 512 chronos/kronos need
before their first real forecast -- confirmed by a real run producing zero
files for both angles, not a silent guess. Fixed by querying the real
archive directly for the actual date of its 560th real trading-day bar
(2024-03-26, matching the real step count -- 44 -- the original proven
run already used) and correcting the file. All 6 stages rerun end to end
against the corrected real dates; `real_factsheets/` holds the current
output.

## Update — phase 4: calendar-tag + horizon-step breakdowns, one real bug fixed

An audit against all 31 real design docs in `04-enhancement-of-each-angle/`
found the fact sheet was silently missing two things every angle's own
doc promises: a day/week/month/quarter breakdown (universal), and a
per-horizon-step breakdown for the 7 angles that store a nested
`predictions` dict (Chronos/Kronos/lag_llama/moirai/moment/
timer_timerxl/timesfm) -- their real headline result (accuracy decay as
horizon extends) was sitting in storage but never rendered. Worse: for
every angle except ARIMA (which has a hand-written manifest), the audit
found `month`/`quarter`/`week_of_month` were being silently averaged into
meaningless numbers by the generic column classifier -- confirmed in real
output, e.g. `month=7.69` in a real generated `garch.md`. All three are
fixed: `month`/`week_of_month`/`quarter` now classify as tags, never
means; a "Breakdown by calendar tag" section groups the same fields
already shown in the session table by real day/week/month/quarter instead
(only real observed values become a row, never a fabricated placeholder);
a "Breakdown by forecast horizon step" section unnests `predictions` (via
`query.unnest_predictions`, already built for this) and groups by
horizon. All 28 fact sheets were regenerated for real; `real_factsheets/`
holds the current output. 3 new tests, 16/16 passing in `test_factsheet.py`,
zero regressions in the full suite (480 passed, 2 skipped).

## Update — phase 3: real API route + real run across 28 of 30 angles

`GET /v1/stage1/vinu-initial-analysis/factsheet/{ticker}/{method}` is
real and proven (byte-for-byte match against the on-disk file). A real
batch run across 28 of the 30 registry entries (real AAPL data, 6 staged
batches) is done -- see `01-implementation.md`'s "Phase 3" section for
the 4 more real bugs this surfaced and fixed, and `real_factsheets/` for
every real generated document. The 2 not included
(`trend_session_structure`, a real pre-existing spec.yaml mismatch;
`news_price_causality_aggregate`, a real empty-result outcome on this
data window) are flagged, not silently skipped.

## Update — phase 2, built for real

After phase 1 (below), discussing the actual document shape with the user
settled on something different: `format.md`'s self-contained paragraph +
market-session x time-format table, not phase 1's per-line layout. Building
that generically for all angles (not just ARIMA) is done — see
`01-implementation.md`'s "Phase 2" section for the real build record, the
real bugs found (a `spec.yaml` encoding corruption, the banned-word check
too broad for quoted methodology text, and the batch orchestrator never
persisting results at all), and the real proof (6 real jobs, 2 symbols x 3
angles, real files on disk). This is now the current, real generator.

## Closing note — phase 1 done

`storage/factsheet.py` + `storage/_factsheet_manifests.py` built, proven
against a real ARIMA run on real AAPL data (100 real rows, real
storage/RunLog round-trip, real generated fact sheet — see
`01-implementation.md` and `real_arima_aapl_1D_factsheet.md`), and both
structural risks this plan named (qualitative-language creep,
comparison-by-omission) have a real enforced guard: a banned-word check
run over the fully rendered text (including text arriving through real
row data, not just the template — proven directly), and an
unmapped-real-column check that raises rather than silently drops. 10
new unit tests, all passing. Phase 2 (manifests for the other 29
registry entries) is explicit future work, not attempted here.

## Related files

- `01-implementation.md` — the real build record, real proof, and 2 real
  bugs found while building this (including the check catching its own
  first-draft disclaimer sentence).
- `real_arima_aapl_1D_factsheet.md` — the real generated output.
- `07-orchestration-suite-test/` — the registry and real per-run storage
  this generator reads from.
- `05-storage-enhancement-levels/plan.md` — rule 4 ("every rate/average
  carries its `n`") this generator inherits directly via `query_slice`.
- `06-implementation-of-each-angles/01-arima/02-real-scenario.md` — the
  real worked example `FIELD_MANIFESTS["arima"]` is grounded in.
- `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/storage/query.py` — the aggregation layer this reuses, not reinvents.
