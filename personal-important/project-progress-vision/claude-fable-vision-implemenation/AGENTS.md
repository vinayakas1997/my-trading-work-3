# AGENTS.md — Self-Documenting Implementation Workflow

## Purpose

Automatically structured phase-by-phase tracking for implementing **Live Risk, Personality
Memory & Execution** — the build-out of `vinu-live` (currently `NOT STARTED` in the governing
architecture doc `my-learning/new-direction-for-the-project.md`) plus the upstream deterministic
risk-math and research-time trade-plan-authoring work it depends on.

The full vision, rationale, and per-phase design detail already live in
[`../claude-fable-vision/`](../claude-fable-vision/):

- [`00-vision-summary.md`](../claude-fable-vision/00-vision-summary.md) — why this plan is shaped the way it is, and where each component belongs in the 3-environment architecture
- [`01-plan-overview.md`](../claude-fable-vision/01-plan-overview.md) — the phased build order this folder's `plan.md` mirrors
- `phase-01-shared-risk-math.md` through `phase-07-feedback-loop-closure.md` — one detailed design doc per phase, written *before* any implementation

**This folder (`claude-fable-vision-implemenation/`) is where execution tracking happens** —
mirroring [`../agentic-implementation/`](../agentic-implementation/)'s workflow exactly, so the
same discipline (plan before code, one task file per work unit, test-summary per phase,
status.md kept current) applies here too. Read the source vision doc for a phase *before*
creating its implementation folder — this `AGENTS.md` governs *how* to track the work, not *what*
the work is.

---

## How to Start a Phase

1. Read `plan.md` here to see the full build order and `status.md` to find the next unstarted phase
2. Read the matching `phase-NN-<name>.md` in [`../claude-fable-vision/`](../claude-fable-vision/) for the full design — what it is, impact, open questions
3. Create `phase-<NN>-<short-name>/` folder in *this* directory (e.g. `phase-01-shared-risk-math/`)
4. Create `00-implementation.md` — the phase overview (plan before code), written against the source vision doc's design, not a reinterpretation of it
5. Create individual files for each work unit i nside the phase
6. On completion, update `status.md` and optionally create a summary `.md` matching the session-closure pattern

---

## Phase Folder Structure

```
claude-fable-vision-implemenation/
├── AGENTS.md                                  # This workflow definition
├── plan.md                                    # Execution build order (mirrors ../claude-fable-vision/01-plan-overview.md)
├── status.md                                  # Overall progress tracker
├── phase-01-shared-risk-math/
│   ├── 00-implementation.md                   # Phase overview — what, where, dependencies
│   ├── 01-task-<short-name>.md                # Individual work unit #1
│   ├── 02-task-<short-name>.md                # Individual work unit #2
│   └── test-summary.md                        # What tests were run and their results
├── phase-02-personality-shock-angles/
│   └── ...
├── phase-03-live-book-ledger/
│   └── ...
├── phase-04-forecast-and-tradeplan-authoring/
│   └── ...
├── phase-05-circuit-breaker/
│   └── ...
├── phase-06-execution-orchestrator/
│   └── ...
└── phase-07-feedback-loop-closure/
    └── ...
```

---

## Agent Rules

1. **Start by reading `plan.md` + `status.md`** — understand the full sequence and where we are
2. **Read the matching source vision doc in `../claude-fable-vision/` before creating the phase folder** — do not re-derive design decisions already made there; if something in the source doc is ambiguous or marked as an open question, resolve it explicitly in `00-implementation.md` rather than silently picking an interpretation
3. **Create the next unstarted phase folder** — find the next phase with status `not started` in `status.md`, respecting the `Depends On` column in `plan.md`
4. **Always start with `00-implementation.md`** — before writing any code, document the plan for this phase
5. **One task file per logical work unit** — split the phase into small, verifiable chunks
6. **Update `status.md` immediately** — after completing all tasks in a phase, mark it and update the timestamp
7. **Create `test-summary.md` per phase** — document what was tested and how, even if tests are automated
8. **Never skip documentation** — even if the change seems trivial, write the task file
9. **Reference the file paths you changed** — each task file must list every file modified with line ranges
10. **Respect the architecture's non-negotiable rule** — per `my-learning/new-direction-for-the-project.md`, any LLM or non-deterministic component lives exclusively in Research-Simulations (`vinu-research`). Initial-Analysis and Live-Trading (`vinu-live`) must be entirely deterministic. If a phase's implementation would introduce a runtime LLM call outside `vinu-research`, stop and flag it rather than proceeding — this is the single rule the whole plan (especially Phase 4 → Phase 6) is built to protect.

---

## Status Values

| Status | Meaning |
|--------|---------|
| `not started` | Phase is planned but no work has begun |
| `in progress` | Phase folder exists and work is underway |
| `completed` | All tasks done, tests pass, verification complete |
| `blocked` | Waiting on a dependency (noted in `plan.md` deps) |
| `superseded` | Phase was replaced/absorbed by another phase (see note in `plan.md`) |

---

## Verification Checklist (end of each phase)

- [ ] Source vision doc (`../claude-fable-vision/phase-NN-*.md`) re-read and design followed, not reinterpreted
- [ ] All task files written reflecting actual changes made
- [ ] All modified files are listed with line ranges
- [ ] No LLM/non-deterministic call was introduced outside `vinu-research` (see Agent Rule 10)
- [ ] Tests pass (automated test suite or manual verification)
- [ ] `test-summary.md` created with results
- [ ] `status.md` updated

---

## Templates

### `00-implementation.md` — Phase Overview

```markdown
# Phase NN: <Phase Title>

**Status:** IN PROGRESS | COMPLETED
**Started:** YYYY-MM-DD
**Source doc:** ../claude-fable-vision/phase-NN-<name>.md
**Depends on:** Phase XX, Phase YY
**Blocks:** Phase ZZ

## What It Delivers

Brief description of what capability ships when this phase is done (should match the source
vision doc's "What it is" section — flag here if this implementation deviates and why).

## Open Questions Resolved

Any open design question the source doc left unresolved (e.g. Phase 4's storage-location
question), and the decision made here.

## Files Touched

| File | Service | Change Type |
|------|---------|-------------|
| `path/to/file.py` | vinu-tools | modify |
| `path/to/new_file.py` | vinu-live | create |

## Tasks in this Phase

| # | Task File | Description | Status |
|---|-----------|-------------|--------|
| 1 | `01-task-xxx.md` | Short description | PENDING |
| 2 | `02-task-yyy.md` | Short description | PENDING |

## Dependencies Met

- [ ] Dependency phase XX completed
- [ ] Dependency phase YY completed
```

### `NN-task-<short-name>.md` — Individual Task

```markdown
# Task N: <Short Title>

**Status:** PENDING | DONE

## Purpose

What this specific work unit accomplishes within the phase.

## Approach

How it will be implemented — key design decisions, relevant patterns to follow.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `path/to/file.py` | XX-YY | Description of edit |
| `path/to/new_file.py` | — | Created |

## Verification

- [ ] Tests pass
- [ ] Type checks pass
- [ ] Linter passes
- [ ] Manual verification done
- [ ] No runtime LLM call introduced outside `vinu-research`
```

### `test-summary.md` — Phase Test Summary

```markdown
# Phase NN — Test Summary

## Tests Run

| Test File | Test Name | Result |
|-----------|-----------|--------|
| `tests/test_foo.py::test_bar` | test_bar | PASS |
| `tests/test_baz.py::test_qux` | test_qux | PASS |

## Coverage Notes

Any gaps in coverage, manual testing performed, or integration checks done.

## Verdict

All tests pass. No regressions detected.
```
