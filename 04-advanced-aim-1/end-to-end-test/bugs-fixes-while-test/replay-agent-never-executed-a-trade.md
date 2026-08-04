---
name: replay-agent-never-executed-a-trade
status: confirmed-real-finding-not-yet-root-caused
severity: breaks-q4-and-q5-of-the-8-question-ritual
---

# Finding: across the full 22-day June-2026 replay, the agent never called a trade-execution tool

## What was wrong

Asked to report P&L per ticker/strategy for the completed `e2e-2026-06`
replay. Initial per-day `response.json` summaries all showed
`"action": "none"` — consistent with either a genuinely flat month or a
broken "final decision" parse. Verified directly against the raw
`thinking.json` full react trace for all 22 days rather than trusting the
harness's parsed summary:

- Counted every `tool_calls` entry across all 22 days. Full inventory of
  tools actually invoked all month: `get_stock_price` (60), `get_fundamentals`
  (41), `get_news` (33), `get_features` (30), `get_portfolio` (21),
  `compact` (5). **Zero** calls to any trade-execution tool.
- The trading tools do exist in the codebase
  (`vinu_agent/tools/trade_tool.py`, `vinu_agent/tools/trade_plan_tool.py`)
  — this is not a missing capability, the agent simply never reached the
  point of calling them.
- 13 of 22 days end their react trace on a bare `tool`-role step, with no
  final assistant synthesis message at all that day — the loop was cut
  off, not concluded.
- The `response.json` "final" text on most other days is early-stage
  planning ("Let me gather fundamentals, news...") — an artifact of
  `write_day()`'s fallback (last assistant message with non-empty
  content, scanned backward), not a real decision, since no decision
  message existed to find.
- Recurring real errors throughout the trace: `Technical indicators
  failed`, `Fundamentals calls errored`, `Features API is down`,
  `LLM call failed at iteration N: ... Request timed out`, and on
  2026-06-29 a hard failure: `Context size has been exceeded` (LLM context
  window overflow, `error_code: 500`).
- Account state confirms this independently: every day's
  `account_snapshot.json` (including the final day, 2026-06-30) shows
  `cash: 100000.0`, `positions: {}`, `ledger: []` — completely untouched
  from the starting balance.

## Why it mattered

Directly breaks two of the 8-question ritual's checks
(`05-one-month-agent-verification.md`): Q4 (realized PnL evidence on a
closed position) and Q5 (confirm `generate_trade_plan` was called at
least once). Neither can be satisfied — not because the questions are
unanswerable, but because the underlying event they check for never
happened. This also means the month-long replay, as run, cannot exercise
Piece 2 (a position actually closing) at all, one of the two reasons `03`
explicitly said a short session wasn't sufficient.

## What this is NOT

Not the same thing as the Step 03 standalone strategy backtests
(`vinu-research` + `vinu-simulator`, real historical P&L over
2022-01-01..2026-06-30: AAPL −3.89% total return, TSLA +8.44%, JNJ
−0.08%). Those are the generated strategy's own backtested performance,
computed independently of the live agent — not evidence of what the
live agent did during this replay. Easy to conflate; kept as two separate
numbers here on purpose.

## What was fixed

Nothing yet — this is a finding, not a fix. Root cause is not pinned down:
plausible contributors visible in the evidence are (a) the LLM's 32K
context window being exceeded on a multi-tool-call day as the session's
history accumulated over the month (`Context size has been exceeded` on
06-29), (b) repeated real backend flakiness (`features-api`,
`initial-analysis` calls erroring mid-turn) forcing extra retry
tool-calls that ate into whatever per-turn iteration/time budget exists,
and (c) a possible missing step-budget increase or context-trimming
strategy for a session meant to run 22 turns back-to-back. Needs follow-up
investigation into the agent's own iteration-limit/step-budget config and
context-management strategy before concluding whether this is a config
issue or a deeper design gap.

## What was achieved

Got a real, verifiable answer (not a guess) to "what was the P&L": zero,
across all three tickers, because zero trades were ever placed — confirmed
by an exhaustive scan of every tool call in the full trace, not by trusting
the harness's own summary field, which independently confirms bug
[`replay-harness-poll-timeout-crash.md`](replay-harness-poll-timeout-crash.md)'s
sibling issue: `write_day()`'s "find the last assistant message" fallback
silently produces a plausible-looking but wrong "final decision" when the
real one never arrived — the same "looks done, isn't" shape as several
earlier bugs in this file.
