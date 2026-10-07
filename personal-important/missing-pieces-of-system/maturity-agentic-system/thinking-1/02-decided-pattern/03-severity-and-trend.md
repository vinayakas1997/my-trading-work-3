# Severity and trend — how the two ungoverned fields actually get computed

## Context

Found while auditing `25-A-Y-details/` against `01-table-schemas.md` and
`02-analyst-interface.md`: `severity` is a required field on every
`Finding` and every schema row, but none of the 25 scoped analyses ever
said how their `routine`/`notable`/`significant` tier gets decided —
only whether the row gets written at all. `reflection_beliefs`' `trend`
column had no producer anywhere — the `Finding` dataclass doesn't carry
one, and the worker-loop's `write_findings()` never computed one.

Both get closed here as **shared Layer 1 functions**, not as 25 bespoke
per-analysis judgment calls — the same reasoning `00-index.md` already
gives for banning hand-picked Condition thresholds applies identically
one layer over: a severity rule invented separately per analysis is
exactly the kind of "reasoning-picked, never-measured number" this
whole design otherwise refuses to allow.

---

## `classify_severity()` — reuses PSI, not a new invented scale

Every Condition in `25-A-Y-details/` already computes "how far this
cycle's value sits from its own trailing distribution" to decide
pass/fail (the P10/P90 band check). Reuse that same distance as the
severity score, via the **Population Stability Index (PSI)** — a
long-established convention (originated in credit-risk scorecards, now
widely used across ML monitoring generally) for exactly this question:
how much has a distribution shifted, bucketed into the same three-way
split `severity` already needs.

```
PSI = Σ (actual_% - expected_%) × ln(actual_% / expected_%)
```
computed between this cycle's value and the trailing-window
distribution the Condition is already reading. The bin edges used here
come from the reference window and stay fixed across cycles — see
`04-reference-baseline-config.md` for the window length, bin-count, and
zero-bin-stability rules; this section only covers the bucket shape.

**Standard buckets, but sample-size-dependent — not one flat cutoff for
all 25 analyses**:
- PSI < 0.1 → stable, no shift → gate does not fire, nothing written
  (matches the design's own "most cycles produce nothing" framing —
  `routine` is a state, not something ever persisted to
  `reflection_findings_history`)
- PSI 0.1–0.25 → `notable`
- PSI > 0.25 → `significant`

**Correction**: these exact numbers (0.1 / 0.25) are only reasonable
for reference/current sample sizes in the 100–200 range — research on
PSI's statistical properties found them "too conservative for larger
sample sizes." Since `evidence_count` varies enormously across the 25
analyses (D's `llm_calls` arrive by the hundreds per window; M's
investment-committee debates accumulate in the low tens), using 0.1/0.25
flat everywhere would over-flag high-volume analyses and under-flag
low-volume ones. The actual reference window, bin count, and (where
warranted) a sample-size-adjusted threshold pair are defined per
`(analyst_name, scope_type, metric_name)` in the new
`04-reference-baseline-config.md` (same folder) — this file only fixes the
*shape* of the rule (PSI, three buckets); that companion file fixes the
*inputs* (what's "expected," how many bins, and the sample-scaled
thresholds).

**Source**: [Statistical Properties of Population Stability Index — Yurdakul & Naranjo](https://scholarworks.wmich.edu/cgi/viewcontent.cgi?article=4249&context=dissertations) — flat 0.1/0.25 reasonable for n,m ≈ 100–200, too conservative above that; sample-size-dependent thresholds recommended instead.

**Exception** — the same one `00-index.md` already allows for absolute
domain floors (Brier ∈ [0,1], correlation ∈ [-1,1]): if an analysis
defines a hard domain boundary (e.g. A's `brier_score ≥ 0.5`, "worse
than random"), crossing that boundary alone is sufficient for
`significant` regardless of PSI. This matters because a Brier number
read in isolation is misleading — it has to be benchmarked against a
reference/uninformative baseline, not judged on its own, which is
exactly what the domain-floor exception already does for analysis A.

**Sources**:
- [What Is Population Stability Index (PSI)?](https://futureagi.com/glossary/population-stability-index-psi/) — PSI < 0.1 stable, 0.1–0.25 moderate/investigate, > 0.25 significant drift, credit-risk origin now applied broadly across ML monitoring.
- [Population Stability Index (PSI) — GeeksforGeeks](https://www.geeksforgeeks.org/data-science/population-stability-index-psi/) — same threshold convention, independent confirmation.
- [Brier Score in Probabilistic Forecasting](https://www.emergentmind.com/topics/brier-score) — a Brier score "must be benchmarked against the score for an uninformative model, rather than interpreted in isolation," the basis for keeping A's domain-floor exception rather than trusting PSI alone for that analysis.

---

## `trend` — computed generically at write time, not per-analyst

One new field on `Finding` (see `02-analyst-interface.md`):
`primary_metric: float` — the single number each analysis already
treats as "the" number (Brier trend for A, correlation for E,
retry-rejection delta for D — already named in each analysis's
`signal_json`, just not previously surfaced as its own field).

At `write_findings()`, before overwriting `reflection_beliefs`, read
the prior row for `(analyst_name, scope_type, scope_key)` and diff
`primary_metric` against the prior value, using the **same PSI-derived
dead-band** as `classify_severity()` (PSI < 0.1 between old and new
`primary_metric` → `stable`; otherwise `improving`/`degrading` depending
on the metric's own polarity — **not read from prose**, but from the
explicit `metric_polarity` column (`higher_is_worse` /
`lower_is_worse`) in `04-reference-baseline-config.md`'s per-metric table,
e.g. Brier score decreasing = improving, correlation climbing toward a
concentration risk = degrading).

This keeps trend entirely out of the 25 analysis specs and the analyst
functions themselves — it falls out of the shared write step for free,
computed once, the same way for all 25.

---

## On evidence-count / sample-size minimums — validated, not replaced

The literature doesn't hand over one universal minimum-sample number
either — financial drift-detection research commonly uses window sizes
around 100–180 observations
([Domain Specific Concept Drift Detectors for Predicting Financial Time Series](https://ar5iv.labs.arxiv.org/html/2103.14079)).
That's a *validation* of the placeholder minimums already scattered
through `25-A-Y-details/` (D's "e.g. 30 calls," V's "e.g. 5 promoted
artifacts") being the right order of magnitude, not a replacement for
them — those stay analysis-specific, not folded into the two shared
functions above, since the right minimum genuinely depends on how often
that analysis's own source data updates (D's LLM calls arrive
constantly; V's promoted artifacts arrive rarely).

---

## Scope note

Design only — nothing here has been implemented. Closes the `severity`
and `trend` gaps found auditing `01-table-schemas.md`/`02-analyst-interface.md`
against `25-A-Y-details/`.
