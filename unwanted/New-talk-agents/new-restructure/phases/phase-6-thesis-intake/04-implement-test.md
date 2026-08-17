---
name: phase-6-implement-test
status: built -- Phase 6 is implemented, tested, and wired
purpose: record of what was actually touched, what was tested, and the real result -- not a plan anymore, a report.
---

# Phase 6 -- Implementation record

Built 2026-08-11, directly following Phase 5 in the same session. Unlike
Phases 4/5, this was genuinely new build (the plan's own framing), not a
fix -- but it still surfaced real gaps in what the plan assumed already
existed.

## Real gaps found beyond the original plan

1. **`Hypothesis`/`Evidence` had no `source` concept at all.** The plan
   assumed tagging `source="human"` was just a matter of discipline at
   the call site; reading `models.py`/`hypothesis_registry.py` directly
   found neither dataclass had ever carried a provenance field. Added
   `Hypothesis.source: str = "system"` (default preserves every existing
   caller's behavior) plus a NEW `Hypothesis.create_from_human()`
   classmethod that hardcodes `source="human"` with **no source
   parameter to override** -- a stronger structural guarantee than
   "required, no default" (02-guard-rail.md's literal wording): there is
   no parameter to forget or mistype at all. A new dedicated route,
   `POST /research/hypotheses/human`, is the only way to reach it.
2. **The plan's two-skill-*files*-in-one-directory layout doesn't fit the
   real `SkillsLoader` mechanism.** `_load_from_dir` requires a
   `SKILL.md` per directory and has no concept of loading an arbitrary
   second file from the same skill by name -- `strategy-definitions.md`
   and `risk-rules.md` sitting bare in one `thesis-intake/` directory
   would never be discovered at all. Built as two independent skills
   instead -- `skills/thesis-intake-strategy-definitions/SKILL.md` and
   `skills/thesis-intake-risk-rules/SKILL.md` -- each loadable via the
   existing `load_skill` tool with zero code changes, and each still an
   unambiguous single-file diff target for the audit log (arguably a
   *cleaner* fit for "confirm the project's existing skill-loading code
   doesn't already have a hook point" than the plan's original layout).
3. **No tool existed to read `TickerSummaryStore`.** Thesis Intake's plan
   requires reading "the Summary Agent's stored read," but no
   `get_ticker_summary`-shaped tool existed anywhere in `tools/`. Built
   `GetTickerSummaryTool`.

## Files touched

| File | Status | What changed |
|---|---|---|
| `vinu-components/vinu-research/vinu_research/models.py` | modified | `Hypothesis.source` field, `Hypothesis.create(..., source="system")`, new `Hypothesis.create_from_human()`. |
| `vinu-components/vinu-research/vinu_research/hypothesis_registry.py` | modified | `_to_dict`/`_from_dict` persist `source` (defaults `"system"` for pre-existing rows with none). |
| `vinu-components/vinu-research/vinu_research/server/routes_hypothesis.py` | modified | New `POST /hypotheses/human` (`CreateHumanHypothesisRequest`) -- Thesis Intake's only write path. `_serialize` now includes `source`. |
| `vinu-components/vinu-research/vinu_research/server/routes_introspect.py` | modified | `_serialize_hypothesis` includes `source`. |
| `vinu-components/vinu-research/tests/test_hypothesis_registry.py`, `tests/test_routes_hypothesis.py` | modified | 4 + 3 new tests. |
| `vinu-components/vinu-agent/vinu_agent/agent/thesis_intake_gate.py` | new | `ThesisIntakeGate` (THGATE) -- `jaccard_similarity()` (stated, testable near-duplicate definition), shared K-cap query against `TickerLedgerStore.count_events(event_type="candidate_proposed")`. Fails open toward *allow* on either lookup erroring (cost gate, not a safety gate -- see design deviations). |
| `vinu-components/vinu-agent/tests/test_thesis_intake_gate.py` | new | 10 tests. |
| `vinu-components/vinu-agent/vinu_agent/agent/skill_audit.py` | new | `SkillAuditStore` + `check_skill_edits()` -- content-hash + line-count diff, scoped to `AUDITED_SKILL_PATHS = ["thesis-intake-risk-rules/SKILL.md"]` only. |
| `vinu-components/vinu-agent/tests/test_skill_audit.py` | new | 6 tests, including the "strategy-definitions edit never appears in this log" scoping proof. |
| `vinu-components/vinu-agent/vinu_agent/tools/ticker_summary_tool.py` | new | `GetTickerSummaryTool`. |
| `vinu-components/vinu-agent/tests/test_ticker_summary_tool.py` | new | 3 tests. |
| `vinu-components/vinu-agent/vinu_agent/tools/submit_thesis_tool.py` | new | `SubmitThesisTool` -- the orchestrator's second entry point. Runs THGATE before any LLM call; on pass, constructs and runs `TeamManager("thesis_intake")` directly (same pattern as `delegate_to_team.py`, not a call to that tool, since this needs two sequential team runs); on `WORTH_CHECKING`, writes the human hypothesis (best-effort) + the `candidate_proposed` `TickerLedger` event (shared counter's write side), then hands off to the real `research` team. |
| `vinu-components/vinu-agent/tests/test_submit_thesis_tool.py` | new | 7 tests. |
| `vinu-components/vinu-agent/tests/test_phase6_thesis_intake_scoping.py` | new | 4 tests -- `theory_reviewer`'s tool list structurally excludes code-execution tools; `submit_thesis` appears in no team's own tool list (orchestrator-only, confirmed by walking the real `teams/` directory). |
| `vinu-components/vinu-agent/teams/thesis_intake/` | new | `TEAM.md`, `manager_prompt.md`, `agents/theory_reviewer/{AGENT.md,prompt.md}`. |
| `vinu-components/vinu-agent/skills/thesis-intake-strategy-definitions/SKILL.md`, `skills/thesis-intake-risk-rules/SKILL.md` | new | The two reference documents theory_reviewer reads. |

## Design deviations from `01-plan.md`/`02-guard-rail.md`, and why

- **Two skill directories, not two files in one directory** -- see gap 2
  above; the real `SkillsLoader` mechanism forced this, and it satisfies
  the stated goal (unambiguous single-file diff target) at least as well.
- **THGATE fails open (toward *allow*) on a lookup error, not closed.**
  `02-guard-rail.md` doesn't specify a direction for THGATE's own
  failure mode (unlike Phase 3's Kill Switch, which explicitly does).
  Reasoned from first principles, matching this build's established
  three-way split of fail-closed directions: THGATE is a **cost** gate
  (worst case of a false "allow" is one avoidable LLM call), the same
  category as Phase 0's RunLog trigger -- not a safety gate like the Kill
  Switch, where the wrong default risks real money. Blocking a human's
  legitimate submission on a transient DB error would directly violate
  THGATE's own stated guard rail ("too strict and the gate saves
  nothing").
- **The K-cap's write side (`candidate_proposed` TickerLedger events) is
  only wired from Thesis Intake's own hand-off in this phase.** Phase 1
  (sweep-engine wiring) predates Phase 0's `TickerLedger` and never wrote
  candidate-proposed events for watchlist-originated ideas. Retrofitting
  that into an already-complete phase was judged out of scope here; the
  shared-counter *query* is proven correct across both `source` values by
  construction (tests seed synthetic `watchlist`-sourced events directly)
  even though only the `human` side has a live production writer today.
  Flagged as a real follow-up, not silently assumed done.
- **`SubmitThesisTool` constructs `TeamManager` directly, twice, rather
  than calling `delegate_to_team`.** THGATE must run before ANY LLM call,
  and a `WORTH_CHECKING` verdict needs a SECOND team run (`research`)
  afterward -- neither fits `delegate_to_team`'s one-shot shape, so this
  tool mirrors its wiring/construction pattern directly instead of
  wrapping it.

## Test results

```
vinu-research: 591 passed, 1 skipped, 1 unrelated flaky failure (full suite; 7 new tests)
                -- test_sqlite_backend.py::TestThreadSafety::test_concurrent_writes
                   ("database is locked" under full-suite load) confirmed
                   passing in isolation (20/20); untouched by this phase,
                   not a regression.
vinu-agent:    545 passed (full suite; 10 + 6 + 3 + 7 + 4 = 30 new tests)
```

No real regressions in either package.

## Known follow-ups (not blocking, not silently dropped)

- **`candidate_proposed` events from the watchlist/Planner side** --
  see design deviation above. Needed before the shared K-cap is fully
  real end-to-end (today it only ever sees human-side writes in
  production).
- **The skill-edit audit log has no live caller yet.** `check_skill_edits()`
  is correct and tested but nothing invokes it automatically -- same
  "not wired to a live loop" shape as Phase 0's `RunLogTrigger`/
  `ChangeGate` and Phase 4's `ShadowEvaluator`. A natural call site is
  service startup (`AgentService.__init__` or `create_app`), not decided
  here.
- **`NEAR_DUPLICATE_THRESHOLD` (0.5) and `K_CAP_DEFAULT` (3) are
  first-pass, explicitly-flagged-provisional defaults**, same category as
  every other untuned threshold across this build.
- **Jaccard token-overlap is a real but crude similarity measure** --
  case-insensitive whole-word overlap only, no stemming/synonyms. Good
  enough to be genuinely testable and deterministic (the guard rail's
  actual requirement), not claimed to be semantically sophisticated.
