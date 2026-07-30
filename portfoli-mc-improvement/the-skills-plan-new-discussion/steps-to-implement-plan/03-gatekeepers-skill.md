---
name: 03-gatekeepers-skill
status: Done
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
  **Resolved by Step 01 (see its Findings §1):** `_build_risk_critic_prompt`
  is only a prompt formatter — it evaluates nothing. The real risk critic
  is `loop.py::_default_risk_critic`, three layers: cross-run comparison
  (can force `STOP`), `_rule_based_check` (deterministic thresholds:
  max_drawdown < -15%, Sharpe < 0.5, win_rate < 40%, CVaR₉₅ < -3%,
  recovery > 120 days, turnover > 2000%, Sharpe p-value > 0.05 — plus
  angle context, which only ever adds suggestions, never changes the
  verdict), and an LLM layer that can only **upgrade** REFINE → PASS/STOP,
  never downgrade. This runs *inside the research loop*, before a
  candidate is ever considered done — it does not overlap
  `compute_validation_verdict`/PBO/correlation/promotion, which run
  *after*, on a candidate already accepted. **This skill must document
  both layers as a sequence** (`_default_risk_critic` gates whether
  refinement continues → `compute_validation_verdict`/PBO/promotion gate
  whether an accepted result is trustworthy), not treat them as
  redundant or pick one over the other.
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

## What was actually built

Both `project-understanding/skills/gatekeepers/SKILL.md` and `rules.yaml`
were fully rewritten after reading, in full, all four real mechanisms:
`compute_validation_verdict` (vinu_simulator/engine/validation.py),
`probability_of_backtest_overfitting` / PBO (vinu_research/pbo.py),
`CorrelationVerdict` (vinu_research/gates/correlation_gate.py), and
`meets_promotion_bar` / `PromotionVerdict` (vinu_research/promotion.py).

**Key structural decision:** gatekeeping was split into two distinct
moments rather than one flat list — `candidate_evaluation` (judging one
backtest result, mid-sweep/mid-refinement) and `promotion_evaluation`
(judging whether an already-accepted artifact should go live). These ask
different questions and use different mechanisms; the original
placeholder draft conflated them into one list.

**Severity model, with reasons written into `rules.yaml` directly (not
left implicit):**
- Hard at candidate-evaluation time: `compute_validation_verdict.passed`
  (fails closed by design), plus trade count / profit factor / drawdown
  ratio / IS-OOS Sharpe — all four **reused from `backtest-diagnose`'s
  existing hard-gate checklist**, not re-derived, since
  `compute_validation_verdict` doesn't check any of them.
- Soft at candidate-evaluation time: PBO (judges the *selection process*
  across candidates, not one candidate's own validity) and
  `CorrelationVerdict` (fails **open** by default — opposite of
  `compute_validation_verdict`'s fail-closed default, called out
  explicitly so it isn't misread).
- Hard at promotion time: `PromotionVerdict.eligible`, which folds the
  correlation gate back in as hard — the same check is soft in one moment
  and hard in the other, and both files say so explicitly, with why.

**Reconciliation with `backtest-diagnose`:** done by reuse, not
duplication — `rules.yaml`'s candidate-evaluation entries cite
`backtest-diagnose/SKILL.md` as their `source` rather than restating
thresholds. One real, unresolved inconsistency was found and
**deliberately left unresolved, flagged instead of silently decided**:
`backtest-diagnose` calls OOS Sharpe > 0.7 a hard gate, but
`loop.py::_rule_based_check` (the actual running risk critic) only
treats Sharpe < 0.5 as a soft suggestion. Both are real, currently-running
code that disagree with each other — this skill documents the tension
rather than picking a side.

**Two new gaps surfaced during this rewrite** (documented in `SKILL.md`,
not solved here — out of scope):
- PBO is computed once per research run but never persisted
  (`ResearchStorage.insert_run`/`update_run` has no `pbo` column) — only
  visible in that run's original live response.
- There's no dedicated read-only way to preview promotion eligibility
  without risking the mutating `POST /promote` call — `SKILL.md`
  documents an approximation using the existing `GET /research/artifacts`
  route's `deflated_sharpe`/`holdout_passed`/`stress_test_passed` fields,
  explicitly noting it can't include the correlation piece.

## Definition of done

- [x] `SKILL.md` and `rules.yaml` reference only real, confirmed field
      names — zero placeholders remain.
- [x] Every check's severity (hard/soft) has a written reason.
- [x] Overlap with `backtest-diagnose` explicitly reconciled — by reuse
      (citing it as `source`) for the four shared checks, and by explicit
      flagged disagreement for the one real inconsistency found
      (OOS Sharpe threshold: backtest-diagnose says hard, loop.py's actual
      behavior treats it as soft).
- [x] A tool call from Step 02 is named explicitly in `SKILL.md` —
      `get_backtest_validation` for the statistical verdict,
      `query_hypotheses` for evidence trail context.
