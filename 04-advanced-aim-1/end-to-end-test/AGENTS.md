---
name: e2e-test-agents
status: definition-phase
purpose: single source of truth for running a real end-to-end build of vinu-components — full historical backfill, initial analysis, strategy/research generation, simulation, then a live-mode agent session — for a small ticker set, with an explicit checklist of what "properly stored" means at each step. Nothing here has been run yet.
---

# End-to-End Test — vinu-components, 2022-01-01 → 2026-06-30

## What this folder is for

A runbook, not a design document. Everything in
`03-on-agent-consiuness/` and `04-agentic-still-refinement/` designed and
shipped *mechanisms* (the Facts Registry, debrief-on-close, prospective
fact-check, freshness reader, the signal-usage contract, the recompute
scan) and verified each one with unit/integration tests in isolation. None
of that proves the *whole system* — 10 services, real historical data,
real strategy generation — works together end to end. This folder is that
proof, walked step by step so whoever runs it (a future agent instance or a
human) knows exactly what to do, what command to run, and what "worked"
looks like before moving to the next step.

## Scope — fixed for this run, not re-litigated per file

- **Date range: `2022-01-01` → `2026-06-30`.** This is the historical
  window every service backfills/analyzes/backtests against. Chosen
  because `vinu-stock-price`'s own backfill orchestrator hard-floors at
  `MIN_BACKFILL_YEAR = 2022` (`backfill/orchestrator.py:25`) — there is no
  data before 2022 to fetch regardless, so this is the earliest honest
  start date, not an arbitrary choice.
- **Tickers: `AAPL`, `TSLA`, `JNJ`.** Same three used throughout this
  project's prior testing (the direction-prediction finding, the
  significance-classifier work, the JNJ fabrication replay) — and already
  the live contents of `data/shared/watchlist.json`. Not re-chosen here.
- **Everything runs against the real Docker stack** (`docker compose up
  --build`), not mocked services — this is the point of an end-to-end test.
- **The real Alpaca live-broker connection is explicitly deferred, not
  part of this pass.** Every verification here — including the final
  agent replay in `05` — runs through `HistoricalFillBroker` (replay
  mode). `vinu-live`'s real order-execution path is a separate, later
  check. Stated once here; not re-raised as an open question in the files
  below.

## The five files in this folder

1. [`01-setup-and-rebuild.md`](01-setup-and-rebuild.md) — rebuild every
   container from a clean state, confirm health, set the ticker/watchlist.
   Do this first; nothing downstream works against a stale or half-built
   stack.
2. [`02-component-triggers-and-verification.md`](02-component-triggers-and-verification.md) —
   the main checklist. One section per service in dependency order
   (news/stock-price → features → initial-analysis → strategy/research →
   simulator → portfolio/agent → live): the exact command/route to trigger
   it for this date range and ticker set, and the exact read-route or file
   to check afterward to confirm the data actually landed — not just that
   the call returned 200.
3. [`03-strategy-research-and-simulation.md`](03-strategy-research-and-simulation.md) —
   strategy generation (`vinu-research`) and simulation (`vinu-simulator`)
   get their own file rather than one more section in file 2, because
   they're multi-step (generate → validate → promote → simulate) and
   because this is the step most likely to silently do nothing (e.g.
   `POST /research/ensure` no-ops if a strategy artifact already exists) —
   worth walking through deliberately rather than as one row in a table.
4. [`04-portfolio-and-strategy-verification.md`](04-portfolio-and-strategy-verification.md) —
   confirms `vinu-strategy` and `vinu-portfolio` actually reflect what `03`
   generated, not just that `vinu-research` says it exists. Added after the
   first pass of this folder found this gap explicitly.
5. [`05-one-month-agent-verification.md`](05-one-month-agent-verification.md) —
   the real end-to-end check: a full month of `vinu-agent` replay, walked
   question-by-question against `../01-vinu-questions-prompt.md`'s
   8-question daily ritual, per ticker — including confirming Piece 2
   (debrief-on-close) actually wrote a real `realized_pnl` evidence entry
   against a closed position. Replaces an earlier, shallower "run a short
   session" close-out that never touched PnL at all.

## Execution order — do not skip ahead

`01` → `02` (in the order its sections are written, which mirrors
`docker-compose.yml`'s `depends_on` chain) → `03` → `04` → `05`. Each
file's last section is "what to confirm before moving on" — treat that as
a gate, not a suggestion. If a step's verification fails, stop and fix it
there; a downstream service reading from an empty upstream store will not
fail loudly, it will just quietly produce empty or degenerate output (this
is exactly the class of bug this whole project exists to catch).

## What "done" looks like for this folder

Every verification checkbox in `02` through `05` passes for all three
tickers. `05`'s one-month replay is the point where every individually-
verified piece — data pipeline, strategy generation, the Facts Registry,
the freshness reader, debrief-on-close, prospective fact-check — gets
checked together, against real (replay) trading days, not assumed to work
together just because each piece passed its own unit tests.

## What this folder does not cover

- Re-verifying the 4 items from `03-on-agent-consiuness/01-plan-and-implementations`
  or the 3 components (`vinu-agent`'s 5 pieces, plus `vinu-initial-analysis`
  and `vinu-research`) from `04-agentic-still-refinement/implementation-plan-from-04`
  individually — those already have their own unit/integration tests
  (280 passing in `vinu-agent`, 500 in `vinu-research`, 4 in
  `vinu-initial-analysis`, per `implementation-plan-from-04/*/status.md`).
  This folder is about the *system*, not re-proving mechanisms already
  proven in isolation.
- An agent replay over the **entire** 2022-01-01 → 2026-06-30 window —
  `05` runs one real month (2026-06), not the full 4.5 years, per the same
  "don't re-run the expensive thing beyond what's needed to check it"
  discipline used everywhere else in this project. A single month is
  enough to exercise a position opening and closing (needed for the
  PnL/debrief check) without paying for a multi-year replay.
- The real Alpaca live-broker connection — see the scope note above.
