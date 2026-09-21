# Angle comprehension hierarchy

**Status (2026-09-22): the split-cluster design is now REAL code, not
just a tested prototype.** `angle_synthesizer` is now cluster-scoped (7
real delegations per ticker, one per cluster, via a new
`get_cluster_angles` tool that structurally can't return another
cluster's data), and a new `cross_cluster_analyst` specialist handles
the ticker-level work (consensus checks, calibration, and real
cross-cluster corroboration analysis). See "Real implementation
(2026-09-22)" below for the full file list and test results.
Real gaps confirmed against current code, full 28-angle clustering scheme
drafted below. See `01-plan.md` for the ordered build steps.

## The idea, in one paragraph

Today, every LLM prompt that touches angle data (the `Angle Digest` in
`forecast_skill`'s forecast call, `angle_synthesizer`'s own reasoning)
gets a flat list of up to 30 raw `angle_name.field: value` lines, with no
explanation of what any angle actually measures and no grouping of
related signals. That's the wrong shape for genuinely comprehending
something the size of a 28-angle read — the fix is a layered,
hierarchical digestion instead of a flat dump: explain each angle, then
group related angles into thematic clusters and synthesize each cluster,
then let the final decision call read the clusters, not the raw 28
lines. Explicitly worth the extra steps/latency this adds — that's a
deliberate tradeoff, not an oversight.

## Where this came from

Found live while designing `missing-pieces-of-system/vigrous-llm-testing/`'s
checkpoint 01 trials (`forecast_skill`) — trial 04 (prompt injection via
Angle Digest) and trial 01 (narrative vs. numbers conflict) both trace
back to the same root cause: the LLM has no grounding for what an angle
name means, and no structured way to weigh 28+ of them at once. Two real
gaps confirmed by reading the code, not assumed:
1. `vinu-initial-analysis/vinu_initial_analysis/catalog/angles.yaml` has
   a real `title`/`purpose`/description per angle, but nothing in
   `angles_tool.py`, `forecast_skill.py`, or any team's `prompt.md` ever
   reads it — the LLM sees raw values with zero explanation.
2. `forecast_skill.py::generate_forecast` is a single, one-shot call
   (deliberately — "ONE LLM call per plan") with no separate reasoning
   pass and no tool access, so even if it had angle explanations, it has
   no room to reason about 28+ of them individually before committing to
   a structured forecast.

## What's in this folder

- **`00-explanation.md`** — the detailed grounding: both gaps with real
  file/line citations, the three-tier design (per-angle digestion →
  clustered synthesis → final decision), and the real 28-angle
  clustering scheme (7 thematic clusters, every one of the 28 real angle
  ids assigned, not a sample).
- **`01-plan.md`** — the ordered build plan: glossary data, the
  `explain_angle` tool, `angle_synthesizer`'s updated prompt,
  `forecast_skill`'s updated prompt shape, and re-running
  `vigrous-llm-testing/checkpoints/01-checkpoint-forecast_skill`'s
  existing trials against the fixed version to prove it actually helped.
- **`02-time-format-richness.md`** — a separate, related question that
  came up while fixing the hardcoded-1D gap (now actually fixed in code,
  see below): now that a non-default timeframe is genuinely fetchable,
  is checking one ever actually worth it? Lays out the option menu (a
  simple confirmation check vs. a real, measured cross-timeframe
  richness score) and the concrete extension needed
  (`AngleCalibrationEntry` gaining a `time_format` field) to answer that
  empirically instead of guessing.
- **`angle-reference/`** — the 28-file "comprehensive book," one file
  per real angle: verbatim `angles.yaml` data, a clearly-labeled FAKE
  example result, and a draft condensed glossary blurb (the raw material
  step 1 below turns into real code).
- **`ticker-book-example/AAPL.md`** — a worked, hand-authored example of
  the 3-chapter book structure for 15 of the 28 angles at 2 timeframes
  each. Demonstrates a real genuine-divergence case (Cluster B + D
  corroborating each other) and a real redundant-check case (Clusters
  E/F/G unchanged across timeframes) side by side.
- **`ticker-book-example/AAPL-full-book-real-3chapter-run.md`**
  (2026-09-22) — all 3 chapters produced end-to-end by a real live model
  for the first time (none hand-authored): Chapter 1 (28-angle index),
  Chapter 2 as **7 separate per-cluster calls** (the design that won
  after real testing — zero cross-cluster hallucinations vs. the
  single-shot version's confirmed one, and 7/7 correct coverage counts
  on the clean dataset vs. 0/2 for single-shot, at no real latency
  cost), and Chapter 3 (cross-analysis) run for real for the first time.
  Chapter 3 found genuine, non-fabricated corroboration (Cluster
  B+D on the clean run, A+D on the uneven run) and correctly identified
  the redundant clusters (C/E/F/G) — but inconsistently: Cluster A shows
  the same real pattern as B/D in both runs, yet only 2 of the 3 ever
  got surfaced together, never all three, and not the same 2 each time.
  Full pipeline, real model, real data: under a minute per ticker.
- **`04-implemented.md`** (2026-09-22) — the definitive real-code
  status: full inventory of what's implemented (glossary, split-cluster
  design, persistence, forecast_skill wiring, the injection redaction
  fix), how it works end to end for one ticker, the real Step 6 re-test
  results (mixed — trial 03 improved, trial 01 regressed, trial 04
  fixed after two attempts), and 10 honest caveats on what's still
  missing or unproven. Read this first for current state.
- **`03-real-llm-findings-and-guardrails.md`** — what actually went
  wrong running Chapters 1+2 against two real local models (4B and 9B,
  both confirmed via real testing that a bigger model does NOT fix
  either the non-convergence or the hallucination problem), and the real
  guardrail code built in response: `vinu-agent/vinu_agent/tools/
  angle_clusters.py` + `cluster_digest_validator.py`, 14 passing tests,
  two of them reproducing this session's exact real hallucination text
  verbatim as regression fixtures. Not yet wired into the real pipeline
  — see that file's "Future steps" for what's left.
- **`ticker-book-example/AAPL-full-28angle-clean.md`** and
  **`AAPL-full-28angle-uneven.md`** (2026-09-22, real LLM run, not
  hand-authored) — the full 28-angle version, every angle at every one
  of its own real `time_formats` (173 real rows), sent to the live
  `hindsight-llm` endpoint via a single-shot adaptation of
  `angle_synthesizer`'s real prompt. The clean run **confirmed two real
  hallucinations** (miscounted 27/28 when all 28 had data; invented a
  `direction` field for 2 angles whose real schema never has one). The
  uneven run deliberately corrupted 5 realistic ways (a zero-data angle,
  asymmetric cluster coverage, a real error field, a malformed `NaN`,
  a stale-flagged duplicate) — **all 5 were caught correctly**, but the
  model also introduced a 6th, unplanted rule violation on its own
  (misassigned `kalman_filters`, a real Cluster A member, into Cluster
  B). Reproducible: `gen_full_book.py` generates the data,
  `run_full_book_test.py` sends it to the live endpoint.

## Current state

`01-plan.md` steps 1-2 are **built and tested**: the 28-entry
`angle_glossary.py` module and the on-demand `explain_angle` tool, wired
into `angle_synthesizer` and `idea_generator`'s real tool lists.

Step 3 is now **REAL, restructured code** (2026-09-22), superseding the
earlier single-shot design after real live-LLM testing proved the split
design out:
- **`vinu-agent/vinu_agent/tools/angles_tool.py`** — new
  `GetClusterAnglesTool` (`get_cluster_angles`), scoped to one real
  cluster's own members, sharing a refactored `_fetch_angle_results`
  helper with the original `GetAllAnglesTool`.
- **`vinu-agent/teams/screener/agents/angle_synthesizer/`** — rewritten
  to be cluster-scoped: takes a ticker + one cluster letter, calls
  `get_cluster_angles`, returns just that cluster's synthesis.
- **`vinu-agent/teams/screener/agents/cross_cluster_analyst/`** (NEW
  specialist) — the ticker-level work that no longer fits inside one
  cluster's call: consensus checks (`compare_angles`), trade-plan
  calibration, and the real Chapter 3 cross-cluster corroboration/
  redundancy analysis.
- **`vinu-agent/teams/screener/manager_prompt.md`** — rewritten for the
  new **8 delegations per ticker** (7 per-cluster + 1 cross-cluster),
  extended JSON schema (`cross_cluster` block added alongside
  `cluster_digest`).
- **Tested**: 94 tests passing (44 in the angle/cluster-specific files,
  50 more across `test_team.py`/`test_tools_discovery.py` confirming the
  real `screener` team loads both specialists correctly with their real
  tool lists) — verified in a throwaway venv, plus a full-suite run
  (1220 passed, 25 failed/2 errored, all in unrelated files needing real
  network/services, confirmed pre-existing via file-overlap check, not
  regressions).

Not yet done: real end-to-end verification against a live LLM endpoint
of this exact new code path (today's live-model proof used standalone
test scripts shaped like this design, not the actual `vinu-agent`
team-loop code itself running it) — a real difference worth closing
before trusting this in production. Also still open: `cluster_digest_
validator.py`'s guardrails (see `03-real-llm-findings-and-guardrails.md`)
are built and tested but not wired into this new flow at all yet.

Next real step is step 4: persisting `cluster_digest` (now 7 real
per-cluster entries) — `cluster_digest` can't reuse `angle_digest`'s
deterministic-Python shortcut (it only exists inside the LLM team's own
output), so persisting it needs a new parsing step in
`scheduler_workers.py`, not just a storage column — see `01-plan.md`
step 4 for the full trace (not yet updated for the 8-delegation shape).

Separately, and already **built and tested**: the two hardcoded-1D spots
`02-time-format-richness.md` describes (`GetAllAnglesTool`'s v1 fetch URL
and its fallback read route) are fixed in real code — see
`vinu-agent/vinu_agent/tools/angles_tool.py` and `vinu-initial-analysis/
vinu_initial_analysis/server/routes_read.py`. The *mechanism* is real;
nothing calls it with a non-default timeframe yet (that's the still-open
"is it worth it" question `02-time-format-richness.md` covers).
