# What's actually implemented (2026-09-22)

This is the real-code status of the angle comprehension hierarchy —
what exists in `vinu-components/` right now, how it actually works end
to end, and what's genuinely still missing or unproven. Everything
below is grounded in real file paths, real test runs, and real live-LLM
results captured this session — not aspirational.

## 1. What's implemented

### 1a. Per-angle glossary (Step 1-2)

- `vinu-agent/vinu_agent/tools/angle_glossary.py` — `ANGLE_GLOSSARY`, a
  condensed blurb for all 28 real angles.
- `vinu-agent/vinu_agent/tools/angles_tool.py::ExplainAngleTool`
  (`explain_angle`) — an on-demand tool, not an always-injected block.
  Wired into `angle_synthesizer` and `idea_generator`'s real tool lists.

### 1b. Cluster-scoped comprehension (Step 3, restructured after real testing)

The original design (one specialist call synthesizing all 28 angles at
once) was replaced after real live-LLM testing found it produces
confirmed hallucinations (an angle cited under the wrong cluster,
miscounted coverage totals). The real, current design:

- `vinu-agent/vinu_agent/tools/angle_clusters.py` — `ANGLE_CLUSTERS`,
  the canonical 7-cluster (A-G) scheme, all 28 real angles assigned,
  as real importable data (not just prompt text).
- `vinu-agent/vinu_agent/tools/angles_tool.py::GetClusterAnglesTool`
  (`get_cluster_angles`) — fetches only one named cluster's real
  members' data. Structurally cannot return another cluster's angles.
- `vinu-agent/teams/screener/agents/angle_synthesizer/` — rewritten to
  handle one ticker + one cluster per delegation (not all 28 angles).
  Returns `{cluster, angles_with_data, synthesis, anomalies}`.
- `vinu-agent/teams/screener/agents/cross_cluster_analyst/` (NEW
  specialist) — runs once per ticker after all 7 cluster calls return.
  Does cross-angle consensus checks (`compare_angles`, moved here from
  the old single-shot design since a comparable pair like arima/chronos
  spans two different clusters), trade-plan calibration, and real
  cross-cluster corroboration/redundancy analysis (the "Chapter 3"
  concept from `00-explanation.md`).
- `vinu-agent/teams/screener/manager_prompt.md` — orchestrates **8 real
  delegations per ticker** (7 per-cluster + 1 cross-cluster), assembles
  the final `cluster_digest` (forwarding each cluster's `synthesis`
  sentence verbatim) and `cluster_anomalies` (forwarding each cluster's
  `anomalies` list, kept as a **separate field**, never merged into the
  synthesis sentence).

### 1c. Persistence (Step 4)

`vinu-agent/vinu_agent/storage/ticker_summaries.py` — `TickerSummary`/
`TickerSummaryStore` gained three new columns this session:
`cluster_digest`, `cross_cluster`, `cluster_anomalies` (schema version
3→5). Two real write paths both carry all three through:

- **Path A** (batch runs): `screener_summary_writer.py::write_ticker_
  summaries`, called from `team.py` right after a screener run
  completes. Also runs `cluster_digest_validator.validate_cluster_
  digest` here and logs (warn-only, never blocks) any structural
  finding.
- **Path B** (single-ticker staleness refresh): `scheduler_workers.py::
  make_summary_agent_fn` + `ticker_gate.py::RunLogTrigger.refresh_if_
  stale`. This path had *no* JSON-block parsing at all before this
  session (only the deterministic `angle_digest`) — now parses the
  manager's raw content for this one ticker's cluster fields too.

### 1d. Guardrails (built alongside Step 4)

`vinu-agent/vinu_agent/tools/cluster_digest_validator.py` — two
narrow, deterministic checks against real ground truth: an invented
cluster key, or an angle named under the wrong cluster (regex-matched,
catches both `kalman_filters` and "Kalman Filters" phrasing). Wired in
as a warn-only check in Path A. **Not yet wired into Path B**, and the
failure policy beyond "log a warning" (drop? retry? block?) is still an
open decision, not made.

### 1e. Wired into `forecast_skill`'s real prompt (Step 5)

- `vinu-agent/vinu_agent/tools/trade_plan_tool.py::_read_summary_
  context` — reads all three new fields off the stored row.
- `vinu-research/vinu_research/trade_plan_authoring.py::_normalize_
  summary_context` — bounds and carries them through (`_bound_cluster_
  digest`, `_bound_cross_cluster`, `_bound_cluster_anomalies`), same
  defense-in-depth re-bounding discipline the existing `angle_digest`
  handling already used.
- `vinu-research/vinu_research/forecast_skill.py::_build_forecast_
  prompt` — renders `=== Cluster Digest ===` and `=== Cross-Cluster
  Analysis ===` sections, **alongside** (not replacing) the original
  `=== Angle Digest ===` section, per the plan's transition note (lets
  both shapes be compared directly, which is exactly what Step 6 did).

### 1g. Comprehension no longer fires on a single finished angle (2026-09-22)

Real gap, found by the user: `RunLogTrigger.check()` (`ticker_gate.py`)
triggers the 7-LLM-call comprehension pass whenever
`vinu-initial-analysis` reports a new `run_id` for a ticker — but a
`run_id` is written per angle (`orchestration_registry.py`), not per
full batch, so 1 of 28 angles finishing was enough to fire all 7
delegations against mostly-empty data.

Fixed: an optional coverage gate. `angles_tool.py::fetch_angle_coverage()`
does a cheap, non-LLM check of real `(angles_with_data, angle_count)`;
`RunLogTrigger` defers `refresh_if_stale` (without advancing
`source_run_id`, so the next cycle re-checks) until coverage clears a
configured fraction (`VINU_AGENT_ANGLE_COVERAGE_MIN_FRACTION`, default
`0.0` — ships inert), with a fail-safe cap
(`VINU_AGENT_ANGLE_COVERAGE_MAX_DEFERRALS`, default `3` within 24h) so a
permanently-broken angle can't stall a ticker's comprehension forever.
Every deferral is logged as a real `TickerLedgerStore` event
(`angle_comprehension_deferred`), not hidden. 6 new tests in
`test_ticker_gate.py`, full `vinu-agent` suite green (1296/1296). See
`01-plan.md` Step 8 for the full account.

### 1i. First real live end-to-end attempt — INCOMPLETE, real findings (2026-09-22)

**Read this section first if you're picking this up next.** Everything
above (1a-1h) was verified with real code and real unit tests, but never
run as the actual `vinu-agent` team-loop against a live model until
today. Full account in `01-plan.md` Step 10 — short version:

- Containers were running stale, day-old images the whole time — had to
  rebuild `agent-api`/`research-api`/`live-api`/`screener-api` before
  any of today's code was even reachable. **If you're testing this
  again, check the image build date matches your last code change
  first** (`docker inspect <container> --format '{{.Created}}'`).
- Found and fixed a real bug: `cross_cluster_analyst`'s prompt already
  said "call `get_all_angles` once" — the model called it 15 times
  anyway. Fixed structurally (a per-instance cache on `GetAllAnglesTool`,
  not a stronger prompt), confirmed live: refetches dropped 15 → 3.
- **Still did not complete.** Two real attempts, killed at ~85 min/109
  calls and ~55 min/76 calls respectively. No crash, no error at any
  point — the model was still steadily making real, successful calls
  both times, just very slowly, and the call rate was visibly slowing
  over the second run's own lifetime.
- **Not yet answered**: whether the 8-delegation design (realistically
  70-100+ individual LLM calls per ticker once each specialist's own
  multi-turn tool-calling is counted) is practical on this local model
  at all, or whether there's a second inefficiency still to find. Not
  guessed at — genuinely unknown, stopped deliberately rather than
  left running indefinitely or reported as a false success.
- **Not broken by any of this**: no corrupt/partial data anywhere (the
  persistence step is all-or-nothing), every other worker kept running
  normally throughout, two real pre-existing permission bugs (unrelated
  to this folder's own work) were found and fixed along the way
  (`./data/strategy-evaluation`, `./data/agent/trade_audit.log`).

### 1h. Manual override for the coverage gate (2026-09-22)

`RunLogTrigger.force_refresh(ticker, summary_agent_fn)` — runs
comprehension for one ticker immediately, bypassing both the run_id
check and the coverage gate from 1g. New CLI command
`vinu-agent force-comprehension <TICKER>`. Logged as a distinct ledger
event (`angle_comprehension_forced`), never conflated with the
automatic fail-safe's proceed-anyway path. Only affects the one ticker
it's run against. 5 new tests, full `vinu-agent` suite green
(1301/1301). See `01-plan.md` Step 9.

### 1j. Coverage gate's 1D assumption fixed (2026-09-23)

Real gap found while reviewing 1g's coverage gate: `fetch_angle_
coverage()` always checked coverage at `time_format="1D"`, but not
every angle produces 1D data at all — confirmed by reading `angles.
yaml`/each angle's own `spec.yaml`: 27 of 28 angles declare `1D` in
their `time_formats`, but `trend_session_structure` does not (only
`1min`/`5min`/`15min`/`1H`/`4H`). The real API route has no
"not applicable" signal, so querying that angle at 1D returned the same
empty result as "hasn't run yet" — meaning coverage could never exceed
27/28 (96.4%) for any ticker, forever. A `min_angle_coverage_fraction=
1.0` (the natural "wait for full coverage" setting) would have deferred
every ticker's comprehension permanently, with no way to ever satisfy
the gate — a real dead end, not a rare edge case.

Fix: `fetch_angle_coverage()` now reads each angle's own `spec.time_
formats` from the `/analysis/angles` response it already fetches, and
excludes any angle that doesn't declare the requested `time_format` at
all from both the numerator and denominator (not-applicable, not
not-ready). An angle with missing/malformed spec data is also excluded
(fails safe). 4 new unit tests (`TestFetchAngleCoverage` in `test_
angles_tool.py`) cover: full coverage when every angle supports the
format, the real `trend_session_structure` case (confirmed excluded via
asserting on the actual HTTP calls made — it's never even fetched),
missing-spec entries excluded, and a non-default `time_format` (`1H`)
filtering correctly. Full `vinu-agent` suite: 1309 passed, 4 skipped.

**Not yet verified live** — code-level + unit-test fix only, not
re-run against the real stack (live testing is paused per Step 10's
"stop fully" direction). Also still open, deliberately not addressed
here: the gate only ever checks one timeframe per call (default `1D`)
— it says nothing about whether an angle's *other* real timeframes
(the couple that also declare `1W`/`1M`/`6M`) are ready. See `01-plan.md`
Step 11 for the full account.

### 1f-bis. Cluster A's mixed forecast/non-forecast members disambiguated (2026-09-22)

Real seam found during review, independently corroborated by this
session's own live-LLM test: Cluster A groups `arima`/
`exponential_smoothing` (forward point forecasts) with `kalman_filters`
(explicitly NOT a forward forecast — a present-state filtered
level/trend estimate) under one "classical statistical" label, unlike
every other cluster's shared-output-shape grouping principle. The
Chapter 3 live run (`03-real-llm-findings-and-guardrails.md`)
independently misassigned `kalman_filters` into Cluster B on its own,
unprompted — the same seam surfacing as a real model error, not just a
naming quibble. Fixed with a targeted prompt rule rather than
restructuring the cluster scheme (membership unchanged, still 3+14+2+3+
2+2+2=28): `angle_synthesizer/prompt.md` gained a Cluster-A-only rule
telling the model to report `kalman_filters`' filtered level/trend
separately, never as a third forecast vote alongside `arima`/
`exponential_smoothing`. Not yet re-tested live against a real model —
same "wiring is real, live re-confirmation still open" caveat as the
rest of this file's Section 4.

### 1f. Prompt-injection defense (found broken, then fixed, both confirmed live)

Real testing (Step 6, checkpoint 01 trial 04) found that just labeling
a flagged value (`FLAGGED ANOMALY in Cluster E: ...` plus a system-
prompt rule to distrust it) does **not** stop the model from complying
with an embedded instruction — it read the flag, named the injection in
its own reasoning, and complied anyway. The fix that actually worked,
confirmed against the live model:

- A cluster with a real `cluster_anomalies` entry has its `cluster_
  digest` sentence **replaced with a `[WITHHELD]` marker** — the
  model never sees the (possibly laundered) synthesis text at all.
- Any raw `angle_digest` entry whose angle name is mentioned inside the
  anomaly description is **replaced with `REDACTED`** — the literal
  injected command text never reaches the prompt.

Re-tested live: the forecast changed from exactly matching the injected
payload (`direction=long, confidence=0.95, magnitude_pct=8.0`) to a
genuine `neutral/0.35` read, with the model's own reasoning correctly
explaining it excluded the flagged cluster.

## 2. How it works, end to end, for one ticker

1. Screener manager gets a ticker. Delegates to `angle_synthesizer`
   7 times, once per cluster (A-G), each a fully independent specialist
   invocation with zero visibility into any other cluster's data.
2. Each call: `get_cluster_angles(ticker, cluster)` → real data for
   just that cluster's members → one synthesis sentence + an anomalies
   list (empty if nothing flagged) + a coverage count.
3. Manager collects all 7, delegates once more to `cross_cluster_
   analyst` with the 7 synthesis sentences (plus its own tool access
   for consensus checks and calibration) → corroboration/redundancy
   findings.
4. Manager assembles the final per-ticker JSON: `summary`, `angles_
   with_data`, `angle_count`, `cluster_digest` (7 sentences),
   `cluster_anomalies` (only clusters with real findings), `cross_
   cluster` (consensus/calibration/corroboration/redundancy).
5. `write_ticker_summaries` parses that JSON, validates `cluster_
   digest` (warn-only), persists everything to `TickerSummaryStore`.
6. When a trade plan is authored: `_read_summary_context` reads the
   row → `_normalize_summary_context` bounds it → `_build_forecast_
   prompt` renders it, redacting any cluster/angle a real anomaly was
   found for, before the prompt ever reaches the LLM.

## 3. Real, verified test results (not assumed)

- 94+21+8 ≈ 260+ new/updated tests across both repos, all passing in
  throwaway venvs; full suites re-run clean (no regressions traced to
  these changes — remaining failures are pre-existing and unrelated).
- Live-LLM checkpoint 01 re-test (all 5 trials, real `_build_forecast_
  prompt` output sent to the real `hindsight-llm` 9B endpoint):
  - Trial 02, 05: stable passes, unchanged.
  - Trial 03 (garbage numeric input): **real improvement** — malformed
    values are now explicitly named as anomalies instead of being
    silently treated as real signals.
  - Trial 01 (narrative vs. numbers): **real regression** — flipped
    from correctly tracking deteriorating risk numbers to following the
    bullish narrative instead. Not a hard fail by the trial's own bar,
    but a confirmed step backward, not hypothetical.
  - Trial 04 (prompt injection): failed on the first mitigation
    attempt, fixed and confirmed on the second (redaction).

## 4. Real caveats — what's still missing or unproven

1. **UPDATED 2026-09-22 — attempted, still not completed.** A real
   attempt was made (see section 1i above, full account in
   `01-plan.md` Step 10): `vinu-agent force-comprehension AAPL` run
   live, twice, against the real `hindsight-llm` endpoint. Found and
   fixed one real bug (a redundant `get_all_angles` refetch loop). Even
   with that fixed, neither attempt actually completed within ~55-85
   minutes — not diagnosed further, not guessed at. So: the wiring is
   real, unit-tested, AND has now been genuinely attempted live for the
   first time — but a live run has still never actually finished and
   persisted a real result. Whether that's fixable, or whether this
   design needs a bigger/faster model to be practical at all, is the
   next real open question, not yet answered.
2. **Trial 01's regression is not root-caused, only observed.** A
   plausible mechanism is noted (the Cluster Digest section restates
   the bullish Cluster B signal a second time before Risk State
   appears) but not proven, and not retested after any fix.
3. **No repeated-run stability check.** Every trial above was run once
   at `temperature=0.2`. Whether trial 03's improvement or trial 01's
   regression are stable across repeated runs, or partly sampling
   noise, is unknown.
4. **`cluster_digest_validator`'s failure policy is still just a
   warning.** A confirmed structural violation (wrong cluster, invented
   key) is logged but still persisted and still reaches `forecast_
   skill` unless it also happens to trigger the separate `cluster_
   anomalies` redaction path (which only fires on `anomalies`, not on
   validator findings — the two systems are not yet connected).
5. **The validator doesn't catch the other confirmed hallucination
   class.** Fabricating a field an angle doesn't actually have (e.g.
   inventing a `direction` for `timesfm`, confirmed earlier this
   session) isn't checked at all — only cluster-membership and coverage
   counts are.
6. **Path B (single-ticker refresh) is not wired to the validator at
   all**, only Path A (batch runs) is.
7. **The HTTP fallback route's request schema is narrower than what
   flows in-process.** `routes_trade_plan.py`'s `GenerateTradePlanRequest.
   summary_context` is typed `dict[str, str | int] | None` — too narrow
   for `angle_digest` already, and now also too narrow for `cluster_
   digest`/`cross_cluster`/`cluster_anomalies`. Not touched this
   session (pre-existing narrowness, not introduced here), but real:
   the HTTP fallback path silently can't carry any of these nested
   fields, only the in-process path can.
8. **Step 7 (deciding whether `forecast_skill` should get its own
   multi-step reasoning instead of staying one call) is still
   explicitly deferred** — this session's Step 6 results are exactly
   the kind of evidence that decision was waiting on, but the decision
   itself hasn't been made.
9. **The full multi-timeframe "book" (fetching every angle at every
   real timeframe, not just 1D) is still not real production code.**
   Everything proving the split-cluster *design* also proved this
   concept out (`ticker-book-example/`), but nothing in the real
   pipeline calls `get_cluster_angles`/`get_all_angles` with a
   non-default `time_format` yet — that's a separate, deliberately
   unstarted cost/latency decision (`02-time-format-richness.md`).
10. **Checkpoint 02 (screener)** has never been run at all, live or
    otherwise — only checkpoint 01 (`forecast_skill`) has real trial
    coverage.
11. **The angle-coverage gate (1g) is not yet live-verified either.**
    Built and unit-tested against fakes (`FakeAngleCoverageReader`), but
    never run against a real `vinu-initial-analysis` deployment to
    confirm it actually changes when comprehension fires for a
    genuinely slow-finishing ticker in practice.
12. **The Cluster-A `kalman_filters` disambiguation rule (1f-bis) is
    prompt-only, not re-verified live.** Added in response to a real,
    independently-confirmed live-LLM error (the model misassigning
    `kalman_filters` into Cluster B on its own), but the fix itself
    hasn't been re-run against a live model yet to confirm it actually
    stops that misassignment — same open item as Trial 01's regression
    above (a fix proposed and applied, not yet proven).
13. **Found but NOT fixed, out of scope of this folder's own work**: a
    handful of `cli.py` call sites predating this session (`_send`,
    `_chat_loop`, the swarm command) use `async with AgentService()`,
    but `AgentService` only defines sync `__enter__`/`__exit__` —
    confirmed via `hasattr(AgentService, "__aenter__")` → `False`. Any
    of those code paths would raise `AttributeError` at runtime if
    actually exercised. Found while building 1h's `force-comprehension`
    command (which was initially written the same broken way, then
    fixed to plain sync before merging — see `01-plan.md` Step 9's
    "Real correction" note). Flagged here as a real, separate bug for
    whoever picks it up next, not silently worked around by leaving it
    undocumented.
