# To-do: what's still missing before this can be built

## Context

`00-decided-pattern.md` (same folder) is the settled narrative — the 9
steps, where Graphiti fits, the diagram, the worked example. It's
complete as an *explanation*. It is **not** a build spec. This doc is
the concrete list of what still has to be decided and written, in
numbers and schemas, before any of the 6 analysts, Layer 0, or the
brain can actually be coded. Nothing in this list has been done yet.

Per `personal-important/01-discussions-to-reach-conclusion/agents-implementation-plan.md`'s own build order, item 1 (Layer 0's
schema) and item 2 (starting with just the Decision-Process analyst,
owns analysis D) are the actual next concrete steps — not all 8 items
need to be finished before anything can start; #1 and a single
scoped-out analysis from #2 unblock the first real build.

---

## 1. No actual table schema (DDL)

`reflection_findings_history` and `reflection_beliefs` are only
described in prose so far. Needed: a real `CREATE TABLE` for each,
following the exact same pattern every other store in this codebase
already uses (`vinu_infra.sqlite.SQLiteBackend` — `SCHEMA` +
`SCHEMA_VERSION` + `MIGRATIONS`, thread-local connections, WAL mode).

At minimum, `reflection_findings_history` needs: `finding_id`,
`analyst_name`, `cluster`, `scope_type`, `scope_key`, `computed_at`,
`signal_json`, `evidence_count`, `severity`, `narrative`. `reflection_beliefs`
needs the same fields but keyed for overwrite (`PRIMARY KEY (analyst_name,
scope_type, scope_key)` or similar), holding only the current state per
topic.

**Why this is first**: nothing else can be written or tested without
this existing.

## 2. No per-analysis query-level scoping for the 25 (A–Y)

The single largest remaining gap. Every analysis in
`data-driven-analysis-opportunities.md` is still one paragraph — "join
X × Y × Z" — not a real, runnable SQL query with real column names.
Needed, per analysis: the exact tables/columns involved (already mostly
named in each analysis's "Join" line), the exact join keys, and what
the query actually returns.

**Recommended order**: don't try to scope all 25 at once. Per
`personal-important/01-discussions-to-reach-conclusion/agents-implementation-plan.md`, start with **D** (Decision-Process) —
`llm_calls.db` and `telemetry.db` are zero-reader stores today, so this
is a pure read + join with no new writer needed anywhere, the fastest
possible proof the whole pipeline works end to end. Scope D fully
(query, thresholds, output shape) before touching the other 24.

## 3. No concrete significance thresholds

"Is this new, changed, or degraded" is conceptually right but
unquantified everywhere. Needed, per analysis: an actual number. E.g.
"a Brier-score delta of ≥0.05 over the last N calibration entries counts
as significant" (for A), "correlation must climb by ≥0.15 over 3+
consecutive weekly checks" (for E). Without these, `evidence_count` and
the gate itself can't be coded — this is the threshold that decides
whether anything gets written to Layer 0 or Hindsight at all.

**Depends on #2** — can't set a threshold for a query that doesn't
exist yet. Scope both together, per analysis, not as separate passes.

**Load-bearing rule to pin down alongside every threshold, not an
afterthought**: the "changed since when" comparison must always be
computed against the full raw history in the real source tables
(`CorrelationMonitorStore`, `decay_snapshots`, `angle_calibration_entries`,
etc. — written unconditionally every cycle, independent of this gate),
**never** against `reflection_beliefs`'/`reflection_findings_history`'s
own already-gated rows. The "correlation must climb by ≥0.15 over 3+
consecutive weekly checks" example above is ambiguous on exactly this
point — if "checks" means 3 raw computations from the source table
(always available), it's correct; if it gets implemented as 3
consecutive `reflection_findings_history` rows (which only exist once
something was already significant), that's circular and would let a
genuine slow-boil pattern (exactly what analysis E exists to catch in
the trading data itself) stay under the bar indefinitely, because the
reflection layer's own memory of "last time" would itself be gated.
Write the rule explicitly per analysis; don't leave it to be decided
implicitly while coding.

## 4. No analyst plug-in interface

`personal-important/01-discussions-to-reach-conclusion/six-agents-critique-and-hindsight-memory-resolution.md` names the
shape (`(data_root_paths) -> list[Finding]`) but it's never been
written as an actual Python interface/protocol to build every analyst
against. Needed: a real `Finding` dataclass (mirroring the
`reflection_findings_history` schema from #1) and a real function
signature every one of the 6 analyst modules implements, so
`reflection_worker_main`'s registry loop can call them uniformly.

## 5. ~~No decision on where the brain/analysts physically run~~ — CLOSED

**Original decision (superseded below): `reflection_worker_main` runs
inside vinu-agent**, one more worker process alongside every other
worker of the same shape (`resolve_worker_interval(...)` →
`while True: cycle(); sleep()` in `vinu-agent/vinu_agent/cli.py`). Not
just an inference from "we're copying vinu-agent's pattern" — confirmed
twice against the real `docker-compose.yml` mounts
(`02-analyst-interface.md`'s colocated-vs-HTTP table): vinu-agent is the
only container with both its own data root and vinu-research's mounted
(`/research-data`), and it's independently the only container where the
two lowest-risk analysts (D and H) can run with zero new HTTP wiring.

**Superseding decision, 2026-09-19: split into its own `vinu-reflection`
service instead.** Reopened by explicit request — the 6-analyst/25-
analysis/Hindsight build is its own real concern, not something that
should keep growing vinu-agent's own process. `vinu-reflection` is a
worker-only container (no HTTP port), reading vinu-agent's storage
classes in-process against a **read-only mount** of vinu-agent's data
volume (`./data/agent:/agent-data:ro`, `vinu-agent` itself as a real
package dependency) — the same mount-and-import posture
`vinu-agent/broker/research_link.py` already established for
vinu-research, just one hop further out. This keeps the mount-cost
argument above intact (still zero new HTTP wiring for D) while giving
the reflection layer its own deploy/restart/health surface, separate
from vinu-agent's.

**Deliberately cheap to reverse**: every analyst module only ever
imports another service's storage classes directly (never
`vinu_agent`-internal orchestration code), so moving
`vinu_reflection/reflection/` back into `vinu_agent/reflection/` later
is a folder move plus a docker-compose edit, not a rewrite — reopen
this decision again (either direction) only if the mount overhead (a
whole extra image built from vinu-agent's own dependency chain, just to
reuse two store classes) turns out not to be worth a separate service
in practice. Implemented: `vinu-reflection/` (own `pyproject.toml`,
`Dockerfile`, `entrypoint.sh`, `cli.py`'s `reflection_worker_main`/
`run_cycle`, `reflection/decision_process.py`), wired into
`docker-compose.yml` as `reflection-worker` (depends on `agent-api`
being healthy). 9 tests, full suite green.

## 6. ~~No Hindsight bank lifecycle details~~ — CLOSED

All three questions decided, against the full three-bank-type design
(per-ticker + portfolio + system-process — `00-decided-pattern.md` step 6):

**(a) Provisioning — explicit, not implicit.** Ticker banks: `bootstrap_new_tickers`
(vinu-agent, already exists) explicitly calls `acreate_bank` at bootstrap
time, rather than relying on implicit creation on first `retain()`.
Explicit wins here because bank creation takes real parameters
(`mission`, `disposition_skepticism`/`disposition_literalism`/
`disposition_empathy`) that should be a deliberate choice tied to one
call site, not whatever an SDK default happens to be. Portfolio and
system-process banks (singletons, no natural "first ticker enters the
watchlist" trigger): created idempotently at `reflection_worker_main`'s
own startup — "does this bank exist? if not, create it," every cycle
start, same posture as `vinu-screener seed-default`'s idempotent seeding
this session.

**(b) Tag-key schema — locked to exactly 3 keys.** Every `retain()`
call populates all three, no more, no less: `date` (ISO date of the
finding), `regime` (current `regime_tag` if the analyst has one,
omitted if not applicable), `source_analyst` (the `analyst_name`).
Previously only shown as examples in
`personal-important/01-discussions-to-reach-conclusion/other-findings-methods.md`/
`six-agents-critique...md` — this locks it as the final list.

**(c) Teardown — keep the bank, don't build automatic deletion.**
Checked against real code: `remove_ticker`/`DELETE /watchlist/tickers/{symbol}`
is a real, implemented endpoint (vinu-stock-price), but nothing in the
codebase actually calls it anywhere — it's manual/operator-only, not
routine churn. Given that, plus the fact that a removed ticker is more
often reversible (temporary liquidity dip, sector rotation) than
permanent (delisted, bankrupt), and destroying evidence would contradict
the growth-control principle already settled for Hindsight generally
(Critique 5: control growth at the input/`retain()`-gate side, never by
deleting after the fact) — the decision is to **keep orphaned banks,
build no automatic teardown.** The real unbounded-growth risk (`#996`
below) is about the `hindsight-api` process's own footprint under
continuous use, not bank count from rare manual removals, so this isn't
the lever that risk actually needs. **Documented manual fallback, not
automated**: if orphaned banks ever genuinely become a problem (e.g.
after years of accumulated manual removals), an operator can call
Hindsight's own `delete_bank` API directly on specific banks — this
decision isn't a dead end, just not something to automate now. The
portfolio/system-process banks don't have this question at all — they
never get torn down, permanent singletons by design.

**Two open Hindsight reliability risks to re-check before this is built**
(from live GitHub-issue search, `personal-important/01-discussions-to-reach-conclusion/hindsight-memory-harness-explanation.md`
and `.../six-agents-critique-and-hindsight-memory-resolution.md`), not
previously carried into this to-do list:
- [`reflect()` — issue #4378](https://github.com/vectorize-io/hindsight/issues/4378): returns a false "I don't have information" on roughly half of real calls (versions 0.9.2/0.10.0). The brain would call `reflect()` up to three times per synthesis (ticker + portfolio + system-process bank) — compounded, that's a real risk of silently losing a third of intended context per synthesis, not a rare edge case.
- [self-hosted `hindsight-api` unbounded memory growth — issue #996](https://github.com/vectorize-io/hindsight/issues/996): ~1GB growth within under an hour in a container, reported live, relevant for any deployment running the three banks above continuously.

Both risks are why `reflection_beliefs` (SQLite) has to stay the brain's
**hard, always-available source of truth** — Hindsight is enrichment,
never something the brain's actual functioning structurally depends on
succeeding. This should be re-verified against whatever Hindsight
release is current at build time, not assumed still true from this
audit.

## 7. ~~No failure-isolation restated as a concrete requirement~~ — CLOSED

Already satisfied by `02-analyst-interface.md`'s real worker-loop
pseudocode, which has the try/except around each analyst's call
explicitly, plus the structural argument for why it holds even before
that: each analyst is a standalone pure function with no shared state,
so one analyst's bug can't corrupt another's computation regardless —
the try/except only stops one failure from skipping the rest of *that
cycle's* run, on top of an isolation guarantee that's already there by
construction. No further design needed; this is a requirement the
worker-loop file must not drop when it's actually written, not an open
question.

## 8. No schema for the brain's own self-trust tracking

Step 9 of `00-decided-pattern.md` describes logging the brain's own
synthesis predictions against later observed outcomes, gating how much
weight its narrative carries by its own accumulated sample size — but
no table exists for this yet. Needed: a store (same `SQLiteBackend`
pattern again), `reflection_synthesis_outcomes`, 12 columns:

```
synthesis_id PK, computed_at,
trigger_reason (scheduled | new_significant_finding | consumer_requested),
inputs_snapshot (JSON — the specific reflection_beliefs rows read for
  this synthesis, so reasoning quality is auditable separately from
  outcome luck: a good call can have a bad outcome, and vice versa),
prediction_json (the synthesized judgment: maturity profile, narrative,
  any proposed action),
proposed_action_type NULL (threshold_nudge | significance_flag |
  narrative_only — a pure narrative and an actionable proposal need
  different grading criteria),
resolution_criteria TEXT (what counts as "right" — written at
  PREDICTION time, never decided after the fact, to avoid the same
  look-ahead bias freeze_manifest/contamination_check already guards
  against elsewhere in this system),
resolve_by (when to check back),
observed_outcome_json NULL (filled in at resolution, same shape as
  prediction_json so the two can be diffed directly),
outcome_match NULL (correct | partially_correct | incorrect |
  inconclusive — a queryable summary so accuracy doesn't require
  re-diffing JSON every time),
resolved_at NULL,
evidence_count_at_synthesis (the evidence backing the analysts this
  synthesis drew on — a synthesis made on thin evidence shouldn't move
  the brain's track record as much as one made on deep evidence)
```

Written when the brain synthesizes; updated later by a resolution
worker (see below) once the predicted outcome is actually known. This
is lower priority than 1–4 since it only matters once the brain itself
exists (step 8), which is last in the build order anyway.

**Also needed, not just the schema**: something has to actually *check*
for resolvable predictions and fill in `observed_outcome_json` — this
doesn't happen passively. The natural shape is a periodic pass over
unresolved `synthesis_id` rows past their resolution window, the same
"scan for what's now answerable" role `significance-worker` already
plays for unresolved `significance_flags` rows. Without this, the
self-trust table would accumulate `NULL`-outcome rows forever and never
actually gate anything.

---

## Status — all 8 closed

As of this pass, **every item on this list is closed**: #1–#5 were
closed earlier (Layer 0 schema, all 25 analyses scoped, the analyst
interface, the "runs in vinu-agent" decision locked against real
docker-compose evidence), and #6/#7 just closed above (Hindsight bank
lifecycle fully decided, failure isolation already structurally
satisfied). #8's schema is written above.

**What actually unblocks building, today**: #1 (Layer 0 schema) plus
the fully-scoped analysis **D** alone (`25-A-Y-details/04-decision-process-cognition.md`,
per `personal-important/01-discussions-to-reach-conclusion/agents-implementation-plan.md`'s
recommended starting point) are what's needed to write and test the
first real piece of this system end to end — Decision-Process is still
the right first slice, since it's the only cluster needing zero
`service_clients` wiring. Every other design question this folder
raised is now answered; what's left from here is implementation, not
more design.

**Update, 2026-09-18 — #1 and D are now built**: `vinu-infra/reflection.py`
implements Layer 0 exactly as scoped above (`ReflectionStore`'s 3
tables, `Finding`, `classify_severity()`/`compute_trend()` per
`03-severity-and-trend.md`, `write_finding()`/`write_findings()`), and
analysis D implements D end to end: reads real `llm_calls`/`team_runs`
rows (two small new reader methods added — `LlmCallLogStore.distinct_roles()`,
`TeamRunStore.get_latest_verdict_by_session_id()` — both were
zero-reader stores before this), computes `retry_rejection_delta` per
`llm_role`, gates on `evidence_count >= 30`, classifies severity via a
real two-group PSI (retry-group vs. no-retry-group reject-rate split —
non-circular, computed fresh from raw rows every call, never from this
analyst's own prior findings).

**Update, 2026-09-19 — D + the worker loop moved into `vinu-reflection`**
(see #5 above for the full reasoning): `vinu-reflection/vinu_reflection/
reflection/decision_process.py` (moved from `vinu-agent/vinu_agent/
reflection/`, same code, only the package changed) and
`vinu-reflection/vinu_reflection/cli.py`'s `reflection_worker_main`/
`run_cycle` — the real worker loop `02-analyst-interface.md` previously
only had as pseudocode now exists: `ANALYSTS` registry (currently just
`[decision_process.run]`), per-analyst try/except isolation
(05-to-do.md #7), `decision_process.seed_reference_config()` called at
every worker startup (idempotent, matching `vinu-screener seed-default`'s
pattern) so `reflection_reference_config` is always populated before
the first `write_finding()` call needs it. Wired into `docker-compose.yml`
as `reflection-worker` (own container, no HTTP port, `./data/agent:/agent-data:ro`
read-only mount of vinu-agent's data, depends on `agent-api` healthy).
34 new tests across 2 packages (25 vinu-infra's Layer 0, 9
vinu-reflection's analyst + worker-loop tests -- vinu-agent's two new
reader methods, `distinct_roles()`/`get_latest_verdict_by_session_id()`,
are exercised indirectly through vinu-reflection's tests, no dedicated
unit tests added in vinu-agent itself for them), all suites green
(248/248 vinu-infra, 1171/1171 vinu-agent, 9/9 vinu-reflection).

**Update, 2026-09-19 — L and M also built, K blocked**: continuing the
same cluster (`25-A-Y-details/04-decision-process-cognition.md` has the
per-analysis detail; summary here). `process_mining.py` (L) and
`debate_value.py` (M) are both in `vinu-reflection`, registered in
`cli.py`'s `ANALYSTS`/`_SEED_FNS`, real end-to-end tests against real
`vinu-research`/`vinu-agent` data shapes. Fixed a real bug found while
writing L/M's tests along the way: `population_stability_index` (in
`vinu-infra/reflection.py`) silently returned `0.0` for any shift
between two zero-variance (all-identical-value) sample groups -- a real
case for near-binary quality data, not just a test artifact -- because
every quantile of a constant reference array equals that same constant,
so equi-quantile binning couldn't distinguish "matches the reference"
from "nothing like the reference." Fixed with the degenerate-reference
fallback `04-reference-baseline-config.md`'s own "Bin count" section
already sanctioned (a plain two-sample difference-fraction, not binned
PSI, for this case) -- this fix applies to every analyst using this
function, not just L/M. **K could not be implemented as scoped** --
checked the real prompt-injection code path and confirmed no structured
record of which memory/fact entries get injected into a prompt exists
anywhere (not an oversight found now correctable in this pass; needs
either a new writer or an accepted lossy approximation — see K's own
section in `04-decision-process-cognition.md` for the two options, left
undecided). 8 new tests since the last update (9 -> 17 total in
vinu-reflection), all suites still green (248/248 vinu-infra, 1171/1171
vinu-agent, 17/17 vinu-reflection). **This closes the Decision-Process
cluster's implementable analyses** (3 of 4 — D, L, M; K blocked).

**Update, 2026-09-19 — A built, first analysis of the Forecast
Intelligence cluster**: `vinu-reflection/vinu_reflection/reflection/angle_trust.py`
(`25-A-Y-details/01-forecast-intelligence.md` has the per-analysis
detail). Reuses the same shared PSI machinery as D/L/M rather than
adding a second significance-testing mechanism for A's percentile-band
Condition (see that module's own docstring); `ticker_cluster_breakdown`
scoped out, same posture as D/L's own scope-downs. One new reader
method added to vinu-research's `SqliteStrategyStore`
(`distinct_angle_names()`). 5 new tests (17 -> 22 total in
vinu-reflection), all suites still green (248/248 vinu-infra, 1171/1171
vinu-agent, 22/22 vinu-reflection, 889/889 vinu-research). 4 of 25
analyses now implemented (D, L, M, A); K blocked; the other 20 (5
clusters minus the 1 analysis done in Forecast Intelligence) are still
design-only.

**Update, 2026-09-19 — Q/P/G/S surveyed and not built, C built.**
Continuing through Forecast Intelligence before moving on: **Q**
(weight-lineage staleness) deferred, not blocked -- its source,
`WeightsStore`, lives in vinu-initial-analysis, the one service already
flagged twice as too dependency-heavy (torch/xgboost/chronos/timesfm)
to mount-and-import the way every analyst so far does; building Q would
reintroduce the exact cost the shared ticker-profile mechanism exists
to avoid, and that mechanism's `vinu_initial_analysis` key doesn't carry
the fields Q needs either. **P and G are genuinely blocked**: checked
`calibration_entries.timestamp` (vinu-research) against every real
writer and confirmed it's never populated -- always `""` -- so the
within-symbol, time-windowed comparison both analyses need (brier
during a gap/fallback window vs. this symbol's own clean-period
baseline) cannot be computed from real data today. **S not attempted**
-- needs a real numeric-claim-extraction spec (fact sheet vs. LLM prose)
that doesn't exist anywhere in this codebase to build against, unlike
every analysis built so far which all reused real, already-written
query code. Full detail and the two ways forward for each in
`25-A-Y-details/01-forecast-intelligence.md`.

Skipped ahead to **C** (`vinu-reflection/vinu_reflection/reflection/loss_attribution.py`,
first "Execution & Money-Flow" cluster analysis,
`03-execution-money-flow.md`) since it was real and tractable. Scoped
`(trade_score_tier, risk_band)` down to `trade_score_tier` alone --
`risk_band` has no categorical label in the real data, only numeric
limits. **Found and fixed a real, unrelated infra bug while wiring
it**: `trade_audit_log.jsonl` had no `VINU_TRADE_AUDIT_LOG` set in
`docker-compose.yml` anywhere, so it was writing to live-api's
container-local `$HOME` instead of its mounted `/data` volume -- silently
lost on every restart. Fixed in `docker-compose.yml` (`live-api` now
sets it; `reflection-worker` gets a new read-only `./data/live` mount).
5 new tests (22 -> 27 total in vinu-reflection), all suites still green
(248/248 vinu-infra, 1171/1171 vinu-agent, 27/27 vinu-reflection). 5 of
25 analyses now implemented (D, L, M, A, C); K blocked, P/G blocked, Q
deferred, S needs a spec. 15 analyses (U/Y from Execution & Money-Flow,
plus all of Regime & Risk Coverage, Governance & Freshness,
External-Signal Cross-Check) remain fully design-only.

**Update, 2026-09-19 — E's pair piece built, the one quadratic-scaling
risk in the whole 25-analysis set**: `vinu-reflection/vinu_reflection/
reflection/correlation_coverage.py` (`25-A-Y-details/02-regime-risk-coverage.md`
has the per-analysis detail). Reads `CorrelationMonitorStore` scoped to
pairs currently co-held (`BookBackend`/`list_open_positions`, both
vinu-live) -- the load-bearing manageability mitigation the design doc
calls out. **Real data-shape correction found while implementing**:
`correlation_monitor_history`'s `flagged` list only ever has a value for
a pair on cycles where it already crossed the comovement threshold, so
a pair's continuous correlation history can't be reconstructed -- only
the sequence of already-flagged values. Implemented against that real
signal (documented as a real gap: this can't catch a pair drifting
toward the threshold while staying under it, the literal "slow boil"
scenario E exists for -- would need a new writer to close). New
`vinu-live` dependency added to `vinu-reflection` (mount-and-import),
reusing the `/live-data` mount already added for C, no new
docker-compose change needed beyond the dependency itself. 5 new tests
(27 -> 32 total in vinu-reflection), all suites still green (248/248
vinu-infra, 1171/1171 vinu-agent, 32/32 vinu-reflection, 436/436
vinu-live). 6 of 25 analyses now implemented (D, L, M, A, C, E-pair).

**Update, 2026-09-19 — H, I, X built; real bug fixed; full triage of the
remaining 16 analyses.** Continuing without stopping, per direction.

**H's governance piece** (`vinu-reflection/vinu_reflection/reflection/skill_edit_governance.py`):
per real skill-file edit (`skill_edit_audit`, vinu-agent), compares
`trade_score_calibration_history` win rate before vs. after, system-wide
(scoped down from "affected strategy family" — no artifact/strategy id
exists on calibration-history rows at all).

**I and X** (`vinu-reflection/vinu_reflection/reflection/screener_agreement.py`,
one module for both — same shape): does the screener's ranker (I) /
alert-rule engine (X) agree with the main pipeline's own independent
interest (`candidate_proposed` events in `ticker_ledger`, a real,
previously-unused signal). New `vinu-screener` dependency + `./data/screener`
mount added.

**Real deployment bug found and fixed**: `angle_trust.py`/`debate_value.py`/
`process_mining.py` (built earlier this pass) all call vinu-agent's
`research_link.get_strategy_store()`, which resolves
`VINU_RESEARCH_DATA_ROOT` from the calling container's own environment —
`docker-compose.yml` never set it for `reflection-worker`, so in a real
deployment those three analysts would have silently read/written nothing
(defaulting to an empty `Path.cwd()/data`). Fixed: `VINU_RESEARCH_DATA_ROOT=/research-data`
+ a new `./data/research` mount added to `reflection-worker`.

**Full triage of the other 16 analyses** (real code/data checked for
every one, nothing guessed at):
- **Genuinely blocked** (assumed data that a real writer doesn't
  actually keep — same class as K/P/G already found): **U**
  (`RebalanceRequestQueue.consume()` deletes each request once
  evaluated — no history), **Y** (`EventsStore.replace_kind()` deletes
  past events every calendar pull — no archive), **J** (`regime_tag` is
  set once at artifact creation and never updated again — no
  regime-transition event stream exists), **R** (`ticker_summaries` is
  explicitly current-state-only per its own docstring — no point-in-time
  reconstruction possible).
- **Needs a new categorical scheme, not a missing writer**: **B** (no
  `strategy_family`-like concept exists anywhere — would mean inventing
  a classification scheme, not reading one).
- **Deferred as a dependency-cost tradeoff** (same reasoning as Q):
  **N** (needs vinu-initial-analysis's Parquet angle results).
- **Structurally blocked**: **T** (depends on `MaturityAssessor`, which
  doesn't exist yet — the design doc already says so).
- **Needs a real spec, not a missing writer**: **S** (numeric-claim
  text extraction, no existing parser to reuse).
- **Needs more investigation before building** (not blocked, not
  checked deeply enough to trust yet): **O, F, W** (each has a vaguely-
  specified join the design doc itself hedges on), **V** (`paper_performance`
  confirmed overwrite-only with no per-return timestamps or promotion
  marker; also needs a new Pearson-correlation helper this codebase
  doesn't have yet).

8 new tests (32 -> 40 total in vinu-reflection), all suites green
(248/248 vinu-infra, 1171/1171 vinu-agent, 40/40 vinu-reflection,
436/436 vinu-live, 436/436 vinu-screener, 889/889 vinu-research). **9 of
25 analyses now implemented**: D, L, M, A, C, E-pair, H-governance, I,
X. K blocked (Decision-Process); the 16 above are triaged as described.

**A new single-reference status file now tracks all of this**:
`25-A-Y-details/07-implementation-plan-status.md` — the plan, the
per-analysis status table (all 25), the 6-analyst completion breakdown,
how each remaining group actually gets closed, and a ranked "where to
continue" list. Read that file first for anything past this point;
entries below stay as the historical log.

**Update, 2026-09-19 — E's concentration piece built, closing out the
lowest-risk item on that ranked list**:
`vinu-reflection/vinu_reflection/reflection/concentration_coverage.py`
(`02-regime-risk-coverage.md` has the per-analysis detail). Reads
`AllocationHistoryStore` (vinu-portfolio); real data-shape correction
found while implementing — `vol_annualized` isn't tracked per sleeve
anywhere, only weight concentration is, so built against that (the
design doc's own "or" already anticipated this). New `vinu-portfolio`
dependency + `./data/portfolio` mount added to `vinu-reflection`. 5 new
tests (40 -> 45 total in vinu-reflection), all suites still green
(248/248 vinu-infra, 1171/1171 vinu-agent, 45/45 vinu-reflection,
436/436 vinu-live, 436/436 vinu-screener, 209/209 vinu-portfolio,
889/889 vinu-research). **10 of 25 analyses now implemented.**

**Update, 2026-09-19 — O/F/W/V + H-consistency investigation pass, then
W and H-consistency built**: real-code investigation (per
`07-implementation-plan-status.md`'s ranked list) found W and
H-consistency both buildable, O a real design decision (not a missing
investigation), and F a genuine hard blocker.
- **W built**: `vinu-reflection/vinu_reflection/reflection/
  threshold_calibration.py`. The design doc's counterfactual ("swept
  range of nearby values") has no helper anywhere in this codebase to
  build against — implemented as the same two-adjacent-windows drift
  detector every other analyst here uses, applied to each checkpoint's
  own logged field instead. Only 2 of the design doc's 3 named
  checkpoints have a real writer (`bracket_partial`, `rebalance_protect`
  — grepped every `calibration_log.record()` call site; no
  "thesis-duplicate" checkpoint exists anywhere). Found and fixed a real
  infra bug along the way: `live-api` had no `VINU_CALIBRATION_LOG` set
  in `docker-compose.yml` — same "writes to the container's ephemeral
  `$HOME`, not `/data`" bug already fixed once for `trade_audit_log.jsonl`.
- **H-consistency built**: `vinu-reflection/vinu_reflection/reflection/
  consistency_freeze.py`. Found `vinu_infra/freeze.py`'s `freeze_manifest`/
  `contamination_check` needed no refactor at all — they're plain,
  argument-only functions, and this file's own "manually-triggered"
  framing was wrong (grepped the whole tree: no caller anywhere, they
  were simply unused). The real, load-bearing fix was packaging:
  `freeze.py` lived in an orphaned `vinu-infra/vinu_infra/` subdirectory
  that the package's own flat `package-dir` mapping never covered, so
  `vinu_infra.freeze` was unimportable from anywhere — moved to
  `vinu-infra/freeze.py` (the same flat layout every other vinu-infra
  module uses). Scoped down to `scope_type=system` (no `strategy_family`
  join is possible from what `freeze_manifest`/`contamination_check`
  actually compute — global file hashes and env vars, not per-strategy
  data) and to a `domain_floor_breached` finding rather than PSI (a
  structural diff, not two numeric distributions).
- **O investigated, not built**: the "eventual performance of a blocked
  artifact" half is real and computable via `decay_snapshots`
  (independent of whether the artifact was ever blocked live). The real
  blocker: `order_rejected` audit entries carry no `artifact_id` at all —
  identifying which artifact got blocked needs a weak symbol+time-window
  match, not a stored key. A real decision (accept the weak match, or
  add `artifact_id` to `order_rejected` logging first), same shape as
  the K/U/Y new-writer decisions.
- **F investigated, not built**: genuinely blocked. `significance_flags`
  has no `artifact_id`/order/trade id at all, only `ticker` — no join,
  weak or otherwise, to any later trade/artifact outcome exists in real
  code today.
- **V not reinvestigated this pass** — still needs a `promoted_at`-
  equivalent timestamp and a Pearson-correlation helper.

12 new tests (45 -> 57 total in vinu-reflection), all suites still green
(248/248 vinu-infra, 57/57 vinu-reflection). **12 of 25 analyses now
implemented**: D, L, M, A, C, E (both pieces), H (both pieces), I, X, W.
