---
name: day-stepper-replay-harness
component: vinu-agent (new orchestration script, calls existing HTTP API)
status: not-started
---

# Item 3 — Day-Stepper Replay Harness

## What this is

The orchestrator that actually runs the month. It does not reimplement
any agent logic — it drives the real `vinu-agent` HTTP API
(`POST /agent/sessions`, `POST /agent/sessions/{id}/messages`) exactly
like a real user or cron job would, one simulated trading day at a time,
advancing `as_of` each step.

## Why an external script, not a new service

Nothing here needs to be a long-running service — it's a finite loop over
a fixed calendar of trading days that finishes and produces a report.
Matches the pattern of `vinu-agent/scripts/generate_tool_catalog.py`
(host-side script hitting the running stack), not a new Docker Compose
service.

New file: `vinu-components/vinu-agent/scripts/run_month_replay.py`

## Step 0 — verify data coverage before picking exact dates

Do not hardcode a start/end date without checking real coverage first.
Query (via the running stack, sequenced one request at a time per the
project's SQLite-concurrency rule):
- `vinu-news`'s per-ticker `backfill_status` for AAPL, TSLA, JNJ — confirm
  `newest_ts` covers the candidate window for all three.
- `vinu-stock-price`'s candle range for the same three tickers, same
  window, both daily and 1-minute resolution (1-minute matters if the
  agent is expected to reason intraday, not just on daily bars).
- `vinu-initial-analysis`'s stored angle output for the window (a `GET
  /analysis/angle/news_price_causality/{ticker}` covering the dates,
  confirming `significance_score` rows exist, not just raw impact rows).
Pick the most recent fully-covered ~20-23 trading-day window (one
calendar month) across all three tickers. Record the exact confirmed
start/end dates in this file's corresponding `testing-status/` log before
running anything.

## Per-day loop

For each trading day `D` in the confirmed window, in order:
1. Compute `as_of = D 09:30:00 ET` converted to UTC ISO 8601 (the agent's
   decision point — start-of-regular-session; this replay does not cover
   premarket, see `full-plan.md`'s note on Section 2 of the premarket
   questions doc).
2. Reuse the **same session** across the whole month (create it once on
   day 1 with `as_of` set, then update `as_of` on the session's stored
   `config` before each day's message — do not create a fresh session
   per day, or the agent loses continuity/memory of its own prior
   decisions and losses, which defeats the point of testing loss
   adaptation).
3. Send a fixed, realistic daily prompt — something close to what a real
   scheduled morning trigger would send, e.g.: *"It's the start of the
   trading session on {date}. Review your current positions, account
   state, and any relevant signals for AAPL, TSLA, and JNJ. Decide what
   action, if any, to take today, and explain your reasoning before
   acting."* Keep this prompt fixed across the whole month — changing it
   day to day would confound "did the agent adapt" with "did the prompt
   change."
4. Let the agent run its normal tool-calling loop (`AgentLoop.run`,
   unchanged) — it may call `get_news`, angle/analysis tools,
   `get_options_greeks` (which correctly reports unavailable, per item
   1), and `TradeTool` (which fills via item 2's historical broker).
5. Record, per day, split into two separate files (see "Output layout"
   below) so a human can read the final decision without wading through
   the full trace, or drill into the full trace when the decision looks
   wrong: (a) the **thinking** — the complete ordered trace of everything
   the agent produced while reasoning about this day (its assistant
   `content` text interleaved with every `tool_calls` request and every
   tool result, exactly as `AgentLoop.run`'s `full_history` already
   assembles it, see `agent/loop.py`), and (b) the **response** — just
   the final assistant message plus a short structured summary (action
   taken, symbol, qty, side, reasoning excerpt).
6. Advance to `D+1`.

## Output layout — one folder per run, thinking and response kept separate

```
the-1-month-back-testing/results/<run-id>/
  manifest.json              # tickers, confirmed window, prompt template, model
  2026-07-06/
    thinking.json            # full ordered trace: assistant content + tool_calls + tool results, in order
    response.json            # final decision only: {action, symbol, qty, side, reasoning_excerpt}
    account_snapshot.json    # get_account()/get_positions() after this day's decision
  2026-07-07/
    thinking.json
    response.json
    account_snapshot.json
  ...
```

**Important honesty note (confirmed by reading `agent/loop.py` and
`agent/llm.py`):** this LLM setup has no separate hidden
chain-of-thought/reasoning field — there is no `reasoning_content` or
equivalent parsed anywhere in the current code. "The thinking" that gets
stored in `thinking.json` is whatever the model chose to write as visible
`content` alongside its tool calls, plus the tool calls and their results
themselves. It is not a deeper internal thought process the model is
hiding — it's the model's own stated reasoning, verbatim. Don't describe
`thinking.json` to a reader as more than that.

## Files to touch

- New: `vinu-components/vinu-agent/scripts/run_month_replay.py`
- New: the output directory structure above,
  `the-1-month-back-testing/results/<run-id>/` (item 4 reads `response.json`
  and `account_snapshot.json` per day for the P&L report; item 5 reads
  `thinking.json` per day for the behavioral rubric).
- No production `vinu_agent` source files beyond what items 1 and 2
  already touch — this script only calls the HTTP API.

## Expected output / how to verify

- A confirmed, logged data-coverage window (step 0) before any day is
  run.
- One `thinking.json` + `response.json` + `account_snapshot.json` per
  simulated day, per the "Output layout" above — confirm the split is
  actually clean (`response.json` genuinely readable alone, without
  needing `thinking.json` to understand what was decided).
- A monotonically advancing `as_of` across the run, with no day skipped
  and no day's transcript showing data dated after that day's `as_of`
  (spot-check a handful of days' tool results against the requested
  `as_of` to catch a lookahead-guard failure early, don't just trust item
  1's own tests).
- The run completes end-to-end for the full month without a crash;
  partial/interrupted runs must be resumable from the last completed day
  (store progress, don't restart from day 1 on failure — a month of LLM
  calls is expensive to redo).
- Sequencing note: this will generate many requests to `news-api` and
  `initial-analysis-api` over the run — keep it single-threaded/sequential
  per the existing project constraint, do not parallelize days to "speed
  it up."
