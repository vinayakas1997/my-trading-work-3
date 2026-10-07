# Strategy enhancer

**Status: built and tested.** All 10 real evaluation steps wired, the
K-cap bug fixed, and the enhancer loop feeding real sibling/failure
context into new candidates. See `02-implementation.md` for the full,
dated build log. A few real, documented items remain open (see that
file's own "Still open" section) — this isn't a claim that everything
imaginable here is finished, just that the plan in `01-plan.md` is.

## The idea, in one paragraph

Every ticker can have up to 3 candidate trade strategies "in flight" at
once (the K-cap). Right now, when a candidate gets rejected at any point
in the real evaluation chain, that slot doesn't free up — a real bug
found live means the cap counts every candidate a ticker has *ever* had
proposed, forever, with no reset. The fix isn't just "make the cap work
again": once it does, a rejection should actively feed the *next*
candidate — the new idea should know what the other in-flight candidates
already look like (so it doesn't duplicate them) and exactly why the
last one failed (so it doesn't repeat the same mistake). That turns
rejection from a dead end into an input, which is what makes this an
"enhancer" rather than just a bug fix.

## Where this came from

Found live, 2026-09-21, while running a real end-to-end test of the
system (main stack + a local LLM) — not designed up front. Investigating
why a real ticker (AAPL) never got a new trade candidate proposed led to
the K-cap bug, which led to mapping the full real chain a candidate
strategy actually passes through, which led to this idea.

## What's in this folder

- **`00-explanation.md`** — the detailed writeup:
  1. The exact K-cap bug (file/line, real data showing it firing).
  2. The full pre-ACTIVE evaluation chain (7 steps, what each one
     actually checks, LLM vs deterministic).
  3. Which steps' rejection reasons are actually saved anywhere today
     (mixed — some are, some aren't).
  4. **Three more real "hold on degradation" mechanisms**, once a
     strategy is already live — at three different levels (one trade
     plan, one strategy's paper-vs-backtest proof, one strategy's
     ongoing health, and the whole portfolio's real equity) — plus which
     of these already auto-retriggers a new attempt on its own (a real
     precedent to reuse, not reinvent).
  5. Proof that real order placement is structurally unbypassable
     (traced every real caller, not assumed) — and an honest note on
     what's *not* proven unbypassable yet.
  6. A mermaid diagram of the full lifecycle, all levels in one picture.
  7. The proposed enhancer design, broken into a real, ordered build plan.
- **`01-plan.md`** — the implementation plan, kept up to date against
  what was actually built (every section now marked **DONE**, with the
  real corrections found along the way — several real call sites
  differed from the original guesses).
- **`02-implementation.md`** — the full, dated build log: every real
  finding, every test suite run, and the honest "still open" list.

## Current state

Built. All 10 real evaluation steps are wired into their real call
sites across `vinu-agent`, `vinu-research`, and `vinu-live`; the K-cap
bug is fixed (a 7-day rolling window — the more exact fix needs a
join that doesn't exist yet, see `02-implementation.md`); the enhancer
loop feeds real sibling/failure context into new candidate proposals;
and the read view (`vinu-agent strategy-eval <TICKER>`) shows, for any
ticker, what passed, what failed, and why — both the specific reason
and the general rule. All 4 touched packages' test suites are green.
See `02-implementation.md`'s "Still open" section for the one honest
remainder — the exact-fix follow-up for the K-cap.
