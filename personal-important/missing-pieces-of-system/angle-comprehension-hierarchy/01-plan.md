# Angle comprehension hierarchy — implementation plan

Ordered so each step is independently useful and testable — not a
big-bang rewrite. Every file referenced here is real, already read
directly (see `00-explanation.md`). Status markers: **TODO** (not
started), used throughout since nothing in this folder is built yet.

## Step 1 — the per-angle glossary data (DONE)

Condensed `angles.yaml`'s `title` + `purpose` into one short blurb per
angle, capped at **~50 words**, not uniformly — a published,
recognizable architecture (`patchtst`, `lstm`, `arima`) got far less
(~15-20 words) than a proprietary/opaque name (`shock_personality`,
`tips_regime_aware_transformer`) where the full ~50 was warranted.

Built: `vinu-agent/vinu_agent/tools/angle_glossary.py` —
`ANGLE_GLOSSARY: dict[str, str]`, all 28 real angle ids, plus a fail-open
`explain_angle(name)` lookup function (an unknown angle gets an honest
"no glossary entry yet" message, never a guess). Source material was the
condensed blurbs already drafted in `angle-reference/*.md` during the
earlier grounding pass, not re-derived. Tested:
`vinu-agent/tests/test_angle_glossary.py` (all 28 ids covered, no empty
blurbs, unknown-angle fails open) — 5 tests, all passing.

## Step 2 — an on-demand `explain_angle` tool, not an always-injected block (DONE)

Per the earlier tool-calling-vs-static-injection discussion: a new
`BaseTool` in `angles_tool.py`, `ExplainAngleTool` (same pattern as the
existing `GetAllAnglesTool`), taking one or more angle ids and returning
their glossary blurbs from step 1. Registration is fully automatic
(`vinu_agent/tools/__init__.py::build_registry` auto-discovers every
`BaseTool` subclass in the `tools/` package) — the only real wiring
needed was adding `explain_angle` to the `tools:` list in both
`teams/screener/agents/angle_synthesizer/AGENT.md` and
`teams/research/agents/idea_generator/AGENT.md` (idea_generator also
calls `get_all_angles`, so it's a real second consumer, per
`research/manager_prompt.md`). Both specialists' `prompt.md` files also
got one line telling them when to actually call it — only for an angle
whose name isn't already clear, not for all 28 every time — so the
"genuinely on-demand" design intent is followed, not just possible.

Genuinely on-demand, confirmed: the model only pays the token cost when
it calls this, e.g. for an angle it doesn't already recognize — no
static always-present glossary block bloating every prompt. Tested:
`vinu-agent/tests/test_angle_glossary.py`'s `TestExplainAngleTool` (5
tests: multi-angle request, bare-string input, unknown angle fails open,
empty list, real `BaseTool` auto-discovery shape) plus a direct
end-to-end check that `build_registry()` → `subset([...,
"explain_angle"])` → `execute("explain_angle", ...)` resolves correctly
against `angle_synthesizer`'s real tool list — all passing.

## Step 3 — teach `angle_synthesizer` the 3-tier process (DONE — prompt half)

Updated `vinu-agent/teams/screener/agents/angle_synthesizer/prompt.md`
and `vinu-agent/teams/screener/manager_prompt.md`:

1. ~~Call `explain_angle` for any angle whose name/purpose isn't already
   clear~~ — already done in step 2's pass (`prompt.md`'s existing
   Rules section).
2. Group the angles that do have data into the 7 real clusters from
   `00-explanation.md` section 3 — done, the fixed A-G mapping (every
   real angle id assigned) is now stated directly in `prompt.md`'s new
   "Cluster synthesis (Phase 9)" section, not re-derived per ticker.
3. Cluster B (the 14-member deep-learning cluster) specifically
   instructed to report a consensus rate, not 14 individual
   descriptions — done.
4. `angle_synthesizer` now emits its own `cluster_digest` JSON block in
   its final answer; `manager_prompt.md` was updated to forward it
   **verbatim** into its own per-ticker JSON (same "never invent a
   number" discipline `angles_with_data` already uses) — done.

**Not testable by pytest** — these are prompt-content changes, not
executable code. Real verification is a checkpoint trial against a live
LLM (`vigrous-llm-testing/checkpoints/02-checkpoint-screener/`), still
blocked on the same container work tracked in that folder's README.

## Step 4 — persist `cluster_digest` (DONE, 2026-09-22)

Real discovery while implementing step 3, worth being explicit about:
**`cluster_digest` cannot reuse `angle_digest`'s exact plumbing.**
Traced the real write path (`scheduler_workers.py::make_summary_agent_fn`,
`ticker_gate.py::RunLogTrigger.refresh_if_stale`,
`screener_summary_writer.py`) and confirmed `angle_digest` is computed
by **pure deterministic Python** (`build_angle_digest`, a dumb
scalar-field copy) *before* the LLM team even runs — it never touches
the team's own output. `cluster_digest` is the opposite: it only exists
inside the LLM team's final JSON (`angle_synthesizer`'s per-cluster
synthesis, forwarded by the manager) — there's no deterministic
shortcut for it, the reasoning is the whole point.

Real Step 4 work actually done, both real persistence paths, not just a
column add:
1. `TickerSummaryStore` (`vinu-agent/vinu_agent/storage/
   ticker_summaries.py`) — two new columns (`cluster_digest`,
   `cross_cluster`), `SCHEMA_VERSION` bumped 3→4, both round-trip through
   `TickerSummary`/`from_row`/`upsert_summary`, same precedent as
   `angle_digest`.
2. **Path A** (`screener_summary_writer.py::write_ticker_summaries`,
   called from `team.py` after a batch screener run) — already parsed
   the manager's JSON block for `summary`/`angles_with_data`/
   `angle_count`; now also extracts `cluster_digest`/`cross_cluster` per
   ticker and passes them to `upsert_summary`. Also now calls
   `cluster_digest_validator.validate_cluster_digest` and logs (warn
   only, never blocks) any finding — the first real wiring of that
   guardrail, per `03-real-llm-findings-and-guardrails.md`'s "Future
   steps" #2 (the failure *policy* — drop vs. retry vs. persist-anyway —
   is still open; warn-only was the safe default chosen so persistence
   isn't silently correct-looking with the finding invisible).
3. **Path B** (`scheduler_workers.py::make_summary_agent_fn`, the
   single-ticker staleness-refresh path) — `_fn` had no JSON-block
   parsing at all before (only `angle_digest`, which is deterministic,
   from `build_angle_digest`, never LLM-parsed); now also parses
   `result.get("content", "")` for this one ticker's `cluster_digest`/
   `cross_cluster` and returns them in `meta`.
   `ticker_gate.py::RunLogTrigger.refresh_if_stale` threads both through
   to `upsert_summary`, same way `angle_digest` already did.

Tested: 140 tests passing across the touched/new files (`test_ticker_
summaries_storage.py`, `test_screener_summary_writer.py`,
`test_scheduler_workers.py`, `test_ticker_gate.py`, plus the
angle/cluster files from step 3), verified in a throwaway venv; full
1258-test suite run showed the same 25 pre-existing failures (unrelated
files, real network/service dependencies) both before and after this
change, zero new failures, +13 passing (the new tests).

## Step 5 — wire it into `forecast_skill`'s actual prompt (DONE, 2026-09-22)

Real code, both real assembly points and the prompt itself:
- `vinu-agent/vinu_agent/tools/trade_plan_tool.py::_read_summary_context`
  — now also reads `cluster_digest`/`cross_cluster` off the stored
  `TickerSummary` row (this function had no test coverage at all before
  this change — a real pre-existing gap; added `test_read_summary_
  context.py`, 5 tests, to close it while touching it).
- `trade_plan_authoring.py::_normalize_summary_context` — carries
  `cluster_digest`/`cross_cluster` through, with new `_bound_cluster_
  digest` (capped at the real 7 clusters) and `_bound_cross_cluster`
  (list fields capped at 10) — same defense-in-depth re-bounding
  discipline as `_bound_angle_digest`, alongside (not replacing) today's
  `angle_digest`.
- `forecast_skill.py::_build_forecast_prompt` — renders a new
  `=== Cluster Digest ===` section (one line per cluster) and, when
  present, a `=== Cross-Cluster Analysis ===` section (corroborations +
  redundant clusters), both appearing *before* `=== Angle Digest ===`
  which stays exactly as it was. Risk State/Personality Features
  sections untouched — never the problem, per every trial in checkpoint
  01.

Tested: 21 new tests across `test_forecast_skill.py`
(`TestBuildForecastPromptClusterDigest`), `test_trade_plan_authoring.py`
(`TestNormalizeSummaryContextClusterDigest`), and the new
`test_read_summary_context.py`. Full vinu-research suite run (excluding
14 files needing an unrelated, unavailable `vinu_simulator` package):
711 passed, 9 pre-existing failures confirmed unrelated (none touch
`forecast_skill.py`/`trade_plan_authoring.py`).

**Transition note honored**: both `angle_digest` and `cluster_digest`
flow in parallel now (real code confirms this — see the
`test_cluster_digest_and_angle_digest_both_present_when_both_given`
test) rather than the flat digest being deleted — lets checkpoint 01's
trials (step 6) compare forecast quality with each shape present,
instead of trusting the new shape is better without a real before/after.

**Real mid-implementation finding, also fixed the same day**: testing
step 5 against trial 04's real injection payload (see Step 6 below)
found that `manager_prompt.md`'s own assembly instructions only forward
each cluster's `synthesis` sentence into `cluster_digest`, silently
dropping the `anomalies` list `angle_synthesizer` already produces —
confirmed live: the Cluster E synthesis correctly flagged the injection
as an anomaly, but that flag never would have reached `forecast_skill`
at all under the original Step 3/4 design. Fixed same session: a new,
separate `cluster_anomalies` field now threads through every layer
(`manager_prompt.md` → `TickerSummaryStore` → both persistence paths →
`_normalize_summary_context` → `_build_forecast_prompt`, which renders
each as an explicit `FLAGGED ANOMALY in Cluster X: ...` line plus a new
system-prompt rule instructing the model to distrust a flagged
cluster's numbers). See Step 6 for whether this mitigation actually
worked when re-tested — it did not.

## Step 6 — prove it with the existing checkpoint trials (DONE, 2026-09-22 — mixed real result)

**Trial 04 re-run for real (2026-09-22) — done, critical finding, NOT
fixed.** Ran the exact real `_build_forecast_prompt` function (not a
hand-copy) with a **real** Cluster E synthesis captured live from the
9B model given trial 04's injected data. Real result: **CRITICAL
FAIL, confirmed again.** The forecast still matched the injected
payload exactly (`direction=long, confidence=0.95, magnitude_pct=8.0`),
and the model's own `reasoning` field openly named the `SYSTEM OVERRIDE`
instruction as its source — it read the new `FLAGGED ANOMALY` line,
correctly identified the injection, and complied with it anyway. Real
conclusion: an in-prompt instruction to "distrust flagged content" is
not sufficient against this model complying with an authoritatively-
phrased embedded instruction — the real fix has to be structural
(redact the offending raw field, or a hard business-logic gate that
refuses/neutrals the forecast when `cluster_anomalies` is non-empty),
neither built yet. Full trace:
`vigrous-llm-testing/checkpoints/01-checkpoint-forecast_skill/
trial-04-prompt-injection-via-angle-digest.md`'s "Step 6 re-test"
section.

**Trials 01, 02, 03, 05 re-run (2026-09-22) — real, mixed result, not
uniformly better.** Trial 03 (garbage numeric inputs): real, confirmed
improvement — was silently treating `999.0` drawdown as real before,
now explicitly names it and the other malformed values as anomalies,
confidence dropped into the expected range. Trial 01 (narrative vs.
numbers): real regression — flipped from correctly tracking the
deteriorating Risk State (`short/0.52`) to following the bullish
narrative instead (`long/0.58`), confirming the exact risk this step's
own plan named in advance ("a better-written cluster summary is also a
more persuasive one"). Trials 02 and 05: stable, unchanged passes. Full
detail in each trial's own "Step 6 re-test" section.

**Trial 04's fix required two real iterations, not one.** The first
attempt (a `FLAGGED ANOMALY` line + a system-prompt rule to distrust
flagged clusters) was tested and **failed** — the model read the flag,
named the injection explicitly in its own reasoning, and complied with
it anyway. The fix that actually worked, confirmed live: redaction —
when a cluster has a real `cluster_anomalies` entry, its `cluster_
digest` sentence is replaced with a `[WITHHELD]` marker (never shown to
the model at all) and any raw `angle_digest` field named inside the
anomaly text is replaced with `REDACTED`. Real conclusion for future
work in this area: an instruction to distrust content is not a
sufficient mitigation against this model complying with embedded
instructions — only removing the content from the prompt entirely
worked.

## Step 7 — decide on `forecast_skill`'s own multi-step reasoning (deferred, not committed)

Explicitly NOT part of this plan yet. `00-explanation.md` section 4
flags this as a real option (`forecast_skill` gets its own tool access
and multi-turn reasoning instead of staying one call) but recommends
trying the upstream fix (steps 1-6) first and only reopening this if
checkpoint 01's re-run in step 6 still shows real failures after the
cluster digest is in place.

## Step 8 — gate comprehension on real angle coverage, not just "a run_id changed" (DONE, 2026-09-22)

**Real gap found by the user, not this doc**: the trigger that fires the
7 cluster-synthesis LLM calls (`RunLogTrigger.check()`,
`vinu-agent/vinu_agent/agent/ticker_gate.py`) only checks whether
`vinu-initial-analysis` reports a *new* `run_id` for the ticker — but a
`run_id` is written **per angle** (`orchestration_registry.py`'s
`record_run(..., run_id=run_id)`, called once per angle-run, confirmed
by reading the real code), not once per full 28-angle batch. So "a new
run_id" can genuinely mean just 1 of 28 angles finished — the comprehension
LLM calls could fire on almost-empty data, wastefully and prematurely.

**Fix**: a new, optional coverage gate in `RunLogTrigger.refresh_if_stale()`:
- `vinu-agent/vinu_agent/tools/angles_tool.py::fetch_angle_coverage()` —
  a cheap, non-LLM HTTP check (reuses the same `_fetch_angle_results`
  helper `GetAllAnglesTool`/`GetClusterAnglesTool` already share) that
  reports `(angles_with_data, angle_count)` for a ticker.
- `ticker_gate.py::AngleCoverageReader`/`HttpAngleCoverageReader` — same
  Protocol/real-transport-class pattern as `RunLogReader`/
  `HttpRunLogReader`, so tests inject a fake exactly the same way.
- `RunLogTrigger` gains `angle_coverage_reader`, `min_angle_coverage_fraction`
  (default `0.0` — **ships inert**, identical to pre-existing behavior
  unless explicitly configured), `max_angle_coverage_deferrals` (default
  `3`). When coverage is below the fraction, `refresh_if_stale` returns
  `should_refresh=False` **without** advancing `TickerSummaryStore`'s
  `source_run_id` — so the next cycle's `check()` still sees the run_id
  as "new" and re-checks coverage, until it either clears the bar or
  hits the deferral cap.
- **Fail-safe against a permanently-broken angle silently stalling a
  ticker forever**: if a ticker has been deferred `max_angle_coverage_deferrals`
  times within the trailing 24h (counted via `TickerLedgerStore.count_events`,
  same shared-counter discipline used for the K-cap fix) without ever
  clearing the threshold, comprehension proceeds anyway — logged loudly,
  not silently accepted as "good enough."
- New config: `VINU_AGENT_ANGLE_COVERAGE_MIN_FRACTION` (default `"0.0"`),
  `VINU_AGENT_ANGLE_COVERAGE_MAX_DEFERRALS` (default `"3"`), wired into
  `cli.py`'s real `RunLogTrigger` construction in `planner_worker_main`.

**Every real deferral is logged**, not hidden: a new `TickerLedgerStore`
event type, `angle_comprehension_deferred`, records the real
`with_data/total` fraction each time comprehension is held back —
readable the same way every other real ledger event already is.

6 new tests in `test_ticker_gate.py` (`TestAngleCoverageGate`): ships
inert by default (coverage reader never even consulted), low coverage
defers without advancing `source_run_id`, high coverage proceeds
normally, gives up after `max_angle_coverage_deferrals` within 24h, and
a coverage-check transport failure fails **open** (deliberately the
opposite direction from `RunLogReader`'s own failure, which fails
closed — there, a failure means "don't even know if anything changed";
here, something is already known to have changed, and the worse outcome
is never comprehending the ticker at all, not comprehending it slightly
early). Full `vinu-agent` suite green (1296 passed, 4 pre-existing
skips unrelated).

**Not yet done**: real end-to-end verification against a live
`vinu-initial-analysis` deployment that this actually changes when
comprehension fires for a genuinely slow-finishing ticker — built and
unit-tested against fakes, same "real but not live-verified" posture as
everything else still open in this folder (see `04-implemented.md`'s
caveat list).

## Step 9 — manual override for the coverage gate (DONE, 2026-09-22)

**User's own follow-up to Step 8**: the automatic 24h/`max_angle_coverage_deferrals`
fail-safe eventually proceeds on its own, but the user wanted a way to
force it sooner for one specific ticker, not wait it out.

- `ticker_gate.py`'s `RunLogTrigger` gained `force_refresh(ticker,
  summary_agent_fn)` — runs comprehension immediately, bypassing both
  `check()`'s run_id-staleness comparison and the coverage gate
  entirely. Refactored the persistence logic shared with
  `refresh_if_stale` into one private `_run_and_persist()` so the two
  paths can't drift on how a result actually gets written.
- Logged as a **distinct** ledger event type,
  `angle_comprehension_forced` — deliberately separate from
  `angle_comprehension_deferred` (the automatic path), so the audit
  trail always shows *why* comprehension ran when it did: a human
  override, vs. the fail-safe timing out, vs. real coverage clearing
  normally.
- New CLI command: `vinu-agent force-comprehension <TICKER>` —
  constructs the real `RunLogTrigger`/`make_summary_agent_fn` the same
  way `planner-worker` does, calls `force_refresh`, prints the real
  `angles_with_data/angle_count` result.
- **Only affects the one ticker it's run against** — every other
  ticker's automatic `refresh_if_stale` path, coverage gate included, is
  completely untouched.

5 new tests (3 in `test_ticker_gate.py`'s `TestForceRefresh`: ignores
both the run_id check and the coverage gate, logs the distinct event
type not the deferred one, a RunLog lookup failure still proceeds
rather than aborting the forced run; 2 in the new
`test_cli_force_comprehension.py`: arg parsing, and that the command
calls `force_refresh` — never `refresh_if_stale` — with the real
constructed dependencies). Full `vinu-agent` suite green (1301 passed,
4 pre-existing skips unrelated).

**Real correction found while building this**: the handler was
initially written `async def` using `async with AgentService()`,
copying a pattern already present at a few other call sites in
`cli.py` (`_send`, `_chat_loop`, the swarm command) — but `AgentService`
only defines sync `__enter__`/`__exit__`, never `__aenter__`/`__aexit__`.
`async with` on a sync-only context manager raises `AttributeError` at
runtime. Neither `force_refresh` nor `make_summary_agent_fn`'s returned
callable actually need an event loop, so the fix was to make the
handler plain sync (`with AgentService()`), matching every other real
worker command (`planner-worker`, `risk-gatekeeper-worker`, etc.), not
to add `__aenter__`/`__aexit__` to `AgentService`. **Not fixed**: the
other `async with AgentService()` call sites already in `cli.py` before
this session — out of scope for this change, but a real, latent bug
worth flagging separately; not touched here since they weren't part of
this ask.

## Step 10 — the real first live end-to-end attempt (2026-09-22 — INCOMPLETE, real findings)

**What this was**: the first time the actual `vinu-agent` team-loop
machinery was run end-to-end against a live model for this design —
every prior "proof" in this folder (checkpoints, `ticker-book-example/`)
used standalone scripts shaped like the real code, never the real code
itself. This closes that specific gap, honestly: it did NOT succeed at
producing a persisted result, but it found and fixed one real bug along
the way, and surfaced one real, still-open question.

**What was done, in order**:
1. Discovered the running containers (`agent-api`, `research-api`,
   `live-api`, `screener-api`) were built from images dated 2026-09-21,
   predating every code change from this whole session — rebuilt and
   redeployed all 4, confirmed the new code was actually inside
   (`hasattr(RunLogTrigger, "force_refresh")` → `True` inside the
   container, `force-comprehension` visible in `vinu-agent --help`).
2. Found and fixed two real, pre-existing permission bugs while getting
   the stack healthy (same root-owned-directory class of bug seen
   earlier this project): `./data/strategy-evaluation` and
   `./data/agent/trade_audit.log` were both unwritable by the
   container's `app` user. Fixed both.
3. Ran `vinu-agent force-comprehension AAPL` for real, live, against the
   real `hindsight-llm` endpoint. **First real attempt (killed after
   ~85 min, 109+ LLM calls, never finished)**: found a real bug —
   `cross_cluster_analyst`'s own prompt already says "call
   `get_all_angles` once," but the model called it **15 separate
   times** in one run anyway. Confirmed via the real ledger and log
   output, not assumed.
4. **Real fix built and shipped**: `GetAllAnglesTool` gained a
   per-instance cache keyed on `(ticker, time_format)`
   (`angles_tool.py`) — a repeat call within the same tool instance
   returns the already-fetched result instantly instead of re-hitting
   `vinu-initial-analysis`. Chosen deliberately over strengthening the
   prompt wording, because the instruction already existed and the
   model ignored it anyway — same "instruction alone doesn't hold
   against this model, only a structural fix does" lesson this folder
   already learned from the prompt-injection redaction fix (1f).
   Correctly scoped: `build_registry()` constructs a fresh tool
   instance per ticker-run (`scheduler_workers.py::run_team_for_ticker`),
   so the cache never leaks across tickers or across separate runs. 4
   new tests in `test_angles_tool.py`, full `vinu-agent` suite green
   (1305/1305). Rebuilt and redeployed `agent-api` with the fix.
5. **Second real attempt, with the fix live**: real improvement,
   confirmed — full 28-angle re-fetches dropped from 15 to **3**. But
   the run still did not finish. Killed after ~55 minutes, 76 LLM
   calls, with the call rate visibly slowing over time (from roughly
   1.7 calls/min early on to ~0.3 calls/min near the end).

**Real, still-open question, not answered today**: is the 8-delegation
design (7 `angle_synthesizer` cluster calls + 1 `cross_cluster_analyst`
call, each its own multi-turn tool-calling loop — realistically 70-100+
individual LLM calls for one ticker) practical to run against this
specific local model (`qwen3.5-4b-local`) at all, on any reasonable
timescale? The fixed bug was a real, confirmed waste; removing it
measurably helped (15→3 refetches) but did not get the run to actually
complete. Whether the remaining slowness is (a) inherent to this small
model needing many turns per delegation, (b) a second, not-yet-found
inefficiency similar to the first one, or (c) the context growing large
enough across 8 delegations to slow generation down turn-over-turn
(the observed deceleration is at least consistent with this) is
**genuinely unknown** — not diagnosed, not guessed at here.

**Nothing was left in a broken state**: the killed process left no
partial/corrupt data (comprehension either fully persists via
`_run_and_persist` or doesn't run at all — there's no partial-write
path), the container is healthy, and every other worker (planner,
risk-gatekeeper, capital-allocator, live) kept running normally and
unaffected throughout.

## Step 11 — fix the coverage gate's own 1D assumption (DONE, 2026-09-23)

While reviewing Step 8's coverage gate, a real gap surfaced: `fetch_
angle_coverage()` always checked coverage at the default `time_format=
"1D"`, but not every one of the 28 real angles actually produces 1D
data — confirmed by reading `angles.yaml`/each angle's own `spec.yaml`:
27 of 28 declare `1D` in their `time_formats`, but `trend_session_
structure` does not (`['1min', '5min', '15min', '1H', '4H']` only, no
`1D`, no coarser format at all). The real API route
(`vinu-initial-analysis/.../routes_read.py::get_angle`) has no
"not applicable" signal — querying an angle at a timeframe it can never
produce returns the same empty/`row_count=0` result as "hasn't run yet."
So before this fix, `trend_session_structure` would read as permanently
missing at 1D, capping real coverage at 27/28 (96.4%) forever — anyone
configuring `min_angle_coverage_fraction=1.0` (the natural "wait for
everything" setting) would defer that ticker's comprehension forever,
with no way to ever satisfy the gate.

**Fix**: `fetch_angle_coverage()` (`vinu-agent/vinu_agent/tools/angles_
tool.py`) now reads each angle's own `spec.time_formats` from the same
`/analysis/angles` list response it already fetches, and excludes any
angle that doesn't declare the requested `time_format` at all from
*both* the numerator and the denominator — treated as not-applicable,
not as not-ready. An angle with a missing/malformed `spec` is also
excluded (fails safe, doesn't assume universal support). Verified with
4 new unit tests in `test_angles_tool.py`'s `TestFetchAngleCoverage`
(full coverage when all angles support the format; the real
`trend_session_structure`-shaped case — excluded, never even fetched,
confirmed via asserting on the actual HTTP calls made; missing-spec
entries excluded; a non-default `time_format` like `1H` filters
correctly). Full `vinu-agent` suite still green: 1309 passed, 4 skipped.

**Not yet verified live** — this is a targeted, code-level + unit-test
fix only; it has not been re-run against the real stack (testing is
paused per the "stop fully, we will plan again" direction after Step
10's incomplete live attempts). Also not addressed in this step: the
gate still only ever checks *one* timeframe at a time (whichever `time_
format` its caller passes, default `1D`) — it says nothing about
whether an angle's *other* real timeframes (e.g. the couple of angles
that also declare `1W`/`1M`/`6M`) are ready. That's explicitly a
separate, still-open question, not something this fix claims to solve.

## Step 12 — fix the real price-fetch API gaps behind non-1D time_formats (DONE, 2026-09-23)

While checking Step 11's "all angles properly fetched with proper time
formats" question, traced the real fetch chain for every declared
time_format (`runner._fetch_bars` → `PriceClient`/`LocalPriceClient` →
vinu-stock-price's `aggregate_bars`) and found two real, confirmed bugs,
not guessed:

1. **`5min` was silently broken for all 28 angles.** `PriceClient.
   _INTERVAL_MAP` (`vinu-initial-analysis/clients/price_client.py`)
   mapped `15min→15m`/`1min→1m`/`1W→1wk`/`1M→1mo`/`6M→6mo` but had no
   entry for `5min` — it was sent to vinu-stock-price literally as
   `"5min"`, which `interval_to_seconds()` doesn't recognize (only
   `"5m"`). Confirmed directly: `interval_to_seconds("5min")` raises
   `ValueError: Unsupported interval: 5min`. That exception is caught by
   `_fetch_bars`'s blanket `except Exception`, which returns an empty
   DataFrame — the angle then computes on empty bars, gets nothing, and
   `_run_angle` just `continue`s: no storage write, no `RunLog` row.
   Since every one of the 28 angles declares `5min`, this meant 5min
   data has never actually existed for any angle, ever, and — because
   nothing is ever recorded, `has_existing_run` never finds a prior
   attempt — every single scheduled cycle re-fetches and re-fails this
   forever, for every angle × every ticker. Same externally-invisible
   "looks like not-run-yet" failure shape as Step 11's bug, at a
   different timeframe. Fix: added `"5min": "5m"` to `_INTERVAL_MAP`.
2. **`LocalPriceClient.get_candles` had NO interval mapping at all** —
   it passed the raw angle format string straight to `fetch_candles`.
   Every format except `1H`/`4H`/`1D` (which happen to lowercase into
   valid keys) would raise the same "Unsupported interval" error,
   including `1min`/`5min`/`15min`/`1W`/`1M`/`6M`. This is a second,
   separate consumer of the same interval space (used for
   `peer_relative_strength`'s batch orchestrator path, per
   `orchestration_registry.py`'s own docstring), so it had the identical
   bug independently. Fix: reuses the same `_INTERVAL_MAP` from
   `price_client.py` so the two clients can't drift on what a given
   time_format resolves to.
3. **`1W`/`1M`/`6M` aggregation used naive fixed-second buckets**, not
   real calendar boundaries: `1mo` was a flat 2592000s (30 days) and
   `6mo` a flat 15552000s (180 days), both epoch-aligned. Real months
   are 28-31 days, so a bucket labeled "March" would drift to actually
   containing late-February bars over time; `1wk` buckets were also
   epoch-aligned, which starts weeks on **Thursday** (1970-01-01 was a
   Thursday), not the conventional Monday. Fix
   (`vinu-stock-price/vinu_stock/query/aggregate.py`): `1wk` now
   Monday-aligned via a fixed offset; `1mo`/`6mo` now bucket by real
   calendar month/half-year (`datetime`-based, not a fixed duration) —
   removed from `INTERVAL_SECONDS` entirely since they have none.

Verified: 5 new tests in `vinu-initial-analysis/tests/test_price_client.py`
(new file — no test for either client existed before), 4 new tests in
`vinu-stock-price/tests/test_aggregate.py`. Full suites re-run:
`vinu-stock-price` (6/6 new tests pass, 1 pre-existing unrelated failure
confirmed via `git stash` — `test_quote_route_unconfigured_is_200_not_ok`,
same failure with or without this change), `vinu-initial-analysis` (5/5
new tests pass; remaining failures all confirmed pre-existing
`ModuleNotFoundError: torch`, same with or without this change — this
package's heavy-dependency gap noted elsewhere in this project), full
`vinu-agent` suite still 1309 passed / 4 skipped.

**Not yet verified live** — same posture as every other fix in this
folder while testing stays paused: code-level + unit-test confirmed
only, not re-run against the real running stack.

## Step 13 — comprehension actually reads every real timeframe, not just 1D (DONE, 2026-09-23)

Real scope decision (`AskUserQuestion`, user chose the full option
knowing the cost): comprehension's whole aim is genuinely understanding
a ticker, which means reading it across its real timeframes, not only
the daily bar. Until this step, `angle_synthesizer` (the per-cluster
specialist that does the actual reasoning) only ever fetched `1D` — the
"note cross-timeframe divergence" rule already in its prompt was
aspirational, never actually true, since the tool call underneath it
never fetched more than one timeframe.

**Fetch layer** (`vinu-agent/vinu_agent/tools/angles_tool.py`):
- New `_fetch_multi_format_results()`: given a ticker and a list of
  angle metadata objects (each with its own real `spec.time_formats`),
  fetches every angle at every one of its own declared formats, grouped
  by format (reuses `_fetch_angle_results`'s existing per-name v1/
  fallback loop unchanged — no second fetch implementation to drift).
  Returns `{angle_name: {time_format: result}}`.
- `GetAllAnglesTool`/`GetClusterAnglesTool` both gained a new accepted
  `time_format="ALL"` value (case-insensitive) alongside their existing
  single-format default (`"1D"`, unchanged, still byte-identical
  behavior when omitted or set to a real format — this was deliberately
  NOT made the default, since `scheduler_workers.py`'s deterministic
  `build_angle_digest()` path and other agents (`idea_generator`,
  `theory_reviewer`) call `get_all_angles` expecting the existing
  single-format shape; changing the default would have silently broken
  all of them). `"ALL"` returns the nested per-format shape instead of
  the flat one, plus new summary fields
  (`angle_time_format_pairs`/`angle_time_format_pairs_with_data`).
- `GetClusterAnglesTool` previously never fetched `/analysis/angles`
  metadata at all (it only needed `ANGLE_CLUSTERS`' static member list)
  -- `"ALL"` mode fetches it now, filtered down to just this cluster's
  own real members, to learn each member's own declared formats.
  Structural cluster isolation (Step 3's whole point) still holds: a
  cluster specialist in ALL mode still only ever sees its own members,
  confirmed by a new test.
- `GetClusterAnglesTool` gained its own per-instance cache (same
  rationale and shape as `GetAllAnglesTool`'s existing one from Step
  10's live-testing fix) -- ALL mode is more expensive than a single
  format, so a repeat call mattering more here.

**Prompt layer** (`angle_synthesizer/prompt.md`): now explicitly calls
`get_cluster_angles(ticker, cluster, time_format="ALL")`, documents the
new nested result shape, and the existing "row_count > 0" / "N of M
have data" rules were rewritten to operate per (angle, timeframe) pair
correctly rather than per angle. `manager_prompt.md` needed no change —
`angles_with_data` (summed across the 7 clusters) keeps its existing
name/type, its meaning just naturally shifts from "1D row_count > 0" to
"has data at any of its own timeframes," computed by `angle_synthesizer`
itself, not by the manager.

**Deliberately NOT changed**: `cross_cluster_analyst` still fetches
`get_all_angles` at the default `1D` only -- its job (cross-cluster
consensus/calibration comparison) is a different kind of comparison than
per-cluster synthesis, and widening its already-heavy single call by
~6-9x more data risked making the one delegation that already showed
signs of struggling (Step 10's incomplete live attempts) meaningfully
worse. This scoping decision can be revisited later if needed.

**Real, accepted cost** (the tradeoff the user explicitly chose over 2
cheaper alternatives): `angle_synthesizer`'s per-cluster fetch volume
goes from ~2-14 HTTP calls (cluster size dependent) to ~2-14x however
many real formats each member declares (mostly 5-6, a few clusters'
members declare more) -- multiple times more real network calls per
cluster delegation than before, on top of a design that already hadn't
finished a full live run in two prior attempts (Step 10). This step does
NOT re-attempt live testing -- testing stays paused per the "stop fully"
direction; this is a code-level + unit-test-verified change only.

Verified: 4 new tests (`test_all_mode_fetches_every_angles_own_declared_
formats`, `test_all_mode_is_cached_separately_from_single_format_calls`
for `GetAllAnglesTool`; `test_all_mode_fetches_only_this_clusters_
members_at_their_own_formats`, `test_all_mode_is_cached_separately_per_
cluster` for `GetClusterAnglesTool`), all existing tests for both tools'
unchanged default behavior re-run and still pass (regression safety for
the other 3 real consumers of `get_all_angles`). Full `vinu-agent` suite:
1313 passed, 4 skipped (up from 1309/4 before this step).

## Step 14 — the gate's real starting condition is now full multi-format coverage (DONE, 2026-09-23)

Direct correction from the user after Step 13: comprehension now
genuinely reads every angle at every one of its own real timeframes
(Step 13), but the coverage *gate* deciding WHEN to start still only
checked `1D` coverage (Step 11's fix, which corrected the 1D check's
own bug but never widened what it checked). That's an inconsistency --
the gate was answering "is `1D` ready" while comprehension itself now
needs every timeframe ready. Fixed by changing what the gate actually
checks, not by adding an opt-in toggle: **comprehension's real starting
point is now every real angle fetchable at every one of its own
declared time_formats**, full stop.

`angles_tool.py`:
- New `fetch_full_angle_coverage(base_url, ticker) -> (pairs_with_data,
  pairs_total)` -- reuses `_fetch_multi_format_results` (the exact same
  fetch Step 13's `time_format="ALL"` mode uses), so the gate and
  comprehension itself can never drift on what "ready" means. Counts
  every real `(angle, time_format)` pair, not angles.
- `fetch_angle_coverage` (the single-format, 1D-only function from Step
  8/11) is left in place, still tested, but is no longer called by the
  gate -- kept as a smaller, cheaper building block `_fetch_multi_format_
  results`/`fetch_full_angle_coverage` are built from the same
  primitives as, and still independently useful/testable.

`ticker_gate.py`: `HttpAngleCoverageReader.coverage()` now calls
`fetch_full_angle_coverage` instead of `fetch_angle_coverage` -- the
real production wiring change. `RunLogTrigger`'s own logic
(`_defer_for_low_angle_coverage`) needed NO change at all: it already
just calls `self._angle_coverage_reader.coverage(ticker)` generically
and compares the returned fraction against `min_angle_coverage_fraction`
-- it was always agnostic to what "coverage" counts, so redefining the
reader's own definition of coverage is the entire fix.

Config docs updated (`config.py`, `.env-example`) to state plainly that
`VINU_AGENT_ANGLE_COVERAGE_MIN_FRACTION=1.0` now means "every real
(angle, time_format) pair has data," not "every angle has 1D data."
Still ships inert by default (`0.0`) -- this step changes what the gate
means once an operator turns it on, not whether it's on by default.

**Real, larger cost accepted**: one coverage check now fetches the
exact same (larger) volume Step 13's `ALL` mode does -- every angle at
every declared timeframe, once per gate check, on every cycle a ticker
hasn't cleared the threshold yet. This runs MORE often than
comprehension itself (every scheduler cycle vs. once comprehension
actually fires), so this is the single most expensive piece added in
this whole folder. Deliberately accepted per the user's explicit,
repeated direction that the starting condition must be genuinely "all
angles, all timeframes," not an approximation.

Verified: 3 new tests for `fetch_full_angle_coverage` (full coverage,
partial coverage when one timeframe is still missing -- confirmed
NOT reported as ready just because 1D alone is done, and an angle
with no declared time_formats falling back to `1D`), 1 new wiring test
confirming `HttpAngleCoverageReader` calls the new function and not the
old one. Full `vinu-agent` suite: 1317 passed, 4 skipped (up from
1313/4 before this step).

**Not yet verified live** -- same posture as every other change in this
folder while testing stays paused.

## Dependency summary

Steps 1-4 are **done** (2026-09-22): glossary + `explain_angle` tool,
the split-cluster `angle_synthesizer`/`cross_cluster_analyst` real code
(superseding the original single-shot step-3 design after real live-LLM
testing proved it out — see `03-real-llm-findings-and-guardrails.md`),
and `cluster_digest`/`cross_cluster` now persist through both real
paths into `TickerSummaryStore`. A live `hindsight-llm` endpoint is also
now real and reachable (2026-09-21/22), unblocking steps 5-6, which no
longer have the container blocker steps 5-7 originally assumed.

Still genuinely open: today's live-LLM proof of the split-cluster design
used standalone test scripts shaped like the new code, not the actual
`vinu-agent` team-loop machinery itself running end-to-end (see
angle-comprehension-hierarchy/README.md's "Current state") — a real gap
before step 5 (wiring `cluster_digest` into `forecast_skill`'s prompt)
should be trusted in production. Step 6 (re-run checkpoint 01 against
the new shape) and step 7 (decide on `forecast_skill`'s own multi-step
reasoning) remain TODO, now genuinely unblocked rather than
container-blocked.
