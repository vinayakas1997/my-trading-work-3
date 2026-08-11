---
name: phase-6-test
status: proposed-not-built
purpose: concrete input/expected-output cases proving THGATE's dedup and shared-cap checks are correct across both entry points, and Thesis Intake stays structurally incapable of writing code.
---

# Phase 6 -- Test plan

**`test_thgate_blocks_near_duplicate_theory`**
Input: a theory highly similar to one already evaluated for the same
ticker recently (present in `HypothesisRegistry`).
Expected: `THGATE` blocks it before any LLM call; the block reason
identifies the specific prior theory it matched -- not a bare rejection.

**`test_thgate_allows_genuinely_distinct_theory`**
Input: a theory with no meaningful similarity to prior entries for this
ticker.
Expected: passes through to Thesis Intake.

**`test_shared_kcap_counts_across_both_sources`**
Input: `TickerLedger` already has `K-1` distinct-candidate events this
cycle for a ticker, a mix of `source="watchlist"` and `source="human"`.
Expected: one more submission from *either* source is allowed (still
under cap); a submission after that (from either source) is blocked.

**`test_kcap_blocks_correctly_even_when_all_prior_events_from_one_source`**
Input: all `K` prior events this cycle came from `source="watchlist"`
alone; a new theory arrives via Thesis Intake.
Expected: blocked at cap -- proves the count query isn't accidentally
scoped to only one `source` value, which would let the other entry point
silently bypass the shared limit.

**`test_thesis_intake_tool_list_excludes_code_execution`**
Input: Thesis Intake's resolved tool list from its team config.
Expected: `run_backtest`, `run_parameter_sweep`, and any code-execution
tool are absent -- the restriction is structural (not present in the
list), not just a prompt instruction.

**`test_hypothesis_registry_write_requires_source_human`**
Input: Thesis Intake's write call to `HypothesisRegistry.add_evidence(...)`
with `source` omitted.
Expected: raises (no default value exists for `source` on this call
path) -- proves the tag can't be silently dropped.

**`test_worth_checking_verdict_hands_off_to_downstream_loop`**
Input: Thesis Intake produces a "worth checking" verdict.
Expected: the same downstream target real system-generated ideas use
(the `research` team's manager loop, per Phase 1) receives it -- same
loop, confirmed by call target, not just described in prose.

**`test_skill_edit_audit_log_records_risk_rules_changes_only`**
Input: one edit to `skills/thesis-intake/risk-rules.md`, one separate
edit to `skills/thesis-intake/strategy-definitions.md`.
Expected: the risk-rules edit produces a logged entry (who/when/diff
summary); the strategy-definitions edit does **not** appear in this same
log -- proves the audit log is scoped specifically to risk-relevant
content, not every file in the skill.

## End-to-end

**`test_phase6_full_theory_walkthrough`**
Input: a human submits a genuinely new, non-duplicate theory for a
ticker with real `TickerLedger`/`HypothesisRegistry`/`TickerSummaryStore`
history and both skill files present.
Expected, in order: `THGATE` passes it through -> Thesis Intake reads all
three real evidence sources plus both skill files -> produces a verdict
grounded in cited real evidence (not fabricated) -> on "worth checking,"
writes to `HypothesisRegistry` tagged `source="human"` and a
`TickerLedger` row -> hands off to the downstream loop. This is the case
that proves the whole entry point works end to end, not just its gate.
