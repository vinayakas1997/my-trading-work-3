# day-stepper-replay-harness — Test Log

## What will be tested / Expected output

- A confirmed, logged data-coverage window (step 0 of the scope doc)
  before any day is run — exact start/end dates recorded here once
  chosen.
- Per simulated day, three separate files (not one blob):
  `thinking.json` (full ordered trace — assistant content + tool_calls +
  tool results, verbatim), `response.json` (final decision only:
  action/symbol/qty/side/reasoning excerpt), `account_snapshot.json`
  (post-day `get_account()`/`get_positions()`). Confirm `response.json`
  is readable on its own without needing `thinking.json`.
- Confirm `thinking.json` is honestly just the model's visible
  content + tool calls, not a claimed "hidden reasoning" — this LLM setup
  has no separate chain-of-thought field (checked `agent/loop.py` /
  `agent/llm.py`, no `reasoning_content` parsed anywhere).
- A monotonically advancing `as_of` across the run, with no day skipped
  and no day's transcript showing data dated after that day's `as_of`
  (spot-check a handful of days, don't just trust item 1's own tests).
- The run completes end-to-end for the full month without a crash;
  partial/interrupted runs must be resumable from the last completed
  day.
- Full detail: [../../scope-responsibilities/03-day-stepper-replay-harness.md](../../scope-responsibilities/03-day-stepper-replay-harness.md)

## Chosen replay window

### Verified 2026-08-03 against the live stack → **2026-07-06 → 2026-07-31**
**(20 trading days)** for AAPL, TSLA, JNJ. This is the most recent complete
calendar month before today and all three tickers fully cover it:

- **Daily candles** (`stock-api:8081/stock/candles/{sym}?interval=1D`,
  key `bar_ts`, provider alpaca): all three tickers return **identical**
  20-day list — 07-06/07/08/09/10, 13/14/15/16/17, 20/21/22/23/24,
  27/28/29/30/31. No gaps, no missing symbols.
- **1-minute candles** (same host, `interval=1m`) exist within the window,
  e.g. 2026-07-20: AAPL 401 bars, TSLA 396, JNJ 326 (not the nominal 390 —
  a few intraday rows absent for all three; fine for a daily-decision agent,
  note it if item 3 picks 1-minute reasoning).
- **News**: across the window, `news-api`: `/news/ticker/{sym}` — AAPL 166
  articles / 25 distinct days; TSLA 185 / 26 days; JNJ 15 / 10 distinct days
  (sparse but present on trading-days 06,13,14,15,16,22,28,30,31). No ticker
  has a data gap that would zero-out a day.
- **Initial-analysis stored output** (`analysis-api` `/analysis/angle/
  news_price_causality/AAPL`): stored 2026-08-02, 129 rows, 119 of which are
  `impact` with `ar_significant` + `novelty_score` populated. **But see
  Bug-3 below** — the `significance_score` column is empty in the stored data.

All coverage queries above were run one request at a time (no concurrency), per
the project's SQLite-concurrency constraint. None of the three services had to
be rebuilt or re-backfilled to produce this window — it already exists.

## Bug / Fix Log

### Bug-3 — stored `news_price_causality` has impact rows but NO
### `significance_score` (empty model output), which item 3/5 rely on
- **Found during:** step-0 coverage validation for the chosen window (item's
  scope says confirm `significance_score` rows exist, not just raw impact).
- **Date:** 2026-08-03
- **Symptom:** `GET /analysis/angle/news_price_causality/AAPL` → 129 rows,
  119 `type=impact`, all with `ar_significant` + `novelty_score`, but
  **0 rows have a `significance_score` column** and there is **no
  `significance_model_eval` row** either.
- **Reproduction:** the query above; also verified the stored `time_format`
  breakdown is 1min:121 (the branch that would compute it), yet the column is
  absent.
- **Root cause (confirmed in code, not guessed):** `news_price_causality/
  compute.py:43` only computes `significance_score` inside the
  `time_format == "1min"` branch (line 43+), via `score_significance`
  (`significance_model.py:78`). That function **silently returns
  `({}, {}, None)` when the window has too few usable rows or too few positive
  examples** (`len(usable) < 130`, and `y_train.sum() < 10` or
  `y_test.sum() < 3`, lines 128-143). For a single-symbol, single-window stored
  run this threshold is commonly not met → no scores and no eval row, exactly
  what the stored data shows.
- **Why it matters for THIS plan:** (a) item 3 step 0's gate "significance_
  score rows exist" would FAIL for the stored data as-is; (b) item 5 reads
  transcripts for "agent leaning on `significance_score` for direction" — if
  the model never produced scores during the replay run, that whole question
  becomes vacuous unless the replay's /run recomputes with enough history.
- **Not yet a regression/fix:** this is pre-implementation; nothing broken to
  fix yet. It's a scoping catch for implement time — decide whether the replay
  harness should (a) accept that per-article `significance_score` may be
  absent for thin windows and score transcripts on other features, or (b)
  broaden the model's training sample (the model trains on THIS run's own rows
  only, so cross-day/window pooling is the lever). Logged now so the
  "significance_score is the headline feature" expectation isn't assumed
  silently. Cross-reference item 1/2 regressions are N/A here (this is an
  initial-analysis concern, not a vinu-agent one).
- **Severity:** major (affects items 3 step-0 and 5 interpretation), not a
  blocker — the replay can still run and produce honest behavior transcripts.

### Bug-4 — `last_account_snapshot()` fallback reported `cash: null` on every day, including days with genuinely zero trades
- **Found during:** post-run review of `run-2026-07-06-2026-07-31` — every
  single day's `account_snapshot.json` showed `"cash": null`, even day 1.
- **Date:** 2026-08-03
- **Symptom:** `ReplayRunner.last_account_snapshot()` returned a hardcoded
  `{"cash": None, ...}` whenever the historical broker's state file
  (`<data_root>/replay_state/<session_id>.json`) didn't exist yet — which
  is indistinguishable from "the read path is broken." A day with zero
  trades (the true, correct state) looked identical to a real failure.
- **Reproduction:** any day where `TradeTool` never successfully reaches
  `HistoricalFillBroker.submit_order()` (see below — this was every day in
  the actual run) leaves no state file, so the fallback always fires.
- **Severity:** minor for *this* run (nothing traded, so the "wrong" value
  and the "right" value coincidentally overlap in meaning) but real: it
  would have hidden an actual bug in the state-file path even on a run
  where trades did happen, since `null` gives no signal either way.
- **Root cause:** fallback literal `{"cash": None, ...}` never referenced
  `HistoricalFillBroker.DEFAULT_INITIAL_CASH` (100,000.0).
- **Fix applied:** `run_month_replay.py::last_account_snapshot()` now
  imports `DEFAULT_INITIAL_CASH` from `vinu_agent.broker.historical_broker`
  and returns it as `cash` (plus an explicit `"note"` field saying no trades
  have happened yet) instead of `None`.
- **Verification:** called the fixed method directly against a
  fresh/nonexistent state path — returns `{"cash": 100000.0, ...,
  "note": "no trades yet this session — untouched starting balance"}`.
- **Status:** fixed. Not re-run against the full month (see below for why).

### Verification results (2026-08-03) — `run-2026-07-06-2026-07-31`, superseded below
**Superseded by `run-2026-07-06-2026-07-31-v2` (see Bug-5 and the
"Verification results (2026-08-03) — v2 run" section further down) — that
run has the `get_features`/`get_news` data-path fixes this one didn't.
Kept here as the historical record of the pre-fix, zero-tool-calling-success
state.**

**P&L: $0.00.** The agent never placed a single trade across all 20
trading days (2026-07-06 → 2026-07-31, AAPL/TSLA/JNJ). Portfolio would
have sat at $100,000 cash the entire month had the fixed default existed
at run time (it reported `null` instead — see Bug-4).

- 20/20 days completed, `thinking.json`/`response.json`/`account_snapshot.json`
  written for every day, resumability confirmed (2026-07-31 was completed
  via a resumed/fresh session after an interruption — moot for P&L since no
  trades ever occurred in any session).
- **Root cause of zero trades, confirmed by direct transcript inspection**
  (not just narration — spot-checked `2026-07-24/thinking.json` and
  `2026-07-15/thinking.json` directly): the local `qwen36-35B` model
  reliably fails to pass required arguments on tool calls in this loop.
  Concrete evidence: `get_stock_price` called 3x in a row with `{}` empty
  arguments → `{"status":"error","error":"'symbol'"}` each time, ending in
  the model's own words: *"I keep making the same mistake - I'm not passing
  the `symbol` parameter."* On 2026-07-15, `submit_order` itself was
  actually invoked once — also with `{}` empty arguments, also erroring
  before ever reaching `TradeTool`'s broker logic.
- **This means `HistoricalFillBroker.submit_order()` (item 2) was never
  exercised by a real call during this run** — it only exists as
  code-reviewed + separately, directly verified (see
  `historical-fill-broker/test-log.md`'s "Verification results" section,
  added 2026-08-03, all checks passed). The zero-trade result is a genuine
  finding about *this model's* tool-calling reliability in this loop, not
  evidence the broker/harness infrastructure doesn't work.
- **Decision: did not re-run the full 20-day month** after the Bug-4 fix.
  Reasoning: the fix only changes what a *no-trade* day reports (null →
  100000.0); it doesn't touch anything that would change *whether* the
  model successfully calls a tool. Re-running would almost certainly
  reproduce the identical zero-trade outcome at real LLM-call cost (up to
  30 min/day × 20 days) for no new information. The broker logic itself
  was instead verified directly and cheaply (see historical-fill-broker's
  log) — that was the actual unverified risk, not the reporting default.
- **Open question this leaves for item 5 / future runs:** this replay
  cannot say anything about the agent's *trading* behavior (loss
  adaptation, risk discipline) because it never traded — item 5's
  behavioral rubric will have real transcript evidence for "does the agent
  reason sensibly when tools fail" but not for the originally-intended loss/
  risk-adaptation questions. A meaningful re-run of item 5's actual target
  questions requires either a more tool-call-reliable model or hardened
  tool-call prompting/schemas first — logged here as a prerequisite, not
  silently assumed away.

### Verification results (2026-08-03) — v2 run, with data-path fixes applied

Re-ran the full window as `run-2026-07-06-2026-07-31-v2` after the
`get_features`/`get_news` fixes (`../../FIXES-2026-08-03.md`). Result:
**$-46.58 (-0.05%)**, one real trade (100 shares AAPL bought 2026-07-08,
filled 2026-07-09 at $310.45, per the historical broker's T+1 discipline).

- 20/20 days completed, fully resumable, ~10 minutes wall-clock for the
  whole month (much faster than the up-to-30-min/day worst case).
- The agent genuinely used tools and reasoned over real data on days 1-3
  (`get_stock_price`, `get_features`, `get_fundamentals`, `submit_order` all
  fired with correct arguments — the Bug-1/Bug-2 schema fixes hold) and once
  more on day 07-13 (`get_portfolio`).
- **New finding: see Bug-5 below.** From 07-09 onward (minus 07-13), the
  agent stopped calling tools entirely and just paraphrased earlier answers
  from memory — meaning this run, too, can't fully answer item 5's original
  loss-adaptation questions, for a different reason than the first run
  (that one never traded at all; this one traded once, then went passive).
- `report.md` regenerated and matches the account ledger (`$99,953.42`
  ending equity, 1 trade) — see `report_month_replay.py` fix note below for
  why the "Day-by-Day Decisions" table's `action` column needed a fix to
  report this accurately.

### Bug-5 — after the day-3 trade, the agent stops calling tools for 16 of the remaining 17 days and repeats stale, self-contradictory portfolio numbers from memory
- **Found during:** post-run review of `run-2026-07-06-2026-07-31-v2` — the
  first full 20-day run made with Bug-1 through Bug-4 (this file) and the two
  `get_features`/`get_news` data-path fixes (`../../FIXES-2026-08-03.md`) all
  applied. This is the first run where the agent actually traded (1 real fill,
  2026-07-08 → 2026-07-09), so it's also the first run where this could be
  observed at all.
- **Date:** 2026-08-03
- **Symptom:** counted `role == "tool"` entries in each day's persisted
  `react_trace` directly (not narration):

  | day | tool calls | day | tool calls | day | tool calls |
  |---|---|---|---|---|---|
  | 07-06 | 5 | 07-15 | 0 | 07-24 | 0 |
  | 07-07 | 3 | 07-16 | 0 | 07-27 | 0 |
  | 07-08 | 8 | 07-17 | 0 | 07-28 | 0 |
  | 07-09 | 0 | 07-20 | 0 | 07-29 | 0 |
  | 07-10 | 0 | 07-21 | 0 | 07-30 | 0 |
  | 07-13 | 1 (`get_portfolio`) | 07-22 | 0 | 07-31 | 0 |
  | 07-14 | 0 | 07-23 | 0 | | |

  From 2026-07-09 onward the model's very first LLM turn each day returns
  final content with **no tool_calls**, so `AgentLoop.run` (`agent/loop.py:
  175-183`) treats it as a completed answer immediately — it never had the
  chance to call `get_portfolio`/`get_stock_price` fresh. Instead the model
  paraphrases the "Current Portfolio Status" answer it already gave on a
  previous day, which is sitting right there in conversation history (the
  session is reused all month per the plan's design, `run_month_replay.py:12-15`).
  Concrete evidence: 2026-07-14 through 2026-07-31 (12 consecutive days) all
  contain the byte-for-byte-identical block `Total Equity: $100,000.00 / Cash:
  $68,908.42 / Market Value: $31,045.00 / Unrealized P&L: -$46.58 (-0.15%)` —
  despite AAPL's actual close price moving throughout that window (confirmed
  via `get_stock_price` output already in the same transcript's early days).
  It's also internally self-contradictory: $100,000.00 "Total Equity" alongside
  a stated -$46.58 loss doesn't reconcile (should be $99,953.42, the real
  figure the agent *did* compute correctly, once, on 07-13 after actually
  calling `get_portfolio`).
- **Root cause (probable, not yet code-confirmed):** consistent with the
  already-known, previously-deprioritized issue in `../../FIXES-2026-08-03.md`
  ("agent stops mid-day at ~18-21 trace steps... tied to `max_tokens=4096` in
  the LLM server logs despite `VINU_LLM_MAX_TOKENS=8000`"). As the reused
  session's history grows (each day appends the full prior day's Q&A, un-
  truncated — messages fetched via `store.get_messages(session_id, limit=50)`
  in `session/service.py:187`), less of the fixed completion-token budget is
  left for a real tool-calling turn, so the model increasingly takes the
  cheapest path: answer directly from context instead of reasoning through a
  fresh tool call. This escalates the known issue from "runs out of budget
  mid-day" to "silently stops doing any real work for over two weeks
  straight" — worth re-classifying from "not a tool bug, tracked separately"
  to a real blocker for trusting any multi-week replay's behavioral signal.
- **Severity:** major — this is not a lookahead/guard leak (no future data
  was used), so it isn't a correctness bug in items 1/2. But it means 16 of
  20 simulated days produced no genuine decision-making to evaluate, which
  directly undercuts item 5's original goal (loss adaptation, risk-tier
  awareness over a full month).
- **Status:** logged, not fixed here. Documented as a known, now-quantified
  limitation for item 5 to work around rather than silently trust. Candidate
  fixes for a future run (not attempted this pass): (a) actually raise
  `VINU_LLM_MAX_TOKENS` server-side to the already-configured 8000 and
  confirm it takes effect, (b) add an explicit system reminder each day
  instructing the agent to re-call `get_portfolio`/`get_stock_price` even if
  it "remembers" yesterday's numbers, (c) summarize/compact prior days'
  turns instead of keeping them verbatim in history so budget doesn't shrink
  every day.

### Also fixed in this pass — `_parse_action`'s "sell" word list matched "closing price" as a close-position order
- **Found during:** the same v2-run review; the "Day-by-Day Decisions" table
  in `report_month_replay.py`'s output showed `action: trade` on almost
  every day, including pure status-report days with zero tool calls.
- **Date:** 2026-08-03
- **Root cause:** `run_month_replay.py::_parse_action`'s sell-word regex was
  `\b(sell|selling|close|exit|reduce)\b` — bare `close` matches ordinary
  phrases like *"Latest close: 308.43"* (a stock's closing price), not an
  intent to close a position.
- **Fix applied:** tightened both the buy and sell regexes to require an
  actual trade phrase (`bought`, `submitted a buy`, `close the position`,
  `exit the position`, etc.) instead of a single loose keyword; also
  tightened the `qty` regex to require the number be immediately followed
  by "shares" (it was previously matching bare numbers including the `2026`
  in "as of 2026-07-09").
- **Verification:** regenerated all 20 days' `response.json` summaries from
  the already-captured `final_content` (no LLM re-run needed) and rebuilt
  `report.md` — now shows exactly 1 `trade` day (2026-07-08, the real
  `submit_order` call), the other 19 correctly `none`.
- **Status:** fixed. Note this only affects the report's narrative label,
  never the P&L/trade-log numbers — those always came from the broker's real
  ledger (`account_snapshot.json`), never from this text parse.

_More entries as implementation proceeds._
