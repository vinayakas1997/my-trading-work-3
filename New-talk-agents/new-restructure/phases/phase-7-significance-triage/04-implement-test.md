---
name: phase-7-implement-test
status: built -- Phase 7 is implemented, tested, and wired
purpose: record of what was actually touched, what was tested, and the real result -- not a plan anymore, a report.
---

# Phase 7 -- Implementation record

Built 2026-08-11, directly following Phase 6 in the same session.

## Real gap found beyond the original plan

**`risk_gatekeeper_hook.py`'s REJECTED path wrote nothing to
`TickerLedger` at all** (confirmed by reading Phase 2's own code, written
earlier this session: "REJECTED writes nothing -- the artifact stays
exactly where it was" -- true for the status transition, but that same
"nothing" extended to the audit trail too). Phase 7's whole pattern
detector depends on real `REJECTED` history existing in `TickerLedger` to
query. Fixed by extending the hook: REJECTED now re-fetches the artifact
(read-only, to resolve its ticker) and writes a `TickerLedger` row
(`event_type="REJECTED"`), still with no status mutation -- the artifact
genuinely stays exactly where it was, only the audit trail changed.

**`Evidence` had no `ref_id` field**, needed for "the flag's `flag_id` as
`ref_id` linking back to what prompted it" (01-plan.md item 4). Added
`Evidence.ref_id: str = ""` (additive, alongside `source` from the same
change) rather than overloading an existing field (`report_path` was
close but semantically wrong) or encoding it indirectly.

## Files touched

| File | Status | What changed |
|---|---|---|
| `vinu-components/vinu-research/vinu_research/models.py` | modified | `Evidence.source: str = "system"`, `Evidence.ref_id: str = ""` (both additive). |
| `vinu-components/vinu-research/vinu_research/hypothesis_registry.py` | modified | `_to_dict`/`_from_dict` persist both new fields. |
| `vinu-components/vinu-research/vinu_research/server/routes_hypothesis.py` | modified | `AddEvidenceRequest` gains `source`/`ref_id` (both defaulted, for backward compatibility -- the real no-default enforcement lives in `significance_triage.py`'s own function signature, not the HTTP layer). |
| `vinu-components/vinu-research/vinu_research/server/routes_introspect.py` | modified | Evidence serialization includes `source`/`ref_id`. |
| `vinu-components/vinu-research/tests/test_hypothesis_registry.py`, `test_routes_hypothesis.py` | -- | No new tests added here (Phase 6 already established the `source` test pattern; `ref_id` is exercised end-to-end via Phase 7's own `record_human_override` tests instead of duplicating coverage). |
| `vinu-components/vinu-agent/vinu_agent/agent/risk_gatekeeper_hook.py` | modified | REJECTED path now writes a `TickerLedger` row (`event_type="REJECTED"`, no status change) -- the real gap above. |
| `vinu-components/vinu-agent/tests/test_team.py` | modified | New `test_rejected_writes_ticker_ledger_row_for_real_artifact`. |
| `vinu-components/vinu-agent/vinu_agent/agent/significance_triage.py` | new | `SignificanceFlagStore` (flags + response-rate tracking, from day one per the guard rail). `detect_repeated_rejection_pattern()` -- the one concrete, shipped pattern detector, querying `TickerLedger` directly. `format_flag_message()`/`deliver_flag()` -- reuses the existing channel `send_message(chat_id, text)` interface, one flag_id shared across every configured channel. `record_human_override()` -- `source` is a required keyword-only parameter with no default (omitting it raises `TypeError` at the call site itself, the strongest form of "enforced, not a convention"), plus a redundant `ValueError` guard against a wrong value being passed. |
| `vinu-components/vinu-agent/tests/test_significance_triage.py` | new | 21 tests covering every `03-test.md` case directly. |

## Design deviations from `01-plan.md`/`02-guard-rail.md`, and why

- **Only ONE concrete pattern detector shipped: repeated `risk_gatekeeper`
  `REJECTED` verdicts.** The plan also names "an unusually large single
  funding decision" and "a close that contradicts the original thesis
  strongly enough to be surprising" as real candidates -- neither has a
  concrete, stated threshold anywhere in this project (unlike the
  repeated-rejection case, which `03-test.md` specifies exactly: "3+
  events... within a defined recent window"). Inventing thresholds for
  the other two without real data to ground them would be exactly the
  kind of ungrounded number this project's whole discipline warns
  against. `detect_repeated_rejection_pattern`'s shape (a plain function
  taking a `TickerLedgerCounter`) is the extension point for adding them
  once real thresholds get decided -- not built speculatively now.
- **`source` on `HypothesisRegistry` writes is enforced by Python's own
  required-keyword-argument mechanism, not a runtime check inside a
  shared method.** `record_human_override(..., *, source: str, ...)` has
  no default -- calling it without `source` is a `TypeError` before the
  function body even runs, mirroring (and arguably strengthening) Phase
  6's "no parameter to override" pattern for `Hypothesis.create_from_
  human()`. A redundant `if source != "human_override": raise ValueError`
  guards against the (currently only theoretical, since nothing else
  calls this function) case of a caller passing the wrong string.
- **No live trigger wires `detect_repeated_rejection_pattern`/`deliver_
  flag` into an actual running loop yet.** Same "not wired to a live
  scheduler" shape as Phase 0's `RunLogTrigger`/`ChangeGate`, Phase 4's
  `ShadowEvaluator`, and Phase 6's `check_skill_edits()` -- correct,
  tested, standalone functions ready for whatever eventually calls them
  on a cadence (most naturally alongside `capital_allocator`'s own
  batched cadence from Phase 2, since that's one of the three real
  sources this phase's flags are meant to come from).
- **The response-rate/alert-fatigue measurement (`SignificanceFlagStore.
  response_rate()`) has no consumer yet either.** Built because the guard
  rail is explicit that "the measurement needs to exist from the start,"
  not because anything currently reads it -- same category as the
  metric existing before the loop that would act on it.

## Test results

```
vinu-agent:    545 -> 567 passed (full suite; 1 + 21 = 22 new tests)
vinu-research: 591 -> 592 passed, 1 skipped (full suite; Evidence.source/
                ref_id additions covered indirectly via vinu-agent's own
                record_human_override tests + existing hypothesis tests
                staying green)
```

No regressions in either package's full suite.

## Known follow-ups (not blocking, not silently dropped)

- **No scheduler calls the triage pass, delivers flags, or checks skill
  edits automatically yet** -- see design deviation above. This is now
  the fourth "correct, tested, not-yet-scheduled" mechanism this build
  has produced (`RunLogTrigger`/`ChangeGate`, `ShadowEvaluator`,
  `check_skill_edits`, and now Significance Triage) -- a real scheduler
  covering all of them is the single highest-leverage piece of
  infrastructure any future phase could add.
- **The other two named significance patterns** (large single funding
  decision, thesis-contradicting close) need real thresholds decided
  before they can be built the same way the rejection pattern was.
- **`ChannelTarget` resolution (which chat_id to actually deliver to) has
  no real config source wired in** -- same category of gap as Phase 5's
  rebalance-request cross-process wiring: the mechanism is correct and
  tested, but something still needs to resolve a real, configured
  chat_id from `AgentConfig`'s loosely-typed `channels` dict (confirmed
  via direct reading: `channels` isn't even a declared dataclass field,
  just accessed via `getattr(config, "channels", {})`) before this can
  deliver a real message in production.
