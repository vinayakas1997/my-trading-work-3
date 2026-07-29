# Inefficiency Fix Session — Context & Process

## What We're Working On

Fixing all 38 inefficiencies documented in `inefficiency-audit.md` across the vinu-components pipeline.

### Severity Breakdown

| Severity | Count |
|----------|-------|
| 🔴 CRITICAL | 2 |
| 🟠 HIGH | 18 |
| 🟡 MEDIUM | 14 |
| 🔵 LOW | 4 |
| **Total** | **38** |

### Components Covered

- `vinu-stock-price` — FP-1, FP-4, DA-11, DA-12, DA-26, DA-27, DA-28
- `vinu-news` — FP-3, DA-2, DA-3, DA-23, DA-24, DA-25
- `vinu-tools` — DA-1, DA-10, DA-29, DA-30, DA-31, DA-32
- `vinu-initial-analysis` — DA-4, DA-5, DA-6, DA-13, DA-14
- `vinu-strategy` — DA-7, DA-15
- `vinu-simulator` — DA-16, DA-17, DA-18, DA-19
- `vinu-research` — FP-2, FP-6, DA-8, DA-9, DA-20, DA-21, DA-22
- `run_pipeline.py` — FP-5

## Status Tracking

All fix progress is tracked in **`STATUS.md`** at the root of this directory. It contains a table of all 38 problems with columns for Status, Date Fixed, and Notes. The header row shows the running tally.

## Future Features Tracking

During problem analysis, you may discover feature gaps that aren't bugs but would add significant value. Document these in **TWO** places:

1. **solution.md** — Add a `## Future Features / Open Questions` section at the bottom of the solution.md for the problem you're fixing
2. **FUTURE-FEATURES.md** — Add the same entry to the central tracking file at `analysis-1/FUTURE-FEATURES.md`

Each entry should include:
- Feature name
- What it does
- Why it matters
- Which component
- Complexity estimate (Low / Medium / High)

## Process (One-by-One)

For each inefficiency (starting from highest severity):

1. **Discuss** — Read the problem, understand root cause, discuss with user
2. **Fix** — Implement the solution in the codebase
3. **Document** — Fill `one-by-one/<problem-folder>/solution.md` with:
   - Problem ID & severity
   - Root cause analysis
   - Solution implemented
   - Files changed
   - Verification notes
4. **Update STATUS.md** — Change the problem's status from `Pending` to `Completed`, add the date, and update the summary counts at the top and bottom

## Documentation Format

Each solution file follows this structure:

```markdown
# <ID> <Severity> <Title>

**Component:** `<component>`
**Files Changed:** `<file1>, <file2>`

## Problem

Brief description of what was wrong.

## Root Cause

Why it happens — the code pattern or design issue.

## Solution

What was changed to fix it.

## Verification

How to confirm the fix works (manual checks, tests, commands).
```

## Folder Structure

```
analysis-1/
├── AGENTS.md               ← This file
├── inefficiency-audit.md    ← The full audit document
└── one-by-one/
    ├── FP-1-backfill-triggers-all-symbols/
    ├── FP-2-research-ignores-simulator/
    ├── ... (38 total)
```
