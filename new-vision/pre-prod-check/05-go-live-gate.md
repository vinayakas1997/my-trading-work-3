---
name: go-live-gate
status: planning only — not yet implemented, not yet evaluated
---

# Task: the bar that decides "ready for real capital" vs. "not yet"

## Goal

A single, explicit checklist that must be entirely green before this
system is allowed to place a real (non-paper) order — pulling together
task 04's scenario results plus the outstanding gaps already known from
`../04-new-full-explanation.md`'s "What's still not built" section.

## Why

Without one explicit gate, "are we ready" becomes a judgment call made in
the moment, which is exactly the kind of ungrounded decision this whole
project's design otherwise refuses to make anywhere else (every stage
above reports a specific, stored reason for its verdict — this gate
should too).

## The gate

Real capital should not flow until **all** of the following are true —
not "mostly true," since a partial pass on a financial system is a fail:

1. **All 9 scenarios in task 04 are `pass`** in the manifest, for at
   least 2 independent tickers each (one ticker passing isn't enough
   evidence the handoff logic is general, not ticker-specific).
2. **Alpaca key rotation is confirmed complete** — the leaked pair from
   `alpaca-details/details.md` (still recoverable from git history) must
   be rotated at the provider, not just removed from tracking. This is a
   security precondition independent of the pipeline's own correctness.
3. **`scripts/setup-secrets.sh --check` passes** with zero missing
   required secrets on the actual deployment target, not just a dev
   machine.
4. **Significance Triage delivery is confirmed live** — a real message
   observed arriving in the configured Telegram/Discord channel, not just
   the code path executing without error (this was explicitly still open
   per `../03-how-to-start.md`).
5. **Kill Switch manual engage/disengage has been exercised at least
   once against this deployment** (scenario 4 in task 04 covers the
   pipeline-level check; this is the operator confirming they know how to
   pull it in practice, under real deployment conditions, not just in a
   test).
6. **Every item in `../04-new-full-explanation.md`'s "What's still not
   built" section is either resolved or explicitly accepted as an open
   risk in writing** — paper-trade rehearsal (role d), the
   replace-decision in `capital_allocator`, Monitor's shock trigger and
   batching, and the cross-ticker portfolio view. None of these block
   go-live by default, but silence on them isn't the same as a decision
   to accept the risk — someone has to actually say so.
7. **Position sizing method is confirmed, not left on the placeholder.**
   `capital_allocator`'s allocation math is explicitly provisional
   (fixed-fraction ranked by deflated Sharpe) — confirm this is the
   deliberate choice for go-live, not an unfinished placeholder mistaken
   for a decision (see `../02-reference-repos-core-logic.md` for the
   Kelly/fixed-fractional/ATR/risk-parity tradeoffs that were never
   finalized).

## Steps

1. Once tasks 01-04 have actually been implemented and run (not just
   planned, as this whole folder currently is), fill in a dated pass/fail
   against each of the 7 items above.
2. Any item that's `fail` blocks go-live — no partial credit, no
   "close enough."
3. Store the completed gate checklist itself somewhere durable (this
   folder is a reasonable place) with the date it was evaluated, so
   there's a record of exactly what was verified before the first real
   order, the same traceability discipline the pipeline itself enforces
   on every trading decision.

## Acceptance criteria

- All 7 items explicitly marked pass/fail with evidence (a manifest
  `test_run_id`, a rotation confirmation, a screenshot of a delivered
  Telegram message — something concrete per item, not just a checkbox).
- A written go/no-go decision, dated, before any real order is placed.

## Dependencies

Depends on tasks 01-04 having actually been executed, not just designed.
This task is the last one in the folder on purpose — it's the summary
judgment, not new work of its own.
