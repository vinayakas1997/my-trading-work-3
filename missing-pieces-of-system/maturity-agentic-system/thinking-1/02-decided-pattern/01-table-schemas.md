# The 3 tables, fully explained — single reference

All three tables the whole reflection layer writes to. Nothing else.
25 analyses, 6 analysts, and the brain all share these.

---

## 1. `reflection_findings_history` — 10 columns

Raw, append-only. Every analyst writes here. Pruned over time (same way
`vinu-initial-analysis`'s `tier3` angle results already are).

| Column | Meaning |
|---|---|
| `finding_id` (PK) | unique row id |
| `analyst_name` | which of the 6 analysts wrote this |
| `cluster` | which analyst cluster (Forecast Intelligence, etc.) |
| `scope_type` | `system` \| `ticker` \| `ticker_pair` \| `strategy_family` \| `angle` (no `regime` value — none of the 25 scoped analyses use it as a top-level scope; regime always lives nested inside `signal_json` instead, see `02-analyst-interface.md`) |
| `scope_key` | what this row is about (a symbol, a pair, a checkpoint name...) |
| `computed_at` | when this finding was computed |
| `signal_json` | the real numbers — different shape per analysis, e.g. `{"brier_trend": ...}` for A, `{"correlation_trend": ...}` for E |
| `evidence_count` | how many real rows backed this finding |
| `severity` | `routine` \| `notable` \| `significant` |
| `narrative` | optional one-line human-readable gloss |

Only gets a row when an analyst's significance gate actually fires —
most cycles, most scopes, write nothing.

## 2. `reflection_beliefs` — 9 columns

Current state only. **Overwritten**, not appended, per
`(analyst_name, scope_type, scope_key)`. Same relationship
`ticker_summaries` has to `ticker_daily_snapshots`.

| Column | Meaning |
|---|---|
| `analyst_name` (PK part) | which analyst |
| `scope_type` (PK part) | same as above |
| `scope_key` (PK part) | same as above |
| `computed_at` | when this belief was last updated |
| `signal_json` | same shape as the history table's |
| `evidence_count` | how much evidence backs the *current* belief |
| `severity` | current severity |
| `narrative` | current one-liner |
| `trend` | `improving` \| `stable` \| `degrading` |

This is the table the brain actually reads from — small, bounded,
always current.

## 3. `reflection_synthesis_outcomes` — 12 columns

The brain's own self-trust log. Written only by the brain, not by the
6 analysts. Tracks what the brain predicted vs. what actually happened,
so the brain has to earn trust in its own synthesis the same way every
other mechanism in this codebase earns trust in a number.

| Column | Meaning |
|---|---|
| `synthesis_id` (PK) | unique row id |
| `computed_at` | when the brain ran this synthesis |
| `trigger_reason` | `scheduled` \| `new_significant_finding` \| `consumer_requested` |
| `inputs_snapshot` | which `reflection_beliefs` rows fed this synthesis — so reasoning quality is checkable separately from outcome luck |
| `prediction_json` | the synthesized judgment: maturity profile, narrative, any proposed action |
| `proposed_action_type` | `threshold_nudge` \| `significance_flag` \| `narrative_only` (nullable) |
| `resolution_criteria` | what counts as "right" — fixed at prediction time, never decided after the fact |
| `resolve_by` | when to check back |
| `observed_outcome_json` | what actually happened (nullable until resolved) |
| `outcome_match` | `correct` \| `partially_correct` \| `incorrect` \| `inconclusive` (nullable) |
| `resolved_at` | when it was checked (nullable) |
| `evidence_count_at_synthesis` | evidence behind the analysts this synthesis drew on — thin evidence moves the track record less than deep evidence |

Resolved by a periodic worker (same shape as `significance-worker`)
scanning rows past `resolve_by` with `resolved_at` still null.

---

**Total: 3 tables, 24 columns, all 25 analyses + 6 analysts + the brain
share them.** No other tables in this design.
