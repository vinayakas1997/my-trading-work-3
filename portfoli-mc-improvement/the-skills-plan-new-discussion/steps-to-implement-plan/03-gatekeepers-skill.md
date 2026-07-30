---
name: 03-gatekeepers-skill
status: Not Started
phase: 2
code: B1
depends_on: [01-verification-pass, 02-tool-wiring]
unlocks: [07-optimizer-rules-skill]
---

# Step 03 — Gatekeepers Skill (rewrite as an interface, not an invention)

## Why this step

An earlier draft of this skill (still sitting in
`project-understanding/skills/gatekeepers/`) invented 10 gatekeepers with
placeholder metric names (`trade_count`, `sharpe_oos`, `maxdd_is`...). Then
we found that `vinu-simulator` already runs `compute_validation_verdict` —
a real, documented, 7-test statistical verdict — automatically on every
single backtest, and `vinu-research` already has PBO (probability of
backtest overfitting), a correlation gate, and a promotion bar. The
placeholder draft is a weaker, invented shadow of something stronger that
already runs automatically. This step replaces it.

## What we're achieving

A `gatekeepers` skill whose job is **interpretation, not invention**: it
teaches the agent to read the real fields that already exist —
`compute_validation_verdict`'s `all_passed`/`reasons`, PBO's overfitting
probability, the correlation gate's `CorrelationVerdict`, and
`promotion.py`'s `PromotionVerdict` — and combine them into one coherent
judgment about a candidate result. Any genuinely new check (like a minimum
trade-count floor, which nothing above appears to enforce) gets added
explicitly and separately, clearly marked as new, not blended in as if it
were equivalent to the statistically-validated ones.

## Where it matters in the future

This is what Step 07 (`optimizer-rules`) judges every sweep candidate
against. If this skill is wrong or invented, the sweep converges on
parameter sets that look good by fake criteria instead of real statistical
ones — the exact overfitting risk the underlying validation code exists to
catch. Getting this right is the difference between a sweep that produces
robust settings and one that produces a curve-fit illusion of robust settings.

## How it connects to other steps

- **Depends on Step 01** for what the risk critic in `llm.py` actually
  checks — if it substantially overlaps `compute_validation_verdict`, this
  skill should say so explicitly and avoid telling the agent to run a
  redundant second check.
- **Depends on Step 02** — this skill only works if a tool exists that
  returns the real `validation` block, PBO score, correlation verdict, and
  promotion verdict for a given result. Do not write this skill's `SKILL.md`
  referencing a tool call that doesn't exist yet.
- **Unlocks Step 07** — the optimizer can't decide "did this candidate pass"
  without this skill defining what passing means.

## Substeps

1. Read `vinu_simulator/engine/validation.py::compute_validation_verdict`
   in full (not just the excerpt already captured in the discussion
   transcript) — confirm the exact keys in the `validation` dict it expects
   and returns.
2. Read `vinu_research/gates/correlation_gate.py`'s `CorrelationVerdict`
   and `vinu_research/promotion.py`'s `PromotionVerdict` in full — confirm
   their exact fields.
3. Read `vinu_research/pbo.py::probability_of_backtest_overfitting`'s
   return dict shape.
4. Rewrite `project-understanding/skills/gatekeepers/SKILL.md` to teach the
   agent: what each of these four real outputs means, how to combine them
   into hard-fail vs soft-fail (a `compute_validation_verdict` failure is
   hard; PBO above some threshold might be soft; use judgment grounded in
   what each check is actually for, not an arbitrary severity assignment).
5. Rewrite `rules.yaml` to reference the *real* field names confirmed in
   substeps 1–3, deleting any placeholder metric name that doesn't map to
   something real. Add net-new checks (e.g. minimum trade count) only where
   substeps 1–3 confirm nothing already covers it, and label them clearly
   as "new, not from existing validation."
6. Cross-check against `backtest-diagnose/SKILL.md`'s existing hard-gate
   checklist — reconcile any overlap rather than leaving two skills
   disagreeing about the same threshold.

## Open risks / assumptions

- Carries forward Step 01's open question about the risk critic overlap —
  do not finalize this skill until that's answered.
- The severity model (hard vs soft) is a judgment call this step has to
  make explicitly and explain, not leave implicit — a future reader should
  be able to see *why* a given check is hard vs soft, not just that it is.

## Definition of done

- [ ] `SKILL.md` and `rules.yaml` reference only real, confirmed field
      names — zero placeholders remain.
- [ ] Every check's severity (hard/soft) has a written reason.
- [ ] Overlap with `backtest-diagnose` explicitly reconciled, not ignored.
- [ ] A tool call from Step 02 is named explicitly in `SKILL.md` as how the
      agent actually fetches this data.
