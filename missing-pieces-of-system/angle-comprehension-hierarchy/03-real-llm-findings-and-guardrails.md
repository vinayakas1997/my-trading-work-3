# Real problems found testing Chapter 1 + Chapter 2 against a live LLM, and the guardrails built for them

**Status: guardrail code built and tested (2026-09-22); not yet wired into
the real pipeline.** This documents what actually went wrong when
Chapter 1 (the 28-angle, all-real-timeframe index) and Chapter 2
(cluster comprehension) were run for real against two live local
models, and the real, tested code built in response.

## The problem, precisely

Two real models were run against the live `hindsight-llm` endpoint on
2026-09-22: `Qwen3.5-4B-Q4_K_M` and `Qwen3.5-9B-Q4_K_M` (both real GGUF
downloads, real llama.cpp `b11065` container, real RTX 5070 Laptop GPU).
Two independent, confirmed problems, each checked directly against the
real generated data rather than eyeballed:

**1. Non-convergence under real production settings.** At
`temperature=0.2, max_tokens=8000` (the real `forecast_skill` defaults —
see `vigrous-llm-testing/checkpoints/01-checkpoint-forecast_skill/
00-checkpoint-info.md`), both models failed to produce any output on
**4 of 5** checkpoint-01 trials — the model gets stuck in a repeating
"Wait... Okay..." self-re-derivation loop inside its own reasoning and
burns the entire token budget before ever emitting the final answer.
**Upgrading model size did not fix this** — the 9B failed on a
different 4 of 5 trials than the 4B did, same ~80% real failure rate.

**2. Hallucinations in cluster comprehension, present on both model
sizes.** Running the full 28-angle, all-real-timeframe Chapter 1 index
through an `angle_synthesizer`-style Chapter 2 synthesis (thinking
disabled, since (1) already ruled out thinking-enabled as usable at this
prompt size) surfaced two distinct, verified-against-ground-truth
hallucinations:
   - **Miscounted coverage.** The clean input has all 28 angles with
     real data (verified: `sum(row_count>0) == 28`). The 4B claimed
     27/28; the 9B claimed 26/28. Both wrong, in different ways.
   - **Cross-cluster attribution.** The 9B's prose narrative for
     Cluster B (deep-learning/foundation-model forecasts) named "Kalman
     Filters" as a contributing member. `kalman_filters` is a real
     Cluster A angle — the system prompt's own verbatim cluster list
     said so directly. The model contradicted an explicit in-context
     instruction, not an inference it had to derive.

Full real data, prompts, and responses: `ticker-book-example/
AAPL-full-28angle-clean.md`, `AAPL-full-28angle-uneven.md`, and this
session's `full_book_results.json` / `full_book_results_9b.json` (kept
alongside for reproducibility).

**Honest caveat on finding 2**: checked directly — in both real captured
runs, the cross-cluster violation appeared only in the discursive prose
section of the response, not in the final, compact `cluster_digest` JSON
block that a real pipeline would actually persist/forward (per
`screener/manager_prompt.md`'s "forward `cluster_digest` verbatim, never
re-summarize" rule, only that JSON block matters downstream). So this
specific captured run's *persisted* artifact happened to be clean. The
guardrail below is still real and tested — proven to correctly catch this
exact failure shape wherever it occurs (see the test reproducing it
verbatim) — just not proven to have been necessary for this one captured
JSON. Treated as defense-in-depth against a confirmed real failure mode,
not a fix for a confirmed live incident.

## What was built: `cluster_digest_validator.py`

Real code, not documentation-only:

- **`vinu-agent/vinu_agent/tools/angle_clusters.py`** (NEW) —
  `ANGLE_CLUSTERS` (the real 7-cluster A-G scheme, all 28 real angle ids,
  same data `angle_synthesizer/prompt.md` states verbatim) and
  `ANGLE_TO_CLUSTER` (the reverse lookup), as real importable Python data
  instead of only existing as prompt text.
- **`vinu-agent/vinu_agent/tools/cluster_digest_validator.py`** (NEW) —
  two narrow, deterministic checks, deliberately not a general
  fact-checker:
  1. `validate_cluster_digest(cluster_digest)` — flags any cluster key
     that isn't one of the real A-G, and flags any angle name mentioned
     inside a cluster's own sentence that's a real member of a
     *different* cluster (regex-based, matches both the raw
     `kalman_filters` form and human-written variants like "Kalman
     Filters").
  2. `validate_coverage_claim(stated_count, angle_row_counts)` —
     cross-checks a stated "N of 28 have data" claim against the real,
     deterministic row-count sum (the same "pure Python, not LLM
     reasoning" discipline `build_angle_digest` already uses for
     `angle_digest` — ground truth already exists in code, no need to
     trust the model's count).
  3. `validate(...)` bundles both into one `ValidationReport`.

**Tested**: `vinu-agent/tests/test_cluster_digest_validator.py`, 14
tests, all passing (verified in a throwaway `uv venv --python 3.12`).
Two tests reproduce the exact real failure text from today's captured
runs verbatim (`test_real_confirmed_failure_kalman_filters_cited_under_
cluster_b`, `test_real_confirmed_failure_4b_undercounted_27_of_28`) —
regression fixtures grounded in this session's real data, not invented
examples.

Real bug hit and fixed while building this: the first regex approach
used `re.escape(angle_id).replace(r"\_", ...)` to build a flexible
matcher — silently never matched anything, because modern Python's
`re.escape` no longer escapes underscores at all (only real regex
special characters), so there was never a `\_` in the escaped string to
replace. Caught by the test suite itself failing on the first run, not
assumed correct — fixed by escaping each underscore-separated part
independently and joining with the flexible separator instead.

## Future steps (not yet done)

1. **Wire into Step 4's real integration point.** `01-plan.md`'s Step 4
   (persist `cluster_digest`) already needs new parsing logic in
   `scheduler_workers.py::make_summary_agent_fn` to pull `cluster_digest`
   out of the screener team's raw `content`. This validator should run
   right there, before `upsert_summary()` — not built yet, Step 4 itself
   hasn't started.
2. **Decide the real failure policy.** Not yet decided: when
   `validate(...).ok` is `False`, does the pipeline drop the digest and
   fall back to the flat `angle_digest`, persist it anyway with a
   logged warning, or retry the LLM call once? This is a real product
   decision, not an implementation detail — needs to happen before Step
   4 is finished, not after.
3. **Coverage-check needs a real field to check against.** Today's test
   prompt didn't request a structured coverage-count field in JSON (only
   `cluster_digest` + `anomalies_found`) — the real production schema
   (`screener/manager_prompt.md`) already has `angles_with_data` as a
   real field per ticker, so `validate_coverage_claim` maps onto real,
   existing structure once wired in, not a new field that needs adding.
4. **Fabricated-field hallucination is NOT covered yet.** The other
   confirmed finding (both models inventing a `direction` value for
   angles like `timesfm`/`timer_timerxl` whose real schema never
   produces that field) needs per-angle real-schema awareness to check
   — harder than a name/cluster lookup, explicitly out of scope for this
   pass, flagged as real future work, not forgotten.
5. **Re-test with `enable_thinking: false` as a real candidate fix for
   problem 1** (non-convergence), separate from this guardrail work —
   the convergence failure looks like a thinking-mode issue, not a model
   size issue, per the 9B result. Not yet decided whether that's safe to
   set in real production (loses the model's reasoning trace entirely,
   trade-off not evaluated yet).
6. **Chapter 3 (cross-analysis) testing stays blocked** on this guardrail
   actually being wired in — testing Chapter 3 against an unvalidated
   Chapter 2 would compound, not isolate, whatever's still wrong.
