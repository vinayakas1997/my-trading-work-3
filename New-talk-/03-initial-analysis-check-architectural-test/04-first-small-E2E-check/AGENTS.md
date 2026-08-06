---
name: e2e-check-agents-directions
status: not-started
purpose: direct instructions for whichever agent actually executes this E2E check — written so a cold agent with no prior conversation context can pick this folder up and run it correctly.
---

# AGENTS.md — Directions for Running This Check

You are executing the **first small end-to-end check** of the `vinu`
trading-analysis project's stage-1 pipeline against **real** data. This
is not a unit-test run and not a synthetic-fixture run — the entire
point is to exercise the real Alpaca feed, real model weights (where
they exist), and the real Docker containers, because almost none of
this pipeline has touched real data before now.

## Read these first, in order

1. `plan.md` in this folder — the full ordered plan (models →
   start-date/quarter-boundary reality-check → Alpaca creds → the
   actual pipeline steps → container deploy). Follow its order; each
   step depends on the one before it.
2. `01-vinu-news.md`, `02-vinu-stock-price.md`,
   `03-vinu-initial-analysis.md` — per-component checklists. Work
   through these while executing `plan.md`'s step 5 ("small pipeline").
3. **If `03-vinu-initial-analysis.md` already has a `Round 1` entry in
   its Bugs & Fixes Log, check whether `04-round-2-tier2-fix-verification.md`
   exists in this folder before doing anything else** — it means a bug
   was already found and fixed after Round 1, and this run's job is to
   verify that specific fix, not to redo Round 1 from scratch. Follow
   that file's steps instead of re-running the full `plan.md` step 5.
4. If you need more background on *why* something is designed the way
   it is, the parent folder `../03-actual-plan-findings/` has the full
   API design, storage design, and build-status audit this check is
   measured against. Don't re-derive decisions already made there —
   read them.

## Ground rules

- **Real data only.** Do not fabricate output, do not mark something
  "done" because it should theoretically work — actually run it and
  observe the real result.
- **Honest labeling stays honest.** If an angle reports
  `model_backend: fallback_proxy`, that's expected for `moirai`/`moment`/
  `lag_llama` (documented env-conflict reasons) — don't try to force
  them to `pretrained` as part of this check; that's out of scope here.
  If a *different* angle that should be `pretrained` reports
  `fallback_proxy` instead, that's a real bug — investigate why (most
  likely: models weren't downloaded before container start, see
  `plan.md` step 1) and record it.
- **Scope stays at 3 containers.** `news-api`, `stock-api`,
  `initial-analysis-api` only. Do not bring up `features-api` or any of
  the other 7 services in the root `docker-compose.yml` — they're
  later-stage and not part of what this check validates. If you're
  tempted to bring one up "just to check something," stop and ask
  instead — that's a scope decision, not something to make
  unilaterally.
- **Don't silently work around a real bug.** If something is broken (a
  container won't boot, an endpoint 500s, a value looks nonsensical),
  the job is to record it accurately in the relevant component file's
  `BUGS-N` section — not to quietly patch around it and move on without
  a trace, and not to declare the check "passed" with a known issue
  unmentioned.
- **Fix only what's clearly a bug, not what's a known documented
  limitation.** Several things are *already known* to be incomplete
  (granularity not threaded through storage yet, no quarter-boundary
  scheduler, `start_date` not enforced) — these are called out
  explicitly in `plan.md` and the per-component files precisely so you
  don't mistake them for new discoveries or "fix" them as an unplanned
  detour. If you do fix one, that's a real scope expansion — flag it
  clearly rather than bundling it in silently.
- **Record bugs and fixes round-wise.** Each component file has a
  `## Bugs & Fixes Log` section with `### Round 1` (`BUGS-1`/`FIXES-1`)
  already scaffolded. If you fix something and re-run the check to
  verify, add `### Round 2` (`BUGS-2`/`FIXES-2`) rather than editing
  Round 1's entries — the round-by-round history is the point, not just
  the final state.
- **This check is deliberately small.** One ticker (`AAPL` suggested),
  a short recent window, 3 angles in `vinu-initial-analysis` — not all
  32 methods, not all tickers, not the full `2022-01-01→now` history.
  If everything here passes cleanly, that's the signal to scale up next
  — don't scale up preemptively inside this same check.

## What "done" looks like

- All 3 containers boot cleanly with real `.env` values.
- Real Alpaca `1min` bars for the test ticker are on disk in the
  redesigned storage shape.
- Real news articles for the same ticker are ingested and at least one
  Section-1 method produces a real (non-error) result over them.
- The 3 chosen `vinu-initial-analysis` angles complete a real
  trigger → poll → `tier3` result cycle, and their output values have
  been eyeballed for plausibility against the real price series, not
  just checked for "did it 200."
- Every component's `BUGS-N`/`FIXES-N` log reflects what actually
  happened during the run — including "none found" where that's
  genuinely true.
- The 2 real findings this plan already surfaced (`start_date` not
  enforced, no quarter-boundary scheduler) are either reconfirmed as
  still true, or corrected in `plan.md` if this run finds otherwise.

## What comes after this check (not part of this task)

Once this small check passes, the next steps discussed but **not**
started yet are: (1) scaling this same check to more tickers/the full
date range, and (2) building the two-tier per-angle explanation docs
(general + deep) discussed separately — that second item specifically
depends on this check's real observed output ranges to be written
honestly rather than speculatively. Don't start either of those inside
this task unless explicitly asked.
