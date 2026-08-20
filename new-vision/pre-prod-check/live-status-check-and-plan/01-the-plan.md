---
name: the-plan
status: planning only — not yet implemented
purpose: one simple, complete plan — check the live pipeline one stage at a time, and how results get stored. Nothing else mixed in.
---

# The plan

Containers stay running exactly as they are. Nothing gets rebuilt or
restarted for this. One real ticker gets pushed through the pipeline,
one stage at a time, in order. For each stage:

1. Call/trigger the real stage (the actual live endpoint or worker — not a
   copy, not a mock).
2. Look at the actual response that comes back.
3. Confirm exactly where that response got stored (which real database/table).
4. Write down pass or fail, one line, before moving to the next stage.

If a stage fails, stop there — don't check the stages after it, since
they'd just be failing because the one before them already failed.

## The stages, in order

| # | Stage | What to call | What "pass" means |
|---|---|---|---|
| 1 | `watchlist_gate` | change-gate ahead of Summary Agent | ticker correctly flagged changed/unchanged, and if changed, Summary Agent picks it up next cycle |
| 2 | `summary_agent` | Summary Agent (`angle_synthesizer`) | summary + cross-angle consensus gets written to `TickerSummaryStore`; confirm by reading it back and seeing today's run |
| 3 | `planner_triage` | Planner triage | fit tier + priority computed from the stored summary; `HypothesisRegistry` was consulted before proposing |
| 4 | `planner_idea` | `idea_generator` | a recipe + parameter space gets chosen and reaches Researcher/Executor intact |
| 5 | `sweep_execute` | Researcher/Executor (role b) | `run_parameter_sweep` completes, ranked results reach role c |
| 6 | `sweep_verdict` | Researcher/Executor (role c) | PASS/FAIL decided; on PASS the candidate reaches `risk_gatekeeper` |
| 7 | `risk_gatekeeper` | `risk_gatekeeper` | verdict computed from real portfolio data; APPROVED moves to pending-allocation |
| 8 | `capital_allocator` | `capital_allocator` cadence run | funded → `mark_active` called, Live+Shadow actually picks it up |
| 9 | `live_shadow` | Live+Shadow / `ShadowEvaluator` | paper twin running off the real price feed |
| 10 | `monitor` | Monitor / `TradePlanOrchestrator` | hold/flag/drop decided; result reaches `HypothesisRegistry` |

Optional entry point, run separately: `thesis_intake` — same checks, entering
through the human-theory door instead of the watchlist.

Cross-cutting, checked once at the end (not per-stage): `ticker_ledger_writes`
(every stage above actually wrote its row to `TickerLedger`, in order),
`kill_switch_gate` (engaging it blocks funding, disengaging resumes),
`significance_triage` (only checkable once Telegram/Discord keys are set).

**Note:** the exact real call for each stage (HTTP endpoint vs. a background
worker's own cycle) still needs confirming against `vinu-agent`'s actual
route/worker code before this table is final — filling that in is the very
next step, not yet done.

## How results are stored

One simple database file. One row per stage checked, per ticker, per run.

```
test_run_id | ticker | stage | status | timestamp | what_was_checked | notes
```

- `status` — pass or fail, nothing else.
- `what_was_checked` — the actual response received and the actual place it
  got stored (e.g. "TickerSummaryStore row for AAPL, run_id abc123").
- `notes` — only filled in on fail, specific enough to know what broke
  without re-reading logs.

Same ticker + same stage + same run always updates the same row — never
duplicates. That way if this gets interrupted halfway through, re-running it
picks up exactly where it left off instead of starting over.

## It's not done after one ticker passes golden path

One ticker passing all 10 stages proves the pipeline *can* work. It doesn't
prove it's fully checked. These also have to run, same table/storage format
as above, before this counts as complete:

### Failure scenarios — same stages, deliberately pushed off the happy path

| # | Scenario | What it proves |
|---|---|---|
| 1 | Golden path, one ticker, no failures | already covered above |
| 2 | Sweep self-verdict FAILs, ticker gets re-proposed | the FAIL reasoning actually changes the *next* proposal, not just gets logged |
| 3 | `risk_gatekeeper` REJECTS | artifact isn't discarded, reason reaches Planner loop-back AND Significance Triage |
| 4 | Kill Switch engaged mid-flow (after APPROVED, before `capital_allocator` runs) | funding lands "funded but blocked," never silently ACTIVE; disengage resumes cleanly |
| 5 | Thesis Intake: near-duplicate theory submitted right after the first | rejected by the cheap check before an LLM call happens |
| 6 | Thesis Intake: ticker already at K-cap via watchlist, then a new theory submitted for it | shared K-cap counter blocks it — not accepted just because Thesis Intake's own dup-check doesn't know about the watchlist path |
| 7 | Rebalance REQUEST hits a position Monitor is evaluating the same cycle | no race — Monitor keeps authority, rebalancer never closes anything directly |
| 8 | Position decays to Monitor's drop threshold | written to `HypothesisRegistry`, and the *next* Planner pass on that ticker actually reads it |
| 9 | Two tickers reach "approved, pending allocation" in the same `capital_allocator` batch | the correlation check runs across both together, not each alone |

Run each on at least 2 different real tickers — one ticker passing isn't
enough to prove the logic is general and not ticker-specific.

## The full-check gate — every box below has to be checked, no partial credit

- [ ] All 10 golden-path stages + all 9 scenarios above = `pass`, on ≥2 tickers each.
- [ ] `ticker_ledger_writes`, `kill_switch_gate`, `significance_triage` cross-cutting checks = `pass`.
- [ ] Alpaca key rotation confirmed done at the provider (the leaked pair from
      git history — still just being removed from tracking isn't enough).
- [ ] `scripts/setup-secrets.sh --check` passes with zero missing on the real
      deployment target, not just this dev machine.
- [ ] A real Telegram/Discord message observed actually arriving, not just
      the code path running without error.
- [ ] Kill Switch manually engaged and disengaged at least once on this real
      deployment, by an actual person, not just in a test.
- [ ] The `env_file: .env` gap is fixed or explicitly accepted in writing —
      right now every container gets real secret values as plain environment
      variables regardless of what's in its `secrets:` list, which partly
      undermines the whole point of the `/run/secrets` file mechanism.
- [ ] Position-sizing method (currently fixed-fraction ranked by deflated
      Sharpe) confirmed as the deliberate go-live choice, not an unfinished
      placeholder.
- [ ] Every route this system actually exposes has been exercised by
      something in this plan — cross-checked against a full read of the code
      (in progress, background) so nothing real gets left untested.

Real capital doesn't move until every box above is checked. A partial pass
is a fail.

## Next step

Build the database file, then go through `vinu-agent`'s real code to fill in
the exact call for each of the 10 golden-path stages in the table above.
