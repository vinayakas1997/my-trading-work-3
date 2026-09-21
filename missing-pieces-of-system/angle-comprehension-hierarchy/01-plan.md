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
