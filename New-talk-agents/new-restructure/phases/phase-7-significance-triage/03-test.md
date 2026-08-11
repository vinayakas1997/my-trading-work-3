---
name: phase-7-test
status: proposed-not-built
purpose: concrete input/expected-output cases proving Significance Triage flags the right things, never blocks, delivers through existing channels, and closes the loop back correctly.
---

# Phase 7 -- Test plan

**`test_routine_decision_not_flagged`**
Input: an ordinary `capital_allocator` funding decision within normal
size/exposure parameters.
Expected: no flag raised.

**`test_repeated_rejection_pattern_flagged`**
Input: `TickerLedger` shows 3+ `risk_gatekeeper` `REJECTED` events for the
same ticker within a defined recent window.
Expected: a flag is raised, citing the pattern (ticker, count, window)
explicitly -- not a generic "something happened" message.

**`test_pattern_detection_reads_ticker_ledger_directly`**
Input: rejection events written to `TickerLedger` through a path that
does not call any Significance-Triage-owned counter update.
Expected: the pattern is still correctly detected on the next triage
pass -- proves detection queries the Ledger itself, not a separately
maintained, driftable counter.

**`test_flag_never_blocks_the_underlying_action`**
Input: a funding decision that triggers a flag.
Expected: the funding action completed and is already reflected in
storage (artifact `ACTIVE`, etc.) *before* the flag's human response, if
any, ever arrives -- the flag is asserted to be informational, not a
precondition of the action having happened.

**`test_flag_gets_unique_id_in_standard_format`**
Input: any raised flag.
Expected: `flag_id` is a 12-character lowercase hex string
(`uuid.uuid4().hex[:12]`, the project-wide convention).

**`test_flag_delivered_via_existing_channel_wiring`**
Input: a flag is raised with Discord configured.
Expected: the delivery call targets the existing
`vinu_agent/channels/discord.py` channel object -- no new HTTP polling
route is created or called for delivery.

**`test_multi_channel_delivery_shares_one_flag_id`**
Input: both Discord and Telegram configured; one flag raised.
Expected: both channel messages reference the same `flag_id`; a
simulated human response via either channel resolves the same flag
record, not two independent ones.

**`test_human_response_writes_override_with_correct_tag_and_ref_id`**
Input: a human responds to a flag with a decision/comment.
Expected: `HypothesisRegistry.add_evidence(...)` is called with
`source="human_override"` and `ref_id` equal to the original `flag_id`.

**`test_override_write_requires_source_tag`**
Input: the override write call with `source` omitted.
Expected: raises -- no silent default.

**`test_unanswered_flag_does_not_error_or_retry_indefinitely`**
Input: a flag with no human response after an extended period.
Expected: no error state is raised, no retry loop attempts redelivery
indefinitely -- it remains a normal, unanswered record; the underlying
system continues operating unaffected.

## End-to-end

**`test_phase7_full_flag_to_override_walkthrough`**
Input: a real pattern of repeated `REJECTED` verdicts accumulates in
`TickerLedger` for a ticker; a triage pass runs.
Expected, in order: pattern detected -> flag raised with a real
`flag_id`, citing the specific ticker/reason -> delivered through the
existing channel wiring -> a simulated human response arrives ->
`HypothesisRegistry` receives the tagged, `ref_id`-linked override write
-> a simulated next Planner pre-proposal consult on that ticker sees the
override alongside the original rejection pattern. Proves the full
detect-flag-respond-remember cycle, not just each piece alone.
