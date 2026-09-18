# Reference/baseline distribution config — the missing inputs to PSI

## Context

`03-severity-and-trend.md` (same folder) defines `classify_severity()`
using PSI, but PSI is a formula with two undefined inputs until this
doc: what counts as "expected" (the reference/baseline distribution)
and how it gets binned. Grounded in external PSI/drift-detection
research (cited throughout), not invented here.

This config is **data, not code** — a separate table, editable without
touching an analyst's code, the same "ships inert, dynamic config over
baked-in" pattern already used elsewhere in this system (e.g.
vinu-screener's external universe-override file).

---

## The table: `reflection_reference_config`

| Column | Meaning |
|---|---|
| `analyst_name` (PK part) | which analyst this rule belongs to |
| `scope_type` (PK part) | same scope as the finding it governs |
| `metric_name` (PK part) | which field in `signal_json` / which `primary_metric` this rule governs |
| `reference_window_definition` | e.g. `"rolling_30d"`, `"trailing_90_entries"` — see "Window length" below |
| `bin_count` | nullable — `NULL` means auto-derive from `evidence_count` (see "Bin count" below); an explicit value overrides |
| `min_samples_per_bin` | default 20 (see "Bin count" below) |
| `epsilon` | default 0.01 (see "Zero-bin stability" below) |
| `metric_polarity` | `higher_is_worse` \| `lower_is_worse` — see "Polarity" below. Required for every PSI-based metric; without it `trend` cannot be computed at all. |
| `updated_at`, `updated_by`, `reason` | so a rule change (e.g. "added intraday-specific window for metric X") is itself auditable, same discipline `symbol_limit_history` already applies to limit changes |

New rules (like an intraday-specific reference window) are added as new
rows here — an insert, not a code change or a redeploy.

---

## Window length — rolling, scaled to how often the source data updates

Two things confirmed by research, not assumed:

- **Rolling, not fixed.** A fixed reference window (e.g. always Q1)
  lets natural seasonal drift masquerade as real drift by the time
  you're comparing against a distant quarter. Rolling windows avoid
  this.
- **Length must match update cadence** — "7-day comparisons work only
  for high-frequency models; monthly-retrain models need 30-day windows
  or PSI becomes noise." This is exactly the same instinct
  `03-severity-and-trend.md` already applies to evidence-count minimums
  (D's LLM calls arrive constantly, V's promoted artifacts arrive
  rarely) — now extended to the reference window itself. Concretely:
  D's `llm_role` metric can use a short rolling window (data arrives
  continuously); V's `paper_live_correlation` needs a much longer one
  (promotions are rare).

**Source**: [Drifting Through Time — Sequence & Destroy](https://sequenceanddestroy.substack.com/p/drifting-through-time) — rolling-window rationale, retrain-cadence-matched window length, seasonal-masking risk of fixed baselines.

---

## Bin count — scales with `evidence_count`, both a floor and a ceiling

Not a fixed 10 bins everywhere. The real constraint is samples-per-bin,
not bin count directly:

```
bin_count ≈ min(20, evidence_count / min_samples_per_bin)
```

- **Floor**: below `min_samples_per_bin` (default 20) per bin, PSI gets
  statistically unstable — "a sample size of 100 is not enough for 20
  bins." Several analyses are low-volume by design (M's
  investment-committee debate, N's kill-switch retrospective, U's
  critical-bypass — all explicitly "rare events" in their own
  Manageability sections in `25-A-Y-details/`). Those need 2-4 bins, or
  should skip PSI's binned form and use a plain two-sample comparison
  until real history accumulates.
- **Ceiling**: capped around 20 bins (demi-deciles) — finer binning
  doesn't add real signal even for a high-volume analysis like D
  (constant `llm_calls` traffic).

**Source**: [mwburke — Population Stability Index](https://mwburke.github.io/data%20science/2018/04/29/population-stability-index.html), [A Practical Introduction to PSI — Coralogix](https://coralogix.com/ai-blog/a-practical-introduction-to-population-stability-index-psi/) — decile/demi-decile convention, small-sample instability.

---

## Bins are fixed from the baseline, not recomputed every cycle

The bin **edges** are computed once, from the reference window, using
equi-quantile (equi-depth) binning — then held fixed across every
subsequent cycle's comparison. Only the *distribution being compared*
(this cycle's actual values) refreshes each time; the bin boundaries
themselves don't move. Recomputing bin edges every cycle would make PSI
readings incomparable cycle to cycle — the opposite of what a trend
needs.

This is a correction to how `03-severity-and-trend.md` currently reads —
it says the Condition is "computed fresh... every cycle," which is
correct for the compared distribution, but doesn't distinguish that
from the bin edges, which must stay fixed.

**Source**: [A Practical Introduction to PSI — Coralogix](https://coralogix.com/ai-blog/a-practical-introduction-to-population-stability-index-psi/) — bins defined from baseline, kept fixed for comparisons across time windows.

---

## Polarity — PSI is magnitude-only, direction is a separate judgment

PSI is non-negative by construction (`(actual% - expected%)` and
`ln(actual%/expected%)` always share the same sign, so every term in
the sum is ≥0) — it measures *how much* a distribution moved, never
*which way*. A PSI of 0.35 says "significant shift," nothing about
whether that shift is good or bad for trading. That judgment is
`trend`'s job (`03-severity-and-trend.md`), and `trend` cannot be computed
without knowing, per metric, whether an increase or a decrease counts
as `degrading`.

Every analysis's Condition prose already implies this polarity in
English (e.g. A's Condition talks about Brier score "moving outside its
band," and elsewhere the doc calls a higher Brier "worse than random")
— but prose isn't something `write_findings()` can read. `metric_polarity`
makes it an explicit, machine-usable value instead. Provisional —
reasoned from each analysis's own Condition/Fetch text, not empirically
validated, same caveat as every other number in this doc:

| Analysis | `primary_metric` | `metric_polarity` |
|---|---|---|
| A | `brier_trend` | `higher_is_worse` (Brier score: 0 = perfect) |
| Q | `accuracy_trend` | `lower_is_worse` (directional accuracy) |
| P | `brier_delta_vs_clean_periods` | `higher_is_worse` |
| G | `fallback_brier_delta` | `higher_is_worse` |
| B | `sharpe`/`ic` for the cell | `lower_is_worse` |
| E (pair) | `correlation_trend` | `higher_is_worse` (rising correlation = concentration risk) |
| E (concentration) | `vol_annualized_trend` / `weight_trend` | `higher_is_worse` |
| N | `shock_reading_at_lead` | **n/a** — event-triggered lead-time detection, not a recurring belief; no `trend` to compute |
| V | `paper_live_correlation` | `lower_is_worse` (low/negative = paper predicts nothing) |
| C | `loss_rate` / `mean_slippage_bps` | `higher_is_worse` |
| U | `critical_outcome_rate` | `lower_is_worse` |
| Y | `mean_pnl_delta` | `lower_is_worse` (already a signed delta; more negative = event overlap hurts more) |
| D | `retry_rejection_delta` | `higher_is_worse` (retries more strongly coupled to bad outcomes) |
| L | `trace_length_outcome_correlation` | `lower_is_worse` (signed delta; long-trace attempts underperforming short) |
| K | `verdict_quality_delta` (with memory vs. without) | `lower_is_worse` |
| M | `with_debate_outcome` delta | `lower_is_worse` |
| O | `projected_performance_of_blocked` | `higher_is_worse` (evidence the limit is blocking good trades) |
| R | `stale_fraction` | `higher_is_worse` |
| F | `outcome_delta` (responded vs. unresponded) | `lower_is_worse` |
| W | `outcome_under_current` vs. `outcome_under_alt_range` | `lower_is_worse` (signed delta; current threshold underperforming swept alternatives) |
| H (consistency piece) | `live_backtest_divergence` | `higher_is_worse` |
| H (governance piece) | `outcome_delta_before_after` | **n/a** — same reason as N: event-triggered per skill-edit, not a recurring belief; no `trend` to compute |
| I | `agreement_rate` | `lower_is_worse` |
| J | `churn_spike_lead_time` | `lower_is_worse` (shrinking lead time = less useful early warning) |
| X | `agreement_rate` | `lower_is_worse` |

**S and T are absent from this table on purpose** — neither uses PSI
(see the count in conversation: S is a fixed-tolerance diff, T is a
direct agreement/disagreement check), so neither needs a polarity
entry; their own Condition text already states pass/fail directly.

---

## Zero-bin stability

If any bin has zero samples in either the reference or current
distribution, PSI's `ln(actual/expected)` term goes to infinity — a
real failure mode for the sparse analyses (M, N, U, T), not a
theoretical one. Fix: add a small epsilon (default `0.01`, the
`epsilon` column above) to every bin proportion before the log term, or
merge sparse bins.

**Source**: [Statistical Properties of Population Stability Index — Yurdakul & Naranjo](https://scholarworks.wmich.edu/cgi/viewcontent.cgi?article=4249&context=dissertations) — PSI becomes infinite on zero-count bins; epsilon smoothing as the standard fix.

---

## Scope note

Design only — nothing here has been implemented. Closes the "what is
'expected'" gap left open when `03-severity-and-trend.md` was written.
