---
name: gatekeepers
description: How to read and combine the real statistical validation, PBO, correlation, and promotion checks that vinu-simulator/vinu-research already compute — this skill interprets existing outputs, it does not invent new thresholds.
category: tool
---

## Gatekeepers — Reading the Real Validation Outputs

This skill used to invent its own metric names and thresholds. It doesn't
anymore. Everything below maps to code that already runs automatically —
`vinu_simulator/engine/validation.py::compute_validation_verdict`,
`vinu_research/pbo.py::probability_of_backtest_overfitting`,
`vinu_research/gates/correlation_gate.py::CorrelationVerdict`, and
`vinu_research/promotion.py::PromotionVerdict`. This skill's job is
**interpretation**: what each output means, how to fetch it, and how to
combine them into one judgment — not inventing a fifth check that
duplicates what these already do.

### Two different moments, two different questions

Gatekeeping happens at two distinct points, and they answer different
questions. Don't conflate them.

**1. Judging one candidate result** (during a sweep, or one iteration of
research refinement) — "is this specific backtest result statistically
real, or noise?"
  - `compute_validation_verdict` — **hard**. Fetch via Step 02's
    `get_backtest_validation` tool, passing the backtest's `run_id` (a
    string — from a `simulate`/`research` response, not a research run's
    integer id). Returns `{"passed": bool, "reasons": [str, ...]}`,
    combining 7 sub-tests: Monte Carlo trade-permutation p-value < 0.05,
    block-bootstrap p-value < 0.05, price-path resample p-value < 0.10,
    walk-forward consistency ≥ 0.60, bootstrap Sharpe CI lower bound > 0,
    BCa-adjusted CI lower bound > 0, placebo (random-entry) p-value <
    0.05. Each sub-test is skipped (not failed) if its own data minimum
    wasn't met; **if none of the seven had enough data, the whole verdict
    fails closed** — "cannot confirm significance" is treated as failure,
    not as a pass by default. This is the strongest, most rigorous signal
    available and should gate hard: a result that fails this is
    statistically indistinguishable from noise, full stop.
  - Trade count ≥ 30, profit factor > 1.5, OOS MaxDD < 1.5× IS MaxDD, IS
    Sharpe > 1.0, OOS Sharpe > 0.7 — **hard**, but these come from
    `backtest-diagnose/SKILL.md`'s existing checklist, not from this
    skill. **Reuse that checklist, don't re-derive these thresholds
    here** — `compute_validation_verdict` doesn't check trade count or
    profit factor at all, so these two skills are complementary, not
    overlapping: `backtest-diagnose` covers sample-size/return-quality
    sanity checks, `compute_validation_verdict` covers statistical
    significance. Apply both.
  - **Known inconsistency, not resolved here:** `backtest-diagnose` calls
    "OOS Sharpe > 0.7" a hard gate, but `loop.py::_rule_based_check`
    (the risk critic that actually runs during refinement — see Step 01
    Findings §1) only treats "Sharpe < 0.5" as a soft *suggestion*, not a
    rejection. These two pieces of the existing codebase disagree with
    each other about how hard this particular line is. This skill does
    not silently pick a winner — when an agent hits this specific
    tension, it should surface it explicitly rather than assume one
    source is authoritative.

**2. Judging promotion to live capital** (BENCHING → ACTIVE) — "should
this artifact, already accepted as a research result, be trusted with
real money?" This is a stricter, separate question with its own gate:
  - `PromotionVerdict` (`vinu_research/promotion.py::meets_promotion_bar`)
    — **hard**, by definition (it's the live-capital gate). Combines:
    `deflated_sharpe` above a configured threshold (multiple-comparisons-
    corrected — read Step 01's finding for why this matters: it corrects
    for "best of many trials" luck), the true out-of-sample holdout check
    (data the refinement loop never tuned against), an optional stress-
    test pass, and — if supplied — the correlation gate below.
  - You can **approximate** promotion eligibility without triggering an
    actual promotion (which mutates state to ACTIVE on success) by
    reading `deflated_sharpe`, `holdout_passed`, `stress_test_passed`
    directly from the existing `GET /research/artifacts` route and
    comparing against the same three thresholds `meets_promotion_bar`
    uses. **Gap, not fixed by this step:** that route does not return
    correlation data, so a fully accurate local check can't include the
    correlation piece — only an actual `POST /research/artifacts/{id}/promote`
    call computes that. Treat a locally-approximated check as informative,
    not authoritative — verify before assuming an artifact would clear
    the real bar.
  - `CorrelationVerdict` (`vinu_research/gates/correlation_gate.py`) — is
    the candidate's return stream too correlated with already-ACTIVE
    strategies? **Hard at promotion time** (it's folded directly into
    `PromotionVerdict` when supplied). **Soft/informational when
    evaluating a sweep candidate mid-search** — a correlated candidate
    might still be individually valid; correlation only matters once
    you're deciding whether to add it *alongside* what's already running.
    Note the asymmetry vs. `compute_validation_verdict`: this gate
    **fails open** — no active strategies, or insufficient return data,
    both resolve to `eligible=True`. Don't read a `True` here as "checked
    and fine" without also checking `reasons` for why.

### PBO — cross-candidate, not a single-result verdict

`probability_of_backtest_overfitting` (PBO) answers a different kind of
question than the two moments above: "across *all* the candidates tried
in this research run, how much did picking the best one just capture
overfitting?" — Bailey/Borwein/López de Prado/Zhu (2017), via
Combinatorially Symmetric Cross-Validation. Returns `pbo` in [0, 1]:
< 0.30 low overfitting, ~0.50 uninformative selection, > 0.70 severe.
**Soft** — it's a warning about the *selection process*, not a defect in
one specific candidate; a high PBO means be more skeptical of "the best
one," not that the best one is definitely wrong.

**Known gap:** PBO is computed once per research `run()` call and
returned in that call's live response (`ResearchResult.pbo`), but it is
**not persisted** to the `research_runs` table — confirmed by reading
`ResearchStorage.insert_run`/`update_run`'s SQL, which has no `pbo`
column. It is only visible in the original response; a later
`GET /research/runs/{id}` call will not have it. If PBO needs to be
checked after the fact rather than only at the moment a run finishes,
that requires adding a `pbo` column and wiring it through
`insert_run`/`update_run` — genuinely new work, not covered by anything
built so far, and out of scope for this skill to silently work around.

### How to combine these into one judgment

1. Fetch `compute_validation_verdict` (via `get_backtest_validation`) and
   the `backtest-diagnose` checklist fields for the candidate. Both hard.
   Either failing → reject the candidate outright, do not continue
   refining it as if it were still in the running.
2. If multiple candidates were compared in the same run, note the PBO
   score. High PBO doesn't reject any single candidate, but it should
   lower confidence in "the best one" and is worth surfacing alongside
   whichever candidate is chosen.
3. Only when moving an artifact toward live capital: check
   `PromotionVerdict` (hard) including its folded-in correlation check.
   This is a separate, later decision from step 1 — don't conflate
   "passed candidate evaluation" with "cleared for live capital."
4. Always report *why*, not just pass/fail — every one of these
   structures already returns a `reasons`/`reasons` list. Surface it
   verbatim; don't collapse it into a bare boolean.

### Fetching this data

Use Step 02's tools:
- `get_backtest_validation(run_id)` — `compute_validation_verdict` +
  top-line metrics for one backtest.
- `query_hypotheses(symbol)` — evidence trail if you need to see whether
  this candidate's own past iterations already told a consistent story.
- Reading promotion/correlation state currently has no dedicated
  read-only tool beyond approximating from `GET /research/artifacts` (see
  above) — this is an acknowledged gap, not an oversight.
