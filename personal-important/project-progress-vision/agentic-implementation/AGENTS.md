# AGENTS.md — Self-Documenting Implementation Workflow

## Purpose

Automatically structured phase-by-phase tracking for implementing the merged strategy-validation pipeline and unified storage/memory layer. Each phase gets a dedicated subfolder with planning, implementation details, and verification results — producing a complete audit trail from first commit to shipped capability.

---

## How to Start a Phase

1. Read `plan.md` to see the full build order and `status.md` to find the next unstarted phase
2. Create `phase-<NN>-<short-name>/` folder (e.g. `phase-01-harden-vinu-infra/`)
3. Create `00-implementation.md` — the phase overview (plan before code)
4. Create individual files for each work unit inside the phase
5. On completion, update `status.md` and optionally create a summary `.md` matching the session-closure pattern

---

## Phase Folder Structure

```
agentic-implementation/
├── AGENTS.md                           # This workflow definition
├── plan.md                             # Merged build order (the overall roadmap)
├── status.md                           # Overall progress tracker
├── phase-01-harden-vinu-infra/
│   ├── 00-implementation.md            # Phase overview — what, where, dependencies
│   ├── 01-task-<short-name>.md         # Individual work unit #1
│   ├── 02-task-<short-name>.md         # Individual work unit #2
│   └── test-summary.md                 # What tests were run and their results
├── phase-02-research-simulator-catalog/
│   ├── 00-implementation.md
│   ├── 01-task-schema-design.md
│   ├── 02-task-catalog-tables.md
│   ├── 03-task-checkpoint-resume.md
│   ├── 04-task-dedup-on-write.md
│   └── test-summary.md
├── phase-03-monte-carlo-algorithms/
│   ├── 00-implementation.md
│   ├── 01-task-block-bootstrap.md
│   ├── 02-task-price-path-resample.md
│   ├── 03-task-verdict-combiner.md
│   └── test-summary.md
├── phase-04-wire-monte-carlo-gate/
│   └── ...
├── phase-05-migrate-stock-price-news/
│   └── ...
├── phase-06-comparative-critique-agent/
│   └── ...
├── phase-07-unified-memory-layer/
│   └── ...
├── phase-08-trading-playbook-synthesis/
│   └── ...
├── phase-09-context-efficient-retrieval/
│   └── ...
├── phase-10-overfitting-robustness/
│   └── ...
├── phase-11-portfolio-correlation-gate/
│   └── ...
├── phase-12-shadow-live-validation/
│   └── ...
└── phase-13-judgment-quality-cost-realism/
    └── ...
```

---

## Agent Rules

1. **Start by reading `plan.md` + `status.md`** — understand the full sequence and where we are
2. **Create the next unstarted phase folder** — find the next phase with status `not started` in `status.md`
3. **Always start with `00-implementation.md`** — before writing any code, document the plan for this phase
4. **One task file per logical work unit** — split the phase into small, verifiable chunks
5. **Update `status.md` immediately** — after completing all tasks in a phase, mark it and update the timestamp
6. **Create `test-summary.md` per phase** — document what was tested and how, even if tests are automated
7. **Never skip documentation** — even if the change seems trivial, write the task file
8. **Reference the file paths you changed** — each task file must list every file modified with line ranges

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

- [ ] All task files written reflecting actual changes made
- [ ] All modified files are listed with line ranges
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
**Depends on:** Phase XX, Phase YY  
**Blocks:** Phase ZZ  

## What It Delivers

Brief description of what capability ships when this phase is done.

## Files Touched

| File | Service | Change Type |
|------|---------|-------------|
| `path/to/file.py` | vinu-infra | modify |
| `path/to/new_file.py` | vinu-research | create |

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
