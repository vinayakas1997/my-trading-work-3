---
name: phase-6-guard-rail
status: proposed-not-built
purpose: what keeps THGATE's dedup/cap check actually correct across both entry points, keeps Thesis Intake structurally incapable of writing code, and keeps the skill-edit audit log honest about what it does and doesn't guarantee.
---

# Phase 6 -- Guard rails

**"Near-duplicate" needs a stated, testable definition -- not a vague
LLM judgment call.** Too loose and legitimate, genuinely distinct
theories get silently blocked (a human submits something real and never
finds out why it went nowhere); too strict and the gate saves nothing. A
human whose submission is blocked as a near-duplicate must be able to see
*why* -- which prior theory it matched against -- not receive silent
rejection. Visibility here matters as much as the threshold itself.

**The shared K-cap query must be tested against both sources, explicitly,
not just one.** The whole point of the shared counter (`01-plan.md`) is
that a `TickerLedger` query counts distinct-candidate events regardless
of `source` (`"watchlist"` or `"human"`). A query that only filters one
source by mistake would silently let the cap be bypassed through the
other entry point -- exactly the boundary gap this mechanism exists to
close. This needs its own explicit test, not an assumption that "it
queries the table" is sufficient.

**"Writes no code, ever" must be a structural restriction, not a prompt
instruction.** Thesis Intake's tool list should not include
`run_backtest`, `run_parameter_sweep`, or any code-execution tool at all
-- the same discipline `risk_gatekeeper` already follows by design
(answers one question, never re-litigates a different one), applied here
by omission from the tool list rather than relying on the prompt saying
"don't write code." A capability that isn't available can't be misused
by an unlucky prompt interpretation.

**The `source="human"` tag on `HypothesisRegistry` writes must be
enforced at the call site, not a convention that can be silently
omitted.** If Thesis Intake's write path ever forgot the tag, a
human-submitted theory becomes indistinguishable from a system-generated
one downstream -- the Planner's pre-proposal consult couldn't tell them
apart, and the provenance this whole design leans on for traceability
quietly breaks. Make `source` a required parameter with no default on
whatever write method Thesis Intake calls, not an optional kwarg.

**The skill-edit audit log records visibility, not access control.** It
answers "did `risk-rules.md` change, and when" -- it does not answer or
enforce "who is allowed to change it." If genuine access control (gating
*who* can edit that file) turns out to matter, that's a separate,
not-yet-decided mechanism (file permissions, required review) and out of
this phase's scope. Don't let the audit log's existence create a false
sense that edits are also being gated, not just observed.
