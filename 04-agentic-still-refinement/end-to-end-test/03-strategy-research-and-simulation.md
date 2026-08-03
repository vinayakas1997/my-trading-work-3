---
name: e2e-strategy-research-simulation
status: definition-phase
---

# Step 3 — Strategy Generation (`vinu-research`) and Simulation (`vinu-simulator`)

## Why this gets its own file

Unlike the services in `02`, this step is multi-stage (generate → backtest
→ validate → **manually approve** → promote), and it's the step most likely
to *silently do nothing* rather than fail loudly — e.g. `POST
/research/ensure` no-ops if a symbol already has an `ACTIVE`/`MONITORING`
strategy artifact, which is correct behavior but easy to mistake for "it ran
and found nothing worth generating." `vinu-strategy` itself has **no
generation trigger at all** — it only exposes read/evaluate routes; all
generation happens through `vinu-research`. Get this ordering wrong and
you'll be debugging the wrong service.

**The approve step is not optional and is easy to skip**: `POST
/research/run` only produces a *run* — it never creates an artifact by
itself, regardless of how good the backtest looks. Promotion only happens
via a separate, explicit `POST /research/runs/{run_id}/approve` call (step 3a
below) — confirmed against the actual code
(`vinu_research/service.py`'s `run_research()` vs. `approve_run()` →
`_create_artifact_from_run()`), and against
[`understanding-project/a-new-strategy-added.md`](../understanding-project/a-new-strategy-added.md),
which names this exact skip as "the one people skip, because step 1 already
returns a `completed` status that *looks* like the strategy is done." Miss
this step and `/research/artifacts` will stay empty forever, `04`'s
`vinu-strategy`/`vinu-portfolio` checks will have nothing to find, and `05`'s
month-long replay will have no promoted strategy to trade against — not
because anything is broken, but because this step never ran.

## 1. Confirm prerequisites are actually met first

Strategy research reads from `vinu-tools` (features), `vinu-initial-
analysis`, and `vinu-stock-price` — all three must already be backfilled
per `02` before triggering this. Don't start this step on the assumption
`02` "probably worked"; re-check its verification checkboxes for all 3
tickers first.

## 2. Trigger strategy generation

Two routes exist, both on `vinu-research` (port 8087), same payload shape:

- `POST /research/run` — **always** runs the full generate → backtest →
  validate pipeline, regardless of existing artifacts, and writes a
  `ResearchRunRecord`. It does **not** promote anything on its own — see the
  approve step (3a) below. Use this for the first run of this e2e test,
  since there's nothing to skip yet.
- `POST /research/ensure` — skips if the symbol already has an
  `ACTIVE`/`MONITORING` artifact. Use this on a re-run of this checklist,
  not the first time.

```bash
curl -X POST http://localhost:8087/research/run \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "from_date": "2022-01-01",
    "to_date": "2026-06-30",
    "user_idea": null,
    "strategy_code": null,
    "dry_run": false
  }'
```

Repeat for `TSLA` and `JNJ`. This is a real code-gen + backtest + promotion
pipeline — expect it to take meaningfully longer than any single call in
`02`, and expect it to make real LLM calls (confirm the LLM endpoint from
`01`'s checklist is actually up before triggering this, not after it times
out).

## 3. Verify strategy generation actually produced something

```bash
curl -s http://localhost:8087/research/runs
curl -s "http://localhost:8087/research/runs/{run_id}"
curl -s http://localhost:8087/research/artifacts
curl -s http://localhost:8087/research/hypotheses
curl -s "http://localhost:8087/research/symbols/AAPL/state"
```

Confirm, per symbol:

- At least one run in `/research/runs` with a completed (not failed/
  timed-out) status.
- Read the run's actual backtest metrics (Sharpe, drawdown) rather than
  just its status — a "completed" run with a degenerate Sharpe (exactly 0,
  or identical across symbols) usually means something upstream (features
  or price data) was empty, not that the strategy is genuinely bad.
- **`summary_text` is non-empty** on each run (check the same
  `/research/runs/{run_id}` response) — this is the plain-English narrative
  added specifically to close the "how does anyone find out what happened"
  gap found while writing this folder. Empty `summary_text` with
  `llm_enabled: true` in `vinu-research`'s config means the LLM call
  failed silently; check the LLM endpoint from `01` is actually reachable.
  Empty `summary_text` with `llm_enabled: false` is expected — the feature
  is gated on that flag, not a bug.

## 3a. Approve each run — the mandatory, easy-to-skip step

Nothing auto-approves a run, regardless of how the backtest metrics look.
For each symbol, take the `run_id` from step 3's completed run and approve
it explicitly:

```bash
curl -X POST http://localhost:8087/research/runs/{run_id}/approve
```

### Verify

```bash
curl -s http://localhost:8087/research/artifacts
```

Confirm each of the 3 symbols now has an artifact here. An empty artifact
list **at this point** (after approving) means the run was genuinely
rejected by promotion criteria (e.g. routed to `BENCHING` instead of
`ACTIVE` on a correlation-blocked result) — a legitimate outcome, worth
documenting, but different from an empty list before approving, which just
means the approve call hasn't happened yet and proves nothing about
promotion criteria either way.

### Document

- Whether the approve call actually returned an artifact per symbol, and if
  not, what status it landed at instead (`ACTIVE` vs. `BENCHING` vs.
  rejected) — don't collapse these into a single "didn't work" bucket.

## 4. Trigger simulation

**Use `/simulator/simulate/custom`, not `/simulator/simulate`.** The plain
`POST /simulator/simulate` route takes a `strategy_name` and fetches its
weight data from **`vinu-strategy`** — which, per
[`understanding-project/a-new-strategy-added.md`](../understanding-project/a-new-strategy-added.md),
has zero awareness of anything `vinu-research` produces (it's a separate
YAML rule engine). Calling it with a research artifact's name (e.g.
`AAPL_4`) always fails with `"No weight data found for strategy..."` — not
a timing issue, a structural one; there is no path by which it could ever
work for a research-generated strategy. Use
`POST /simulator/simulate/custom` instead, with the approved run's own
`strategy_code` verbatim:

```bash
# {run_id} is the numeric research run id from step 3a (e.g. 4), not the
# artifact_id string. Fetch the approved run first to get its strategy_code:
curl -s "http://localhost:8087/research/runs/{run_id}"
```

```bash
curl -X POST http://localhost:8085/simulator/simulate/custom \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_code": "<the approved runs strategy_code field, verbatim>",
    "class_name": "UserStrategy",
    "symbols": ["AAPL"],
    "start_date": "2022-01-01",
    "end_date": "2026-06-30",
    "run_validation": true,
    "full_metrics": true
  }'
```

`class_name` is `UserStrategy` for every run observed so far (the fixed
class name `vinu-research`'s codegen always emits) — confirm against the
actual `strategy_code` string rather than assuming, if this ever changes.
Note the field names here are `start_date`/`end_date`, not `from_date`/
`to_date` like `vinu-research`'s payload — easy to transpose by copying the
previous curl call without checking.

## 5. Verify simulation output

```bash
curl -s http://localhost:8085/simulator/runs
curl -s "http://localhost:8085/simulator/results/{run_id}"
```

Confirm the result covers the full requested date range (check the
earliest/latest trade or equity-curve timestamp against 2022-01 and
2026-06, the same boundary-check discipline used for stock-price data in
`02`) and that `full_metrics` actually populated (non-null Sharpe, max
drawdown, trade count) rather than returning an empty metrics object.

## Document, for all 3 tickers

- Research run IDs, final status, and whether an artifact was actually
  promoted (not just "run completed").
- The real backtest Sharpe/drawdown/trade-count per symbol — write these
  down even if they look bad; a legitimately poor backtest is a valid,
  informative outcome for this checklist, a silently-empty one is not.
- Simulation run IDs and confirmed date-range coverage.

## What to confirm before considering this folder's backfill complete

- [ ] All 3 tickers have at least one `vinu-research` run with real
      (non-degenerate) backtest metrics
- [ ] The `POST /research/runs/{run_id}/approve` call (step 3a) was made
      for all 3 tickers — not assumed to happen automatically
- [ ] Documented, per ticker, whether a strategy artifact was actually
      promoted after approving — and if not, why (rejected by promotion
      criteria vs. pipeline error are very different outcomes)
- [ ] All 3 tickers have a `vinu-simulator` run covering the full
      2022-01-01 → 2026-06-30 range with populated metrics

## Next: `04` and `05`, not a short session here

Continue to
[`04-portfolio-and-strategy-verification.md`](04-portfolio-and-strategy-verification.md)
to confirm `vinu-strategy`/`vinu-portfolio` actually reflect what got
generated here, then
[`05-one-month-agent-verification.md`](05-one-month-agent-verification.md)
for the real end-to-end agent check — a full month of replay, walked
question-by-question against `../01-vinu-questions-prompt.md`'s 8-question
ritual, including the PnL/debrief-on-close verification. A short few-day
session isn't enough to exercise a position actually closing (Piece 2)
or the questions that depend on a real stretch of trading days.
