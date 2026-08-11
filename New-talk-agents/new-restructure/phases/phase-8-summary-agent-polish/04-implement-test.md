---
name: phase-8-implement-test
status: built -- Phase 8 is implemented, tested, and wired
purpose: record of what was actually touched, what was tested, and the real result -- not a plan anymore, a report. Final phase of the 9-phase build.
---

# Phase 8 -- Implementation record

Built 2026-08-11, directly following Phase 7 in the same session. This is
the last of the 9 phases (0-8) -- see the session's overall summary for
the full build.

## Real gap found beyond the original plan

**`CalibrationTracker` tracks calibration per `artifact_id` (a specific
trade-plan artifact), not per angle name.** The plan's framing --
"feeds the Summary Agent which angles to actually trust right now, based
on each angle's own historical forecast accuracy" -- assumes a
per-angle historical calibration signal exists. It doesn't: confirmed by
reading `calibration.py`, `hypothesis_registry.py`, and every angle's own
storage directly, nothing anywhere populates calibration entries keyed by
angle name (only Phase 4/5/6's trade-plan flow populates entries, keyed
by `artifact_id`). Built the REAL capability instead of the assumed one:
if a ticker has an associated `type='trade_plan'` artifact, the Summary
Agent can now cite its real, trackable calibration history -- genuine
evidence, just scoped to one specific trade plan's forecast accuracy, not
a per-angle trust weighting. This is flagged explicitly in the tool
descriptions and the updated prompt, not silently substituted for what
the plan originally described.

## Files touched

| File | Status | What changed |
|---|---|---|
| `vinu-components/vinu-agent/vinu_agent/agent/angle_consensus.py` | new | `compare_directional`/`compare_magnitude`/`compare_categorical` -- deterministic, never an LLM judgment call. Third `insufficient_data` outcome whenever either angle's `row_count <= 0`. Every result's `reasoning` cites the real compared values. |
| `vinu-components/vinu-agent/vinu_agent/agent/angle_consensus_adjacency.yaml` | new | The companion adjacency config (not embedded in a prompt) -- `regime_analysis`/`trend_lifecycle` label pairs, grounded in each angle's own real classification code (`compute.py`/`lifecycle.py`), not guessed. |
| `vinu-components/vinu-agent/tests/test_angle_consensus.py` | new | 16 tests, including the "config edit changes the outcome without any code change" proof. |
| `vinu-components/vinu-agent/vinu_agent/agent/trade_plan_calibration.py` | new | `get_trade_plan_calibration()` -- in-process first (`broker/research_link.py`'s `get_strategy_store()`, confirmed real and live today, not blocked on the pending vinu-research migration), HTTP fallback to the same route `vinu-portfolio`'s own `_fetch_outcome_confidence` already calls. Returns which transport actually answered. |
| `vinu-components/vinu-agent/tests/test_trade_plan_calibration.py` | new | 6 tests, including the in-process-vs-HTTP identical-result proof. |
| `vinu-components/vinu-agent/vinu_agent/tools/angle_consensus_tool.py` | new | `CompareAnglesTool`. |
| `vinu-components/vinu-agent/vinu_agent/tools/trade_plan_calibration_tool.py` | new | `GetTradePlanCalibrationTool`. |
| `vinu-components/vinu-agent/vinu_agent/tools/find_trade_plan_tool.py` | new | `FindTradePlanArtifactTool` -- the missing symbol -> `type='trade_plan'` artifact_id lookup neither the plan nor any existing tool provided; `get_trade_plan_calibration` needs a real `artifact_id` as input and nothing resolved one from a ticker before this. |
| `vinu-components/vinu-agent/tests/test_angle_consensus_tool.py`, `test_trade_plan_calibration_tool.py`, `test_find_trade_plan_tool.py` | new | 6 + 2 + 4 tests. |
| `vinu-components/vinu-agent/teams/screener/agents/angle_synthesizer/AGENT.md` | modified | Tool list gains `compare_angles`, `find_trade_plan_artifact`, `get_trade_plan_calibration`. |
| `vinu-components/vinu-agent/teams/screener/agents/angle_synthesizer/prompt.md` | modified | New "Cross-angle consensus" and "Calibration" sections (which pairs to compare, how to report each `compare_angles` outcome, the not-found-is-normal framing for trade-plan lookup, the "has data but underperformed" vs. "no data" wording distinction the guard rail requires). Final-answer checklist extended from 3 to 5 items. |
| `vinu-components/vinu-agent/tests/test_phase8_end_to_end.py` | new | The realistic-mix scenario from `03-test.md`'s end-to-end case -- agree/diverge/insufficient_data angles plus high- and low-trust calibration, all in one test, each condition asserted distinctly. |

## Design deviations from `01-plan.md`/`02-guard-rail.md`, and why

- **Calibration wiring answers "has this trade plan been right over
  time," not "has this angle been right over time."** See the real gap
  above -- the plan's assumed capability doesn't exist anywhere in this
  codebase; building the real, adjacent one and being explicit about the
  difference (in the tool description, the prompt, and this record) was
  judged more honest than either forcing a fake per-angle mapping or
  skipping the calibration piece entirely.
- **`FindTradePlanArtifactTool` was not named in the plan but was
  necessary to build.** `get_trade_plan_calibration` needs a real
  `artifact_id`; nothing existing resolved "does this ticker have a
  trade-plan artifact, and what's its id" before this phase.
- **The adjacency config currently has exactly one angle pair**
  (`regime_analysis`/`trend_lifecycle`) rather than several. Each entry
  was grounded in the angles' own real classification code, not guessed
  from a design doc's worked example -- populating more pairs (e.g.
  `arima`/`chronos` as a directional pair doesn't need the adjacency
  table at all, but other categorical pairs would) is real, incremental
  follow-up work, matching the guard rail's own framing ("will need
  tuning as more angle pairs get added").
- **No real multi-turn LLM run validates the updated `angle_synthesizer`
  prompt end-to-end.** Every deterministic piece this phase built
  (`angle_consensus.py`, `trade_plan_calibration.py`, all three tools) is
  fully tested; whether the LLM actually calls `compare_angles`/
  `find_trade_plan_artifact`/`get_trade_plan_calibration` and reports
  their real outputs faithfully needs a live run against the configured
  OpenRouter model, deliberately not done in this pass -- same reasoning
  as Phase 1's equivalent, real-LLM-dependent tests (cost/rate-limit risk
  on the free-tier model, confirmed real earlier this session).

## Test results

```
vinu-agent:    567 -> 602 passed (full suite; 16 + 6 + 6 + 2 + 4 + 1 = 35 new tests)
vinu-research: 592 passed, 1 skipped (full suite; no vinu-research changes this phase)
```

No regressions in either package's full suite.

## Known follow-ups (not blocking, not silently dropped)

- **No real per-angle calibration tracker exists anywhere** -- if this
  capability is genuinely wanted later, it needs its own storage design
  (angle name as the tracked key, not `artifact_id`), not a retrofit of
  `CalibrationTracker`.
- **The adjacency config needs more pairs** as more angles get
  cross-checked in practice -- a config-only change, no code/prompt
  redeploy needed, per its own design.
- **`DEFAULT_MAGNITUDE_TOLERANCE` (0.15) is a first-pass, unvalidated
  default**, same category as every other untuned threshold across this
  build.
- **A real live-LLM run against the updated `angle_synthesizer` prompt**
  is the natural next validation step, whenever a deliberate real-LLM
  test pass gets scheduled (see Phase 1's equivalent follow-up).

---

# All 9 phases (0-8) are now built, tested, and documented

This closes the 9-phase build plan (New-talk-agents/new-thinking/
new-restructure/phases/) end to end. Each phase's `04-implement-test.md`
is the honest, as-built record of what that phase actually did --
several phases (2, 4, 5, 6, 7) found and fixed real gaps the original
plan didn't anticipate, confirmed by reading the real code directly
rather than trusting the plan's own assumptions. Every phase's full
package test suite was run and confirmed green (no regressions) before
moving to the next.
