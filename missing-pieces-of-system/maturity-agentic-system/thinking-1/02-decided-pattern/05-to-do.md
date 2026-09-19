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

**Update, 2026-09-19 — P/G's "blocked" verdict was wrong; built.** Found
while investigating V (chasing its `promoted_at`/Pearson-helper blockers):
the `calibration_entries.timestamp` claim behind P/G's own "Blocked"
verdict above doesn't hold up. Checked `calibration.py`'s `add_entry()`
directly — it sets `timestamp=datetime.now(timezone.utc).isoformat()`,
and `git blame` shows that line has been there since 2026-07-27, two
months before the verdict was written. It's wired to a real writer:
vinu-live's `feedback_loop.py` calls `POST /trade-plan/{id}/record-
outcome` on every closed position, which reaches `append_calibration_
entry()` and persists the real timestamp. This was a documentation
error, not a real data gap — first one caught in this file.
- **P/G built**: `vinu-reflection/vinu_reflection/reflection/
  ingest_health.py` (one module, merged per-ticker row, per the design
  doc's own merge rule). Real join is on `Artifact.created_at` (the
  forecast-authoring moment), not `CalibrationEntry.timestamp` (the
  trade's *close* time) — joining on the close time would have mis-dated
  every comparison against `ingest_log`/`provider_fallback_log`'s
  gap/fallback days. Scoped down the "`gap_count` exceeds its own
  trailing P90" half of P's Condition — no historical time series of
  `gap_count` exists anywhere, only a current snapshot — same "build
  what's real, document what isn't" posture as W's own scope-down.
  `CatalogStore.list_ingest_log()` added (`ingest_log` was write-only
  everywhere else, exactly as originally flagged). Found a second real
  bug while writing tests: `vinu_stock.storage.backend.MetaBackend`
  requires `VINU_STOCK_DATA_ROOT` set even when given an explicit db
  path (`SettingsStore`'s schema init calls `vinu_stock.config.
  load_config()` regardless) — worked around by opening `CatalogStore`
  directly instead, the same construction vinu-stock-price's own tests
  already use.
- Environment note: this pass's test suite for `ingest_health.py`
  couldn't actually be executed in-session — a local Application Control
  policy blocks pandas' compiled extension (pulled in transitively via
  `vinu_research.models` -> `portfolio.py`), which also blocks several
  *pre-existing* reflection/stock-price test files, not just this one.
  Verified instead via `vinu-stock-price`'s new store-method tests
  (pandas-free, 9/9 green) and a standalone harness that stubs only the
  one pandas-triggering import and exercises the real join/PSI logic
  end-to-end (22/22 checks passed). Whoever next runs this in a normal
  dev/CI environment should run the real suite once and drop this note.

**14 of 25 analyses now implemented**: D, L, M, A, C, E (both pieces),
H (both pieces), I, X, W, P, G.

**Update, 2026-09-19 — V's two blockers both turned out to be
non-issues; built.** Chased down the same day, right after P/G. The
`promoted_at`-equivalent timestamp this file long assumed `paper_
performance` needed doesn't exist -- and isn't needed. Grepped
`PaperPerformanceStore.record_daily_return(s)`'s one real caller anywhere
in the codebase: `ShadowEvaluator.record_daily_paper_returns()`
(`vinu-live/vinu_live/shadow_evaluator.py`), which only ever iterates
`status=BENCHING` artifacts. So `paper_performance` is paper-period-only
by construction -- nothing appends to it once an artifact leaves
BENCHING -- and `calibration_entries` (populated only by closed *live*
broker positions, via `feedback_loop.py`) is live-period-only by the same
kind of construction. The two stores were already cleanly split; no join,
no new field, needed at all.
- **V built**: `vinu-reflection/vinu_reflection/reflection/
  paper_live_correlation.py`. Added the other real blocker --
  `vinu_infra.reflection.pearson_correlation()`, this codebase's first
  correlation-coefficient helper (everything before this only needed
  PSI). Scoped down to `scope_type=system` (one row across every
  promoted artifact) instead of the design doc's `strategy_family`
  breakdown -- same taxonomy B still doesn't have, same "don't invent B's
  scheme here" posture E's concentration piece already took. Also
  substituted a paper-vs-live distribution PSI for the write/no-write
  significance gate: the design doc's Condition is a single correlation
  coefficient recomputed fresh each cycle from the full history, which
  has no natural two-window PSI comparison the way every other analyst's
  Condition does (that's handled centrally by `write_finding()`'s own
  `compute_trend()` instead, diffing this cycle's correlation against the
  prior belief). "Correlation ≤ 0" implemented directly as
  `domain_floor_breached`.
- 6 new tests in `vinu-infra/tests/test_reflection.py`
  (`TestPearsonCorrelation`) ran green for real, 31/31 total --
  pandas-free, unlike the reflection-worker suite. `test_paper_live_
  correlation.py` hit the same sandbox pandas block as P+G's own test
  file (`vinu_agent.broker.research_link` pulls in `vinu_research.models`
  the same way); verified instead via the same kind of standalone
  harness, 15/15 checks passed.

**15 of 25 analyses now implemented**: D, L, M, A, C, E (both pieces),
H (both pieces), I, X, W, P, G, V. **B's taxonomy design is now the only
real, still-open next-win left** across all 6 clusters (see
`07-implementation-plan-status.md`'s ranked list).

**Update, 2026-09-19 — B's taxonomy designed and built.** The design
task this file's own ranked list called for, right after V. Confirmed
`signal_definition` before ruling it out: it's not messy free text as
originally assumed, it's *empty* -- no real writer anywhere ever sets
`Artifact.signal_definition` on a real artifact
(`service.py::_create_artifact_from_run` never touches it). Found
`ResearchRunRecord.user_idea` instead -- required on every real research
run (or auto-proposed by `ResearchService._propose_idea` when omitted,
never silently empty), and confirmed short/descriptive against every
real value in this codebase's own tests and non-LLM fallback string
("SMA crossover", "momentum breakout", "Trend-following strategy for
{stage} stage...").
- **B built**: added `Artifact.strategy_family` (`vinu-research/
  vinu_research/models.py`), same "written once at creation, never
  backfilled" contract as `regime_tag`/`freeze_hash`/`timeframe`.
  Classified via the new `vinu_research/strategy_family.py` -- a small,
  fixed, keyword-based taxonomy grounded in the style categories
  systematic-trading literature commonly uses (momentum, mean-reversion,
  breakout, volatility, stat-arb, event-driven), the same "research
  external convention, pick something grounded, document the reasoning"
  resolution `03-severity-and-trend.md`/`04-reference-baseline-config.md`
  used for the PSI-threshold questions. `unclassified` is a real 7th
  bucket for runs that state no style (autonomous refresh/refine runs),
  not a classifier failure. Wired into `service.py::
  _create_artifact_from_run`. `vinu-reflection/vinu_reflection/
  reflection/regime_strategy_coverage.py` built against it, joined to
  `trade_audit_log.jsonl`'s real exit rows (not `bench_history`, a
  per-artifact backtest series that can't answer a per-real-trade
  cross-tab) via `artifact_id`. `ic` dropped from the per-regime
  breakdown (no per-forecast expected-value data available); reports a
  raw reward-to-variability ratio instead of an annualized Sharpe (real
  trade holding periods vary, no single annualization factor applies).
- 14 new tests in `vinu-research/tests/test_strategy_family.py` plus 2 in
  `test_strategy_store_transitions.py` (`TestStrategyFamilyField`) ran
  green for real: 905/905 (889 + 16), once `pytest-asyncio` was
  installed in this pass's own venv (its absence, not a real regression,
  caused the async `test_service.py` suite to error on first attempt --
  installing it and rerunning showed all 905 genuinely pass). This also
  showed the earlier "Application Control policy blocks pandas
  permanently" note (P/G's and V's own entries above) was wrong -- a
  fresh venv, rebuilt to double-check, ran every previously-"blocked"
  suite for real, cleanly: `test_ingest_health.py` (7/7),
  `test_paper_live_correlation.py` (6/6), and this pass's own
  `test_regime_strategy_coverage.py` (6/6). The block was transient
  (most likely a one-time AV/allow-list scan against a freshly
  pip-installed binary), not a permanent constraint -- worth remembering
  as its own lesson: re-verify an environment limitation before writing
  it down as permanent, the same caution already earned by P/G's
  documentation-error verdict.

**16 of 25 analyses now implemented**: D, L, M, A, C, E (both pieces),
H (both pieces), I, X, W, P, G, V, B. Every one of the 6 analysts now has
every implementable analysis done -- what's left across all 25 is real
blockers, deferrals, and specs, not uninvestigated gaps (see
`07-implementation-plan-status.md`'s ranked list for what's next).

---

**2026-09-20 -- the 21 pre-existing Windows-only test failures got fixed
for real, not just documented.** Asked directly "the windows error is
been solved check teh errors and tell me" -- rechecked in a fresh venv
and found the exact same 19 `vinu-infra` + 2 `vinu-agent` failures as
before, contradicting the premise. Then asked to fix them instead of
just reporting them, so:
- 18 of `vinu-infra`'s 19 (`test_llm_client.py`, `test_llm_client_async.py`):
  `LlmClient.close()`/`AsyncLlmClient.close()` never called
  `TelemetryStore.close()` -- a method that already existed specifically
  to release `telemetry.db`'s sqlite connection before
  `TemporaryDirectory` cleanup, just never wired up at the one call site
  that mattered. Fixed in both `llm/client.py` and `llm/client_async.py`.
- 1 (`test_logging.py`): same class of bug for a log `FileHandler` --
  the test's own cleanup fixture closed it, but only in teardown, which
  runs after `TemporaryDirectory.__exit__` already tried and failed.
  Fixed by closing it inside the test, before the `with` block exits.
- 2 (`test_secrets.py`): compared `secrets_dir()` against a hardcoded
  POSIX path string instead of a `Path` object -- `Path` normalizes
  separators per-platform, so the string comparison only ever held on
  POSIX. Fixed the test; `secrets_loader.py` itself was already correct
  (it only ever runs inside Linux containers in production).
- 1 (`test_ticker_profile.py::test_lock_file_created_alongside`): a real
  cross-platform inconsistency in `ticker_profile.py` -- the `filelock`
  library's Windows backend deletes the `.lock` file on release by
  default; POSIX's native-lock backend doesn't need to. Fixed by passing
  `preserve_lock_file=True` to both `FileLock(...)` calls.
- `vinu-agent`'s 2 `TestOrderThrottle` failures: not a throttle-logic bug
  at all -- `OrderGuard.check()` always calls `_check_risk_budget()`,
  a real GET to `localhost:8090/portfolio/risk/status` with no service
  listening, and Windows' connection-refused round trip on a dead
  loopback port is measurably slower than Linux's -- slow enough that
  the throttle's 1-second real-clock window's oldest entries aged out
  before the 4th call in each test, so the throttle itself never got a
  chance to trip. Fixed by mocking `requests.get` in both tests
  (`test_order_guard.py`), the same pattern already used elsewhere in
  that file.
- Result, re-verified end to end in a fresh venv: `vinu-infra` 254/254,
  `vinu-agent` 1171/1171 passed + 4 skipped (`test_order_guard.py` alone
  went from 2 failed/81 passed to 83/83), and every other package
  (`vinu-research`, `vinu-reflection`, `vinu-stock-price`, `vinu-live`,
  `vinu-screener`, `vinu-portfolio`) still fully green. Zero known-bad
  tests left anywhere in the repo.

**2026-09-20 -- K, U, Y's new-writer decisions, asked and answered.**
This file's own ranked list had flagged K/U/Y as blocked on a real
product/priority call ("is the missing history worth a new writer") and
deliberately left it undecided rather than picking silently. Asked the
user directly which of the three to build; the answer was all three.
- **K** ("does retrieved memory actually help"): `vinu_agent/agent/
  context.py`'s `build_messages()` now captures the real `Fact.id`/
  `MemoryEntry.id` values it already had in hand (including the
  token-budget-trimmed case) into `last_injected_fact_ids`/
  `last_injected_memory_ids`. New `vinu_agent/storage/
  injected_context_log.py` (`InjectedContextLogStore`) is the writer --
  one row per `build_messages()` call, keyed by `session_id`, written
  from `session/service.py`, best-effort (a turn with nothing injected
  writes no row at all). Unlike U/Y below, K's analyst was built the
  same day: `vinu_reflection/reflection/memory_effectiveness.py`, same
  `TeamRunStore.get_latest_verdict_by_session_id` join key D already
  established (plus a new pure-read `TeamRunStore.
  distinct_session_ids_with_verdict()` for the session universe) --
  every chat turn is a potential data point, so there was no reason to
  wait for it to accumulate.
- **U** ("critical rebalance-bypass justification"): new
  `rebalance_request_history` table in `vinu-live`'s
  `rebalance_intake.py`, appended to by `consume()` right before it
  deletes the working-queue row (plus `history_for()`/`all_history()`
  reads). Writer only -- critical bypasses are rare events by design, so
  the table starts empty; the analyst itself waits for real production
  history to accumulate.
- **Y** ("earnings/macro-event holding loss"): new `events_archive`
  table in `vinu-stock-price`'s `events/store.py`, appended to by
  `replace_kind()` right before its existing delete-then-insert wipes a
  kind's rows (`INSERT OR IGNORE` keyed on the same PK, so a
  still-upcoming event seen across several consecutive pulls isn't
  re-archived with a wrong `archived_at`), plus a new
  `archived_overlapping()` read mirroring `upcoming()`. Writer only --
  same reasoning as U, the archive starts empty and Y needs closed
  trades whose window is already in the past.
- 41 new tests across `vinu-agent` (22: `TestLastInjectedMemoryIds`,
  `test_injected_fact_id_is_captured`, `test_injected_context_log.py`),
  `vinu-reflection` (7: `test_memory_effectiveness.py`), `vinu-live` (6:
  `TestRebalanceRequestHistory`), and `vinu-stock-price` (4:
  `TestEventsArchive`) -- all ran green, and the full suite for every
  affected package still passed end to end afterward with no
  regressions (`vinu-agent` 1183/1183 + 4 skipped, `vinu-reflection`
  83/83, `vinu-live` 442/442, `vinu-stock-price` 111/111).

**17 of 25 analyses now implemented**: D, L, K, M, A, C, E (both
pieces), H (both pieces), I, X, W, P, G, V, B. U and Y's new writers are
built and collecting data, but their analysts aren't -- see
`07-implementation-plan-status.md`'s ranked list for what's next.

---

**2026-09-20 -- O and R's new-writer decisions, investigated and closed
the same way as K/U/Y.** Asked to "go on" and implement the next ranked
item; investigated O, J, and R (the remaining new-writer-shaped items)
against the real code before asking anything, same discipline as K/U/Y:
- **O** ("are operator mandate limits protecting against real risk, or
  just friction"): confirmed `order_guard.py`'s operator-limit rejection
  sites (`_check_symbol_override`'s hard block, plus
  `max_order_value`/`max_position_pct`/`max_capital_utilization_pct` via
  `_effective_limit`) never looked up which artifact they were blocking
  -- pure numeric/override checks, no artifact lookup at all.
- **R** ("is the Planner ever triaging against silently stale angle
  data"): confirmed `ticker_summaries` is deliberately non-versioned
  (own docstring says so), but found the real "Planner triage event"
  call site (`ChangeGate`'s `run_gate_cycle` -> `_on_yes` in
  `scheduler_workers.py`) already has everything needed to check
  freshness LIVE, at the moment triage happens -- just never did.
- **J** ("screener churn as a regime-change indicator"): different
  shape entirely -- `Artifact.regime_tag` is a static, set-once field,
  never a system-wide time series with "transitions" to detect. No
  existing concept to build a writer against; flagged as needing a spec
  first (same category as S), not asked about.

Asked directly which of O/R to build; the answer was both. Built:
- **O**: new `GuardResult.blocked_artifact_ids: list[str]` field,
  populated at all four operator-limit rejection sites via a new
  `OrderGuard._blocked_artifact_ids(symbol)` helper (the same
  `list_artifacts_for_symbol` call `_check_active_artifact` already
  makes, broadened to `[ACTIVE, BENCHING, MONITORING]`). Surfaced into
  `order_rejected` audit entries from both of `trade_tool.py`'s real
  guard-result logging call sites (`guard.check()` and
  `guard.pre_approve()`). Every other rejection reason (kill switch,
  allowlist, daily limits, no-active-artifact, ...) deliberately left
  with an empty list -- not what O is asking about.
- **R**: new `_log_triage_freshness()` in `scheduler_workers.py`, called
  from `make_planner_on_yes`'s `_on_yes` (now takes an optional
  `run_log_reader` param, wired from `cli.py`'s existing
  `HttpRunLogReader`) right before the real triage check. Logs a
  `triage_freshness_check` event to the already-existing
  `TickerLedgerStore` -- no new table needed, this is exactly what it
  already exists to hold. Best-effort: a freshness-check failure never
  blocks the real triage/proposal it's observing.
- Both are writer-only, same reasoning as U/Y: `order_rejected` entries
  and `triage_freshness_check` events both only started 2026-09-20, so
  there's no real history yet for either analyst to compare against.
- 13 new tests (`TestBlockedArtifactIds` in `test_order_guard.py`,
  `TestPlannerTriageFreshnessLogging` in `test_scheduler_workers.py`)
  ran green, and the full `vinu-agent` suite still passed end to end
  afterward with no regressions.

Only J is left unresolved among the original five new-writer-shaped
items (K/U/Y/O/R) -- and unlike the other four, it's not actually a
new-writer decision at all, it's a missing spec. See
`07-implementation-plan-status.md`'s ranked list for what's next.

---

**2026-09-20 -- U, Y, O, and R's analysts built too, not left waiting on
data.** After U/Y/O/R's writers shipped, the plan had been to leave
their analyst modules unbuilt until real production evidence
accumulated (critical bypasses, past events, blocked-artifact
rejections, and triage cycles are all either rare or newly-started).
Asked directly: "you said some need real trades, can't we just build it
so when it starts it will be working right, can't we do that?" -- yes:
nothing about "no data yet" argues against writing and testing the
analyzer code itself, only against real findings showing up soon. Every
analyst in this codebase already starts at zero evidence and gates on
its own `MIN_EVIDENCE_COUNT` floor before writing anything -- that's the
exact mechanism that makes building ahead of data safe, and it's the
same reasoning K's own analyst was already built under in the previous
entry.

Built all four:
- **U** (`rebalance_bypass.py`): "subsequent realized P&L" reads
  `trade_audit_log.jsonl`'s real exit rows (same source B established),
  taking the first exit for a request's symbol at or after
  `requested_at`. `MIN_EVIDENCE_PER_GROUP=5` (rare events by design)
  gates both the system-wide rollup and any per-symbol finding.
- **Y** (`event_holding_loss.py`): closed trades come from
  `trade_audit_log.jsonl`'s entry+exit pairs joined by `trade_id`;
  overlap checked against both the live `events` table (a very recent
  trade might not be superseded by a pull yet) and the new
  `events_archive`. `MIN_EVIDENCE_COUNT=20` for the primary; the
  secondary per-ticker finding additionally requires the symbol's own
  delta to diverge from the system baseline, per the design doc's own
  Storage note.
- **O** (`mandate_limit_friction.py`): "eventual projected performance"
  reads `decay_snapshots` via `get_strategy_store().get_latest_snapshot
  (artifact_id)` -- same `get_strategy_store()` B/V already use. Found
  and fixed a real bug before it shipped: the first draft read
  `data_root_paths["vinu_research"]`, a key that doesn't exist anywhere
  in `cli.py`'s real wiring (only vinu_agent/vinu_live/vinu_screener/
  vinu_portfolio/vinu_stock/vinu_reflection do) -- would have raised
  `KeyError` in production despite passing its own tests (which had
  fabricated that key themselves). Caught by checking the real wiring
  against B/V's established pattern before calling it done, not by the
  tests alone.
- **R** (`triage_freshness.py`): windowing follows `angle_trust.py`'s
  adjacent-window PSI precedent rather than the design doc's literal
  "trailing band" phrasing. Found and fixed a second real bug while
  writing this one's tests: merging two `list_events_by_type()` results
  and re-sorting by `timestamp` doesn't preserve true order when
  multiple events land in the same second (`_now()` is second-
  resolution) -- routine under a burst of triage cycles, and the
  default case in any fast test. Fixed by ordering by SQLite's own
  `rowid` instead, and adding `list_events_by_types()` (queries several
  types in one pass, already in true insertion order) so the analyzer
  never needs to re-merge two separately-sorted lists at all.
- 25 new tests across the four analyzer test files, plus 9 more for the
  new pure-read methods they needed (`AuditLogger.read_all`,
  `TickerLedgerStore.list_events_by_type`/`list_events_by_types`) --
  all green. Smoke-tested `cli.py`'s real `run_cycle()` against
  completely empty mounted data roots: all 19 registered analysts ran
  with zero crashes and zero findings written (correct -- no evidence
  yet), confirming the wiring is genuinely production-ready, not just
  unit-tested in isolation. Full suites re-verified afterward with no
  regressions: `vinu-reflection` 108/108, `vinu-agent` 1205/1205 + 4
  skipped, `vinu-live` 442/442, `vinu-stock-price` 111/111, `vinu-research`
  905/905 + 1 skipped.

**19 of 25 analyses now implemented**: D, L, K, M, A, C, U, Y, E (both
pieces), H (both pieces), I, X, W, P, G, V, B, O, R. Every one of the 6
analysts now has every implementable analysis actually built, tested,
and registered -- U/Y/O/R will simply start writing real findings once
production data clears each one's evidence floor, no further code
needed. What's left (Q, N, S, F, T, J) is entirely real dependency-cost
tradeoffs, missing specs, and structural/schema blockers -- see
`07-implementation-plan-status.md`'s ranked list, now topped by J's spec
gap (the only remaining new-writer-shaped item that isn't actually a
new-writer decision).

---

**2026-09-20, later the same day**: after committing the U/Y/O/R work,
the user asked to keep going ("continue what is stoppping?"). Nothing
was actually blocked -- all prior work was complete and verified, just
sitting uncommitted; committed it (`486dc312`), then re-checked J since
it topped the ranked list.

J's original framing (`regime_tag` relabeling events) was re-confirmed
as a genuine dead end, not something to push past: traced
`Artifact.regime_tag`'s one real write site
(`research_artifact_writer.py:159`) back to `candidates[i]["regime"]`,
which comes from a backtest-window label a strategy candidate was tuned
against -- a static per-candidate tag, not a live signal, so there was
never going to be a "regime changed" event to log there no matter how
long this got investigated.

But that dead end didn't mean J itself was a dead end. Grepping more
broadly for "regime" in vinu-research surfaced
`market_regime_analogue.get_market_regime_stats_for_today()`: a real,
already-running, once-per-calendar-day computation -- a KNN match of
"today's" whole-market pattern (built from a reconstructed benchmark
price path) against historical regime windows, producing
`positive_ratio`/`avg_return`/`median_return`/`max_drawdown` across the
matches. It already feeds `TradeScore.regime_fit_score` on every
authored trade plan. Checked whether that score gets persisted anywhere
reflection could read (`SqliteStrategyStore`'s schema, `TradeScoreResult`
usage) -- confirmed it doesn't; the whole computation lives only in an
in-memory, process-lifetime `_DAY_CACHE` that gets cleared every day it
advances. Real signal, no durable home -- the same shape as several
other analyses this session (a real computation or event genuinely
happening, just never written down anywhere reflection can read it),
not the "invent a new concept" problem the original framing implied.

Proposed the reframe to the user before building anything (concrete
design: persist `market_regime_stats` durably, then PSI-trend it) --
approved. Built:
- `MarketRegimeHistoryStore` (`vinu-research/vinu_research/storage/
  market_regime_history.py`, new): one row per calendar date
  (`positive_ratio, avg_return, median_return, max_drawdown, n_matches,
  n_positive, n_negative`), `INSERT OR IGNORE` keyed on `date` so the
  first write each day wins and a later same-day call (already
  short-circuited by the day-cache) can never overwrite it with stale
  data.
- `get_market_regime_stats_for_today()` takes an optional
  `history_store` param now (default `None`, so every existing caller/
  test is unaffected) and calls `.record()` right where it already
  computes `result`, wrapped in its own try/except -- persistence
  failure fails open, same posture as the rest of that function.
- Wired from the one real call site, `trade_plan_authoring.py`'s Phase 4
  branch, via a new `get_market_regime_history_store()` helper in
  `vinu-agent/broker/research_link.py` -- same `VINU_RESEARCH_DATA_ROOT`-
  direct pattern `get_strategy_store()` already established for B/V/O,
  chosen over threading a store object through `author_trade_plan()`'s
  call chain (which doesn't currently receive one).
- `regime_drift.py` (new analyst, `vinu-reflection`): reads the full
  history, applies the same adjacent-window PSI trend as
  `triage_freshness.py`/`angle_trust.py` on `positive_ratio`
  (`CURRENT_WINDOW=10`, `REFERENCE_WINDOW_MAX=30`,
  `MIN_REFERENCE_WINDOW=10` -- smaller than R's 20/60 since this fires at
  most once per calendar day, not per triage cycle), `scope_type=system`,
  `scope_key="market_regime"`, `POLARITY_LOWER_IS_WORSE` (a falling
  positive-match ratio is the bad direction, same delta convention as
  U's `critical_outcome_delta`). Registered in `cli.py`'s
  `ANALYSTS`/`_SEED_FNS`.
- 15 new tests: 4 in `test_market_regime_analogue.py` (2 new
  persistence-related, on top of the module's existing 31), 6 in new
  `test_market_regime_history.py`, 5 in new `test_regime_drift.py`.

Two real caveats flagged and left as-is, not "fixed": `regime_analogue_
enabled` is off by default in `config.py`, and persistence only happens
on a calendar day some `author_trade_plan()` call actually runs the
Phase 4 branch -- sparser than a guaranteed daily heartbeat. Both are
product/config decisions, not code gaps; `regime_drift.py`'s own
evidence-floor windowing already makes it safe to have registered ahead
of data, same reasoning as U/Y/O/R.

Full suites re-verified in a fresh throwaway venv (`.tvj`, cleaned up
afterward): `vinu-reflection` 113/113, `vinu-agent` 1205/1205 + 4
skipped, `vinu-research` 912/912 + 1 skipped (one
`TestThreadSafety::test_concurrent_writes` flake seen only under
full-suite CPU contention -- reran 23/23 in isolation, confirmed
unrelated to this change; `sqlite_backend.py` itself was never touched).

**20 of 25 analyses now implemented**: everything from the prior entry
plus J. What's left (Q, N, S, F, T) is entirely real dependency-cost
tradeoffs, missing specs, and a structural blocker -- see
`07-implementation-plan-status.md`'s ranked list, now topped by Q/N's
dependency-cost decision since every remaining item is a decision or
schema change, not a design gap needing a fresh concept.

---

**2026-09-20, later still**: user asked to "think what can be done and
complete the next ones" against the remaining 5 (Q, N, S, F, T) --
re-investigated all of them rather than assuming the 2026-09-19/09-20
verdicts still held, same discipline as J's reframe.

**F: re-investigated and built.** The 2026-09-19 note ("genuinely
blocked, no real or weak join found... only `ticker`") turned out to be
incomplete, not wrong about what existed -- `significance_flags`
(`vinu_agent/agent/significance_triage.py`) has always also had
`created_at`, which combined with `ticker` is exactly the same
symbol+time weak join U's `rebalance_bypass.py` uses against
`trade_audit_log.jsonl`'s exit rows. That precedent simply didn't exist
in the codebase yet on 2026-09-19 (U was built 2026-09-20), so the
earlier pass had nothing concrete to reach for even after noticing
`created_at` was there. Re-checked with that precedent in hand: the only
real gap was `SignificanceFlagStore` having no way to read every flag
(`get_flag(flag_id)` is a single lookup, `response_rate()` only
aggregate counts). Added `all_flags()` -- ordered by SQLite `rowid`, not
`created_at`, catching the same same-second-tie ordering risk found (the
hard way) while building R, applied here proactively instead of waiting
to hit it. `significance_response_outcome.py` (new file) is F itself:
per `reason` (flag_type), splits flags into responded/unresponded label
lists using the next exit's realized_pnl sign for that ticker at or
after the flag's `created_at`, `MIN_EVIDENCE_PER_GROUP=5` (same rarity
order of magnitude as U). One real, permanent caveat: `llm_failure_rate`
flags use a sentinel ticker (`"SYSTEM"`) that never appears in
`trade_audit_log.jsonl`, so that flag_type never accumulates evidence --
correct, since there's no real position to check an LLM-failure alert
against in the first place. 9 new tests (6 for the analyst, 3 for
`all_flags()`).

**Q and N: re-investigated and found to be *more* blocked than the
2026-09-19 "dependency-cost" framing said, not less.** Both had been
filed as "the data exists in vinu-initial-analysis, importing that
package is just expensive" -- checked whether that was actually the real
blocker, the way it turned out not to be for J/F.
- Traced `weights_ref` (Q's whole premise) through the real attribution
  pipeline and found it never reaches any data vinu-research/vinu-agent
  stores at all: `angle_calibration_entries` has no `weights_ref` column
  (and no `symbol` column), and `Artifact.origin_angles` (the only real
  angle-attribution field) comes from `angles_used`, a plain list of
  angle-name strings an LLM research-manager self-reports
  (`research_artifact_writer.py:100`) -- disconnected from which
  checkpoint file actually produced a forecast. A free, torch-free
  Parquet/`.pt` reader would still have nothing to join against. Q needs
  new plumbing inside vinu-initial-analysis itself before it's buildable
  at all, not just a cheaper way to read what already exists.
- Checked whether N's `shock_clustering`/`shock_personality` angle data
  really requires the heavy import, since `fetch_personality_features`
  already reads it via `ResearchTools.get_angle_rows()`. It does avoid
  the heavy import -- but only by making a live HTTP call to
  vinu-initial-analysis's own running server. Every other analyst in
  this worker is a pure offline read of a mounted, committed file; none
  require any origin service to be up. Building N this way would be a
  first-of-its-kind live-service dependency for this worker, a real
  architecture decision, not an implementation detail.
- Neither built this pass -- both now need their own real decision (new
  cross-service plumbing for Q; a live-HTTP exception for N), tracked
  separately in `07-implementation-plan-status.md`'s ranked list rather
  than under one shared "dependency-cost" label.

**S and T: re-confirmed, not rebuilt.** S still needs a real
numeric-claim-extraction design (matching a number in Markdown against
the same number paraphrased in LLM prose) with no existing parser
anywhere in this codebase to build against -- rushing a regex heuristic
here risks false "divergence" findings that undermine the whole
reflection system's credibility, worse than leaving it unbuilt. T is
still blocked on `MaturityAssessor`, a separate, larger deliverable
outside the 25-analysis build entirely. Neither's prior verdict changed;
re-checking them didn't surface anything the earlier passes missed.

Full suites re-verified in a fresh throwaway venv (`.tvf`, cleaned up
afterward): `vinu-reflection` 119/119, `vinu-agent` 1208/1208 + 4
skipped.

**21 of 25 analyses now implemented**: everything from the prior entry
plus F. What's left (Q, N, S, T) is: two real new-plumbing/architecture
decisions (Q, N -- now tracked separately, not one shared deferral), one
missing spec (S), and one structural blocker (T) -- see
`07-implementation-plan-status.md`'s ranked list.

---

**2026-09-20, later still**: user asked to think harder specifically
about Q and N -- "think where it missed so that we implement it and fix
it." Traced one level deeper than the prior pass's "new plumbing needed"
(Q) / "live-HTTP dependency" (N) verdicts, rather than treating either
as settled.

**Q**: chased `weights_ref` to its one real write site --
`vinu-tools/vinu_tools/compute/backtest/walk_forward.py`'s
`weights_sink` call, invoked only from each DL angle's offline
`backtest.py`. Checked the LIVE forecast path each angle actually runs
on schedule (`compute.py`, dispatched by `vinu_initial_analysis.runner.
AngleRunner`) and confirmed directly: it never saves or references a
checkpoint at all. There is no "currently-live model checkpoint" concept
anywhere in production for these angles -- the prior pass's "thread
weights_ref through to AngleCalibrationEntry" plan would have had
nothing real to thread it *to*. What IS real:
`orchestration_registry.py` runs every DL angle's `backtest.py` on a
genuine (if quarterly, `quarters.py`) schedule, writing an immutable
`tier2` Parquet record with real `bar_ts`/`hit`/`weights_ref` per
walk-forward step. Confirmed the storage layer itself
(`vinu_initial_analysis/storage/parquet.py`'s `AngleStorage`) only
imports `pandas`/`pyarrow` -- the heavy deps belong to the angle-
computation modules, never the storage layer -- so reading it needs no
new dependency installed, just a data mount.

**N**: re-checked whether `shock_clustering`/`shock_personality` really
needed the live HTTP call the prior pass settled on, given the same
`AngleStorage` finding above applies to them too. It does avoid the
heavy import -- confirmed by reading `AngleStorage`'s own imports
directly rather than assuming. Traced the real schedule
(`AngleRunner.run()`'s `tier="tier2"` default, `quarters.py`'s
calendar-quarter boundary, `cli.py`'s `_compute_batch` always passing
the same quarterly `to_ts`) and found shock readings only ever refresh
once per quarter in the official record -- even the "continuous"
hourly-polling compute mode dedupes against the same quarterly window,
so there's no finer-grained tier3 rolling history to fall back on
either. "The trailing window immediately before a halt" doesn't exist
at that resolution; reframed to "the nearest quarterly snapshot before
the halt."

Also confirmed `safety_ledger.jsonl` is genuinely live-written for real
halts (`kill_switch.halt_trading()` -> `_ledger_append` ->
`get_safety_ledger().append("halt", {"scope": ...})`) -- the design
doc's "confirmed real" note for that store held up under a second look.

Proposed the reframe (a shared torch-free Parquet reader; Q around the
angles' own backtest-accuracy history; N around the nearest quarterly
snapshot) to the user before building -- approved. Built:
- `_initial_analysis_parquet.py` (new, vinu-reflection): `list_analyzed_
  symbols()`, `read_latest_run()` (DL angles -- one run's file already
  contains the full walk-forward series, concatenating runs would
  double-count, same reasoning `AngleStorage.read()`'s own docstring
  gives), `read_all_runs()` (shock angles -- each run is one new
  snapshot row, concatenating IS the real history), `to_utc_datetime()`
  (normalizes `stored_at` regardless of how tz round-trips through
  Parquet -- a real comparison bug caught before it could bite: a
  tz-naive pandas Timestamp compared against a tz-aware `datetime`
  raises).
- `dl_angle_backtest_health.py` (Q): adjacent-window PSI trend on `hit`
  (`CURRENT_WINDOW=30`/`REFERENCE_WINDOW_MAX=90`, matching A's
  `angle_trust.py`) plus a flat staleness check on the record's own
  `stored_at` age vs 2x `VINU_TIER2_PERIOD_MONTHS`. `DL_ANGLES` is the
  real 7 -- confirmed by grepping `weights_sink` usage across all 8
  angle names the design doc's own text lists; ARIMA never calls it (a
  classical per-step refit with nothing to checkpoint), resolving that
  file's own "7 vs 8 names" discrepancy along the way.
- `shock_reading_before_halt.py` (N): only *scoped* halts (`payload.
  scope` a real ticker, not `"global"`) join to a symbol's shock
  readings -- a global halt has no single symbol to check. Compares the
  nearest-before reading against the system-wide normal distribution via
  PSI (same two-group shape U/F use), using each shock angle's own
  simplest real field (`n_shocks`/`n_shock_dates`) rather than the
  richer nested stats.
- Real bug caught and fixed before shipping: both new analysts'
  accuracy/staleness findings for Q initially shared one scope_key per
  (symbol, angle) -- `reflection_beliefs`' real primary key is
  `(analyst_name, scope_type, scope_key)` with no `metric_name` column,
  so the second finding would have silently overwritten the first's
  belief row every cycle both fired. Fixed by giving the staleness
  finding its own `:staleness`-suffixed scope_key.
- `docker-compose.yml`'s `reflection-worker` gets a 7th mount
  (`./data/initial-analysis:/initial-analysis-data:ro`) -- a data mount
  only, `vinu_initial_analysis` is never installed as a package. No new
  Python dependency needed either: `pandas`/`pyarrow` are already
  transitively installed via vinu-research/vinu-stock-price.
- 20 new tests: 7 for the shared reader, 7 for Q, 6 for N -- all green
  on first real run. Smoke-tested `cli.py`'s real `run_cycle()` against
  empty/missing data roots: 23 analysts registered, zero crashes, zero
  findings (correct).

Only vinu-reflection + docker-compose.yml changed this pass -- no
vinu-agent/vinu-research source touched, so their full suites weren't
re-run (vinu-reflection's own 139/139 covers everything new).

**23 of 25 analyses now implemented**: everything from the prior entry
plus Q and N. What's left (S, T) is a real spec gap and a structural
blocker on a separate, larger component (`MaturityAssessor`) -- see
`07-implementation-plan-status.md`'s ranked list, now topped by S's spec
since Q/N no longer need any further decision.

---

Same day, asked directly which of 4 remaining directions to take (S's
spec, starting `MaturityAssessor`/"the brain", two small polish items
from the ranked list, or stop) -- chose the two small items, leaving S
and T open as real, undecided/blocked work rather than building past
what was asked.

- **V's per-`strategy_family` breakdown** (`paper_live_correlation.py`):
  the "revisit once B's taxonomy is resolved" note from the day before
  could finally be closed, since B (built earlier the same day) gave
  `strategy_family` a real value. Added one `scope_type=strategy_family`
  Finding per family clearing `MIN_SAMPLE_ARTIFACTS`, additive to (not
  replacing) the original `scope_type=system` row. Real bug caught before
  shipping, same class as Q's the day before: B already writes
  `scope_type=strategy_family`/`scope_key=<family>` under the identical
  `analyst_name` (`regime_risk_coverage` -- B and V share one
  `analyst_name`, differing only in `metric_name`), and
  `reflection_beliefs`' real primary key
  (`analyst_name, scope_type, scope_key`) has no `metric_name` column --
  a plain family-name `scope_key` for V's new finding would have silently
  overwritten B's belief row for that family every cycle. Fixed with a
  distinct suffixed `scope_key`
  (`f"{family}:paper_live_correlation"`). Also added a second
  `reflection_reference_config` seed row (`scope_type=strategy_family`,
  same `metric_name`) alongside the existing `scope_type=system` one --
  legitimately two rows since that table's real primary key includes
  `scope_type`, not a duplicate.
- **`regime_analogue_enabled` turned on**: added
  `VINU_RESEARCH_REGIME_ANALOGUE_ENABLED: "true"` to `docker-compose.yml`
  for *both* `agent-api` and `research-api` -- traced
  `trade_plan_tool.py` and found two real call paths for
  `author_trade_plan()`: the primary one runs in-process inside
  `agent-api` (`_author_and_freeze_trade_plan_in_process`), and a
  fallback goes over HTTP to `research-api`'s own
  `routes_trade_plan.py` only if the in-process call raises. Both
  containers resolve `ResearchConfig` from their own environment
  independently (`get_research_config()` -> `load_config()`), so setting
  the flag on only one would leave J's `regime_drift.py` blind on
  whichever path happens to run for a given call. This closes J's first
  documented caveat; the second (sparser-than-daily persistence, gated on
  Phase 4 actually running) is a structural property of the trigger, not
  a config gap, and stands as documented.
- Verification: fresh throwaway venv, real runs (not skipped) --
  `vinu-reflection` 144/144 (139 + 5 new: 4 per-family-breakdown tests +
  1 dual-seed-row test), `vinu-research` 912/913 passed + 1 skipped (one
  `TestThreadSafety::test_concurrent_writes` flake under full-suite
  contention, confirmed 23/23 in isolation -- same known flake as before,
  unrelated to this change), `vinu-agent` 1208/1212 passed + 4 skipped
  (matches prior baseline exactly). `docker-compose.yml` validated as
  real YAML (`yaml.safe_load`). Smoke-tested `cli.py`'s real `ANALYSTS`/
  `_SEED_FNS` registries after the change: still 23/23, unaffected.

Both closed the same day they were asked about -- S and T remain the
only two open items, exactly as scoped.
