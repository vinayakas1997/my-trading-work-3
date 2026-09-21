# End-to-end verification plan — expected behavior at each real stage

## What this file is

A checklist to run *before* trusting a full end-to-end run (main
docker-compose stack + a real simulation/backtest + the Hindsight stack).
Each stage below states what should concretely happen, in terms of real
files/fields you can go check yourself — not a vague "should work."
Anything observed that doesn't match a stage's "Correct" line is a real
bug to chase, not a formatting nit.

Every claim below was checked against real code on 2026-09-21, not
assumed from the design docs. Where something the design *assumed*
doesn't actually exist, that's called out as a **Gap**, same convention
`02-decided-pattern/25-A-Y-details/07-implementation-plan-status.md`
already uses.

Status as of 2026-09-21: this is a **plan**, not yet executed. Run it in
order — each stage's data feeds the next (ticker discovery → analyses
have something to read → context building has a summary to build →
authoring has context to use → simulation exercises the whole thing).

---

## Stage 1 — Ticker discovery / filtering at system start

**Real files**: `vinu-screener/vinu_screener/rankers/seed.py`
(`build_core_starter_config`, `seed_default_ranker`),
`vinu-screener/vinu_screener/pipeline/hard_filter.py`
(`HardFilterConfig`, `passes_hard_filter`),
`vinu-agent/vinu_agent/tools/screener_client.py`
(`fetch_screener_top_tickers`),
`vinu-agent/vinu_agent/agent/scheduler_workers.py`
(`discover_new_tickers`, `bootstrap_new_tickers`), `vinu-agent/vinu_agent/
cli.py`'s `planner_worker_main`.

**What actually happens**: the only built-in ranker is `core_starter` —
seeded once from a hardcoded 50-symbol large-cap universe (or a JSON
override at `VINU_SCREENER_SEED_CONFIG`). Its hard filter is
`min_price=5.0, min_dollar_volume=1_000_000.0` — nothing else is set,
even though the config supports more. Factors: 10-day momentum (weight
5.0), 30-day momentum (weight 3.0), a small RSI-extreme penalty
(weight -0.01). Top 20 pass through. A ticker only enters the agent's
watchlist via `discover_new_tickers`: the union of the static
`VINU_AGENT_WATCHLIST_SEED_TICKERS` env list and, if
`VINU_AGENT_SCREENER_RANKER_ID` is set, the screener's ranked top-N.
`bootstrap_new_tickers` then runs the real `screener` LLM team once per
new ticker to write its first `TickerSummaryStore` row.

**Correct**: watchlist = seed list ∪ screener's hard-filtered top-N; no
ticker under $5 or under $1M dollar volume ever appears.

**Wrong**: a sub-$5 penny stock in the watchlist (hard filter bypassed);
the watchlist staying empty despite `core_starter` having real ranked
candidates (check `VINU_AGENT_SCREENER_RANKER_ID` is actually set —
ships inert/empty when unset, which is correct-but-easy-to-mistake-for-broken).

**Gap, real, not fixed here**: there is no deterministic outside/web
cross-check of a filtered ticker. `WebSearchTool`/`NewsTool` are real and
callable, but only *inside* the `screener` LLM team's bootstrap run —
whether a ticker gets cross-checked against outside data depends on
whether the LLM chooses to call them that run, not a guaranteed filter
step. Don't expect "does this match outside reality" to be a
deterministic pass/fail here — it's LLM-discretionary, at best.

---

## Stage 2 — The 24 reflection analyses store facts correctly

**Real files**: `vinu-reflection/vinu_reflection/cli.py` (`ANALYSTS`,
`run_cycle`), `vinu-infra/reflection.py` (`Finding`, `write_finding`,
`ReflectionStore`).

**What actually happens**: `run_cycle` calls every analyst's
`run(data_root_paths, service_clients)` with per-analyst exception
isolation, then `write_findings`. `write_finding` only persists a row
when `classify_severity(psi, domain_floor_breached)` returns non-None
(PSI ≥ 0.1) — **most cycles produce nothing, on purpose**. A quiet cycle
is not a bug.

**Correct**: for any analyst that *should* have fired (real drift
present in its source data), `ReflectionStore.get_belief(analyst_name,
scope_type, scope_key)` returns a row with `computed_at` from the latest
cycle, `primary_metric` matching the real computed delta, and `trend`
set relative to the prior belief (`"stable"` only if no prior belief
existed).

**Wrong**: a belief stuck at an old `computed_at`/`primary_metric`
despite new source data clearly existing (the analyst silently failed —
check the worker's own exception log, `run_cycle` swallows per-analyst
errors); or a `severity` populated despite PSI < 0.1 (would mean
`classify_severity`'s dead zone was bypassed somehow — a real bug, not
expected behavior).

**How to check concretely**: after a cycle, query `reflection_beliefs`
for all 24 analysts' expected `(scope_type, scope_key)` pairs (see
`07-implementation-plan-status.md`'s per-analysis table for which
cluster each belongs to) and diff `computed_at` against the cycle
timestamp.

---

## Stage 3 — Context building / summary (vinu-agent)

**Real files**: `vinu-agent/vinu_agent/agent/scheduler_workers.py`
(`make_summary_agent_fn`, `run_team_for_ticker`),
`vinu-agent/vinu_agent/storage/ticker_summaries.py`
(`TickerSummaryStore`), `vinu-agent/vinu_agent/agent/
planner_triage_hook.py` (`PlannerTriage.check` — a separate,
deterministic gate, not part of context building itself).

**What actually happens**: `make_summary_agent_fn`'s inner function
fetches every angle deterministically (`GetAllAnglesTool` — never parsed
from LLM prose), builds an `angle_digest`, computes an angle-trust
overlay from real calibration accuracy, then runs the real `screener`
LLM team with a task string that explicitly names any low-trust angles
and their accuracy/n. Result is upserted into `TickerSummaryStore`. A
300s dedupe cache avoids redundant LLM calls for the same ticker.

**Correct**: `TickerSummaryStore.get_summary(ticker)` has non-empty
`summary` text, a populated `angle_digest` (JSON dict keyed by angle
name), `angles_with_data`/`angle_count` matching the real angle count
from vinu-initial-analysis, and — if any angle had accuracy below
threshold with enough closed attributions — the summary text names it.

**Wrong**: stale `updated_at`; empty `summary` (the LLM call itself
failed — check `result.get("status") == "completed"`); `angle_digest={}`
when angles clearly exist for that ticker.

---

## Stage 4 — Strategy authoring uses all real components

**Real file**: `vinu-research/vinu_research/trade_plan_authoring.py`,
`author_trade_plan()`.

**What actually happens**: every one of these is real, but individually
feature-flagged and **fails open silently** on any error — confirm the
relevant flag is on before expecting to see it fire:
- `summary_context` (Stage 3's output) → always folded into the forecast.
- `maturity_context` — only if `config.maturity_tier_enabled`.
- `current_regime` — feeds both the confluence vote and a separate
  `_regime_size_multiplier` applied to position size.
- Screener rank percentile — only if `config.screener_ranker_id` is set
  → `_screener_rank_size_multiplier`.
- `market_regime_analogue` — only if `config.regime_analogue_enabled`.
- Trade Score tier → `TIER_SIZE_MULTIPLIER`, also multiplies position size.

**Correct, concretely checkable**: `trade_score.reasons` literally
contains `"regime_size_multiplier=X.XX (regime=...)"` and
`"screener_rank_size_multiplier=X.XX (percentile=...)"` with **real,
non-placeholder values** (not `regime=unknown` / an unranked default) —
that's the ground-truth audit trail proving each channel actually fired,
not just existed as config. Final `risk_bands.max_position_size_pct`
should equal base size × tier multiplier × regime multiplier × screener
multiplier.

**Wrong**: any of these multipliers sitting at exactly 1.0 (neutral)
despite real regime/rank data existing for that symbol — check the
corresponding `logger.debug(... failed, continuing ...)` line for a
silent fail-open.

**Gap, not a bug**: a component missing from `trade_score.reasons`
because its flag is off is *expected*, not broken — check config before
treating an absent multiplier as a failure.

---

## Stage 5 — Simulation, and where its output actually lands

**Real files**: `vinu-simulator/vinu_simulator/cli.py` (`run_main`),
`vinu-simulator/vinu_simulator/service.py` (`SimulationService.simulate`),
`vinu-simulator/vinu_simulator/storage/results.py` (`ResultStorage.save`),
`vinu-simulator/vinu_simulator/storage/meta.py` (`MetaStorage.insert_run`).

**What actually happens**: `simulator run --strategy ...` (or `POST
/simulate`) pulls strategy weights + price/volume, runs
`WeightSimulator`, then persists three things: (1) `equity.parquet` /
`weights.parquet` / a trades parquet under
`{data_root}/simulations/{run_id[:2]}/{run_id}/`, (2) a
`simulation_runs` SQLite row (`MetaStorage`) with metrics/benchmark/
trade_count/`config_hash`, (3) a run-card summary file.

**Correct**: after a run, `simulator list`/`simulator metrics <run_id>`
shows a row with `trade_count > 0` (unless genuinely no trades
triggered) and the parquet files exist at the expected path.

**Wrong / easy to misread**: `config_hash` means an *identical* request
returns a cached prior run rather than re-simulating — if you expected a
fresh run and got old numbers back, check whether the config actually
changed, don't assume the engine is broken.

**Important scope correction — read this before checking anything
"stored in Hindsight"**: `trade_audit_log`/`decay_snapshots`/
`calibration_entries` are **not** vinu-simulator concepts at all — they
belong to the real-trading/paper-trading audit path
(`vinu-infra/trade_audit_log.py`, `vinu-agent`'s `order_guard.py`/
`kill_switch.py`, and various `vinu-reflection` analysts), not the
backtest engine. And **Hindsight has no real integration anywhere in
this codebase yet** — confirmed via a full-repo grep: every "hindsight"
mention outside `hindsight-llm/` (an unrelated model-serving container,
not a retrospective-analysis service) is a forward-looking comment about
a future pipeline, not a real writer. **Nothing simulation output, or
anything else, currently pipelines into Hindsight.** Do not check for
this — there is nothing there to fail or pass. This is the step-8
brain/Hindsight-integration work this file's own earlier conversation
already scoped as a separate, not-yet-built pass.

---

## Running this plan

1. Bring up the main stack (`docker-compose.yml`) and let Stage 1 run at
   least one discovery cycle.
2. Let `vinu-reflection`'s worker run at least one cycle once Stage 1/2's
   prerequisite services have real data (Stage 2 needs Stage 1's
   watchlist to exist first for most analysts to have anything to read).
3. Trigger Stage 3 (a summary cycle) and Stage 4 (author a real trade
   plan) for at least one ticker, and check `trade_score.reasons`
   directly.
4. Run a real `simulator run` (Stage 5) and check `simulator metrics
   <run_id>`.
5. Do **not** check for a Hindsight write anywhere in this pass — see
   Stage 5's note above.

Log every deviation from a stage's "Correct" line as a real, numbered
finding — cite the file/field you checked, same as every entry in
`02-decided-pattern/25-A-Y-details/07-implementation-plan-status.md`
does. Don't note "seems fine" without having actually read the field.
