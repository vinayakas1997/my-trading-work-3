---
name: e2e-strategy-research-simulation
status: definition-phase
---

# Step 3 — Strategy Generation (`vinu-research`) and Simulation (`vinu-simulator`)

## Why this gets its own file

Unlike the services in `02`, this step is multi-stage (generate → backtest
→ validate → promote), and it's the step most likely to *silently do
nothing* rather than fail loudly — e.g. `POST /research/ensure` no-ops if a
symbol already has an `ACTIVE`/`MONITORING` strategy artifact, which is
correct behavior but easy to mistake for "it ran and found nothing worth
generating." `vinu-strategy` itself has **no generation trigger at all** —
it only exposes read/evaluate routes; all generation happens through
`vinu-research`. Get this ordering wrong and you'll be debugging the wrong
service.

## 1. Confirm prerequisites are actually met first

Strategy research reads from `vinu-tools` (features), `vinu-initial-
analysis`, and `vinu-stock-price` — all three must already be backfilled
per `02` before triggering this. Don't start this step on the assumption
`02` "probably worked"; re-check its verification checkboxes for all 3
tickers first.

## 2. Trigger strategy generation

Two routes exist, both on `vinu-research` (port 8087), same payload shape:

- `POST /research/run` — **always** runs the full generate → backtest →
  promote pipeline, regardless of existing artifacts. Use this for the
  first run of this e2e test, since there's nothing to skip yet.
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
- At least one artifact in `/research/artifacts` for that symbol — an
  empty artifact list after a "completed" run means the pipeline ran but
  nothing passed promotion criteria, which is a legitimate outcome but a
  different one than "it worked" — document which one actually happened.
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

## 4. Trigger simulation

`vinu-simulator` (port 8085) needs a strategy name to simulate against —
use one of the artifacts confirmed in step 3, not a placeholder:

```bash
curl -X POST http://localhost:8085/simulator/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "<artifact strategy name from step 3>",
    "start_date": "2022-01-01",
    "end_date": "2026-06-30",
    "run_validation": true,
    "full_metrics": true
  }'
```

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
- [ ] Documented, per ticker, whether a strategy artifact was actually
      promoted — and if not, why (rejected by promotion criteria vs.
      pipeline error are very different outcomes)
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
