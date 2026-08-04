---
name: e2e-complete-status
status: step-05-complete-agent-decision-loop-needs-fixing
purpose: single source of truth for what was actually checked/verified across the real end-to-end test run (01-05), and every real problem hit along the way — not a plan, a record of what happened.
---

# End-to-End Test — Complete Status

Covers the real run against the live Docker stack (`vinu-components`, 10
services), tickers AAPL/TSLA/JNJ, window 2022-01-01 → 2026-06-30 for
data/research/simulation, and a full real 22-trading-day agent replay for
June 2026. Every bug referenced here has its own detailed file in
[`end-to-end-test/bugs-fixes-while-test/`](end-to-end-test/bugs-fixes-while-test/AGENTS.md)
— this file is the rollup.

## 1. What was checked and verified

### Step 01 — Stack up, all services healthy
All 10 containers (`vinu-news`, `vinu-stock-price`, `vinu-tools`,
`vinu-initial-analysis`, `vinu-strategy`, `vinu-simulator`, `vinu-agent`,
`vinu-research`, `vinu-portfolio`, `vinu-live`) built and confirmed
`healthy` via `docker compose ps` and each service's own health endpoint.
Local LLM confirmed reachable and serving before anything else was
triggered: `qwen36-35B`, a real 34.66B-parameter model
(`llama.cpp`/GGUF, 22.1 GB on disk), at `http://host.docker.internal:8009`,
**32,000-token context window** (`n_ctx: 32000` — this number matters a
lot later, see §2).

### Step 02 — Data backfill (news, stock price, features, initial-analysis)
Triggered and verified real backfill for AAPL/TSLA/JNJ across the full
window:
- News and stock-price bulk backfill actually populated data (after fixing
  the watchlist-sync gap, see §2) — verified via direct row/record counts,
  not just "200 OK".
- FinBERT sentiment scoring run manually (confirmed not automatic — a real
  gap, documented, not fixed this pass since it's a scope decision, not a
  bug).
- `vinu-initial-analysis` angles run for all 3 tickers, including
  `news_price_causality`, after fixing the quadratic performance blowup
  (see §2) — verified against real production data volumes (AAPL:
  435,330 candles, 9,079 articles).

### Step 03 — Strategy research and simulation
For all 3 tickers:
- `POST /research/run` executed the real generate → backtest → validate
  pipeline (real LLM calls, not `dry_run`).
- Each run explicitly approved via `POST /research/runs/{run_id}/approve`
  (confirmed this is NOT automatic — a real, documented gap in the
  original checklist, fixed).
- Confirmed real, non-degenerate backtest metrics per ticker via
  `POST /simulator/simulate/custom` (the correct route for a
  research-generated strategy — `POST /simulator/simulate` cannot work for
  these, see §2):

| Ticker | Total Return | Sharpe | Max Drawdown | Trade Count | Equity Points |
|---|---|---|---|---|---|
| AAPL | −3.89% | −0.32 | −6.66% | 143 | 1,124 |
| TSLA | +8.44% | 0.21 | −16.83% | 380 | 1,124 |
| JNJ | −0.08% | −0.018 | −1.89% | 71 | 1,123 |

Equity points (1,123-1,124) confirmed the full 2022-01 → 2026-06 range was
actually covered, not a partial/truncated run. Monte Carlo validation ran
for all 3 (p-values recorded per ticker).

### Step 04 — Portfolio/strategy verification
Confirmed `vinu-strategy` and `vinu-portfolio` correctly reflect what
Step 03 produced, and confirmed the structural gap that `vinu-strategy`
(a YAML rule engine) has zero awareness of `vinu-research` artifacts —
already known project-wide, concretely re-confirmed here.

### Step 05 — One-month live agent replay (2026-06-01 → 2026-06-30, 22 trading days)
Ran the real day-stepper harness (`run_month_replay.py`) against the live
`vinu-agent` HTTP API, one simulated trading day at a time, one continuous
session (`5466372e1212`) across the whole month, real `POST
/agent/sessions/{id}/messages` calls — not a simulation of the agent, the
actual API a real cron job would hit.

- **All 22 of 22 trading days completed** (took 3 invocations total — see
  §2 for why it crashed twice before finishing).
- **Verified per-day output directly against the raw tool-call trace**
  (`thinking.json`), not just the harness's own parsed summary, because
  the summary turned out to be unreliable (§2).
- **Real result: the agent placed zero trades across the entire month.**
  Full inventory of every tool call made all 22 days: `get_stock_price`
  (60×), `get_fundamentals` (41×), `get_news` (33×), `get_features` (30×),
  `get_portfolio` (21×), `compact` (5×). No trade-execution tool
  (`trade_tool.py`/`trade_plan_tool.py` — both exist in the codebase) was
  ever called. Account state confirms this independently: every single
  day's `account_snapshot.json`, including the final day, shows
  `cash: 100000.0`, `positions: {}`, `ledger: []` — completely untouched.
  **P&L for the month: $0.00 for AAPL, TSLA, and JNJ — flat, because no
  trades happened, not because of a profitable/losing strategy.**
- This is separate from and not comparable to the Step 03 backtest table
  above — that's the generated strategy's own historical backtest
  performance; this is what the live agent actually did, which was
  nothing.

## 2. Problems faced — full detail, root causes where known

### 2.1 The core problem: the agent never completed a real trading decision, likely a context/tokenizer mismatch

This is the most important finding of the whole test. Digging into *why*
the agent placed zero trades across 22 days surfaced a real, specific,
verifiable root-cause candidate in `vinu_agent/agent/loop.py`:

- **The agent's own context-management logic uses a hardcoded budget of
  `max_tokens = 128000`** (`loop.py:305`) to decide when to
  compact/microcompact the conversation history.
- **The actual backing LLM's real context window is 32,000 tokens**
  (confirmed directly from the model server: `curl
  http://localhost:8009/v1/models` → `"n_ctx": 32000"`, for `qwen36-35B`).
- That's a **4x mismatch** — the agent's internal safety net doesn't even
  start compacting until it estimates it's used 128K tokens, by which
  point the real 32K-token model has already been sent a request 4x over
  its actual limit.
- Worse, **the token estimate itself is not a real tokenizer** — it's a
  flat character-count heuristic: `_estimate_tokens(text) = len(text) / 4.0`
  (`loop.py:28-32`). No `tiktoken`, no model-native tokenizer, nothing
  that accounts for how JSON tool-call payloads, ticker symbols, numbers,
  and news text actually tokenize. Even if the 128K threshold were fixed
  to 32K, this estimate could still be meaningfully wrong in either
  direction.
- **This is directly, not speculatively, connected to a real observed
  failure**: day 2026-06-29's trace ends with `LLM call failed at
  iteration 2: OpenAI LLM call failed after retries: Error code: 500 -
  {'error': {'code': 500, 'message': 'Context size has been exceeded.',
  'type': 'server_error'}}` — the exact failure mode this mismatch
  predicts, on the exact kind of day (late in the month, session history
  fully accumulated) where it would first bite.
- **This needs a real tokenizer implemented** — matching whatever
  tokenizer `qwen36-35B` actually uses (not a generic 4-chars/token
  guess), and the `max_tokens` constant needs to be sourced from the
  model's real `n_ctx` (currently hardcoded, not read from config or the
  `/v1/models` endpoint anywhere in the codebase — grepped for
  `128000`/`32000`/`n_ctx`/`context_window` across `vinu_agent/`, found
  only the one hardcoded `128000` literal).

### 2.2 The ReAct loop frequently ends without a final decision
13 of the 22 days' full traces end on a bare tool-result step — no final
assistant synthesis message at all that day, meaning whatever decision
process was happening got cut off mid-cycle. `max_iterations` defaults to
50 (`loop.py:42`); trace step counts grew from 10 (day 1) to 60 (day 30),
so raw iteration count alone likely wasn't always the limiter — more
likely a mix of this and the LLM-call failures below compounding across a
session that never resets its history.

### 2.3 Repeated real backend/LLM call failures during the replay
Pulled directly from the day-by-day reasoning text, not paraphrased:
- `2026-06-02`: "Fundamentals calls for TSLA and JNJ errored."
- `2026-06-05`: "Technical indicators API failed."
- `2026-06-09`: "Technical indicators failed."
- `2026-06-18`: "LLM call failed at iteration 3: OpenAI LLM call failed
  after retries: Request timed out."
- `2026-06-23`: "Fundamentals calls had an error."
- `2026-06-24`: "Both fundamentals and features APIs are failing."
- `2026-06-25`: "Features API is down."
- `2026-06-29`: context-size-exceeded failure, see §2.1.
- `2026-06-30`: "Fundamentals calls had an error."

That's real intermittent flakiness in `features-api`/fundamentals calls on
**9 of 22 days (41%)** — not a one-off, a recurring pattern across the
month, each occurrence forcing the agent to retry/recompute manually
("let me compute technicals manually from the price data"), burning
iterations and context on recovery instead of decision-making.

### 2.4 Per-day LLM latency — real, structural, not a bug
Each trading day is one continuous agent turn, and the local 35B model on
local hardware (not a hosted API) takes real wall-clock time per call:
day 1 (a single LLM round trip) took ~4 minutes; later days with more
tool-calling rounds and larger accumulated context took 10-20+ minutes
each. This is expected given the model/hardware, not something "wrong,"
but it's why a 22-day replay takes hours, not minutes, and needs to be
accounted for in any future run's time budget.

### 2.5 `run_month_replay.py` crashed twice before finishing (harness bugs, both handled)
1. **Poll-timeout crash** — the harness's own lightweight status-poll
   request had an unrelated hardcoded 30s timeout with no retry; a single
   slow poll (while `agent-api` was busy on the real LLM call) killed the
   whole 22-day run after only 4 days completed. Made worse by the
   background task runner reporting a false `exit code 0`, because the
   script's output had been piped through `tail`, which swallowed the
   real Python crash. **Fixed**: wrapped the poll request in a
   try/except that retries transient failures instead of crashing, and
   stopped piping through `tail` for subsequent runs so exit codes are
   trustworthy. Full detail:
   [`replay-harness-poll-timeout-crash.md`](end-to-end-test/bugs-fixes-while-test/replay-harness-poll-timeout-crash.md).
2. **`agent-api` container restart mid-attempt** — after the fix above,
   the run failed once more at day 10: `agent-api` cleanly restarted
   (`ExitCode=0`, `OOMKilled=false`, `docker stats` showed trivial memory
   use at 89MiB/2GiB — ruled out as a resource issue) mid-way through an
   LLM call, losing that day's in-flight attempt and dooming the poll to
   the full 30-minute timeout before the harness gave up. Root cause of
   *why* the container restarted was not pinned down. **Not fixed at the
   code level** — the harness's existing resume-by-skip design already
   recovers for free on the next invocation (the incomplete day's
   `response.json` was never written, so it's retried fresh, not skipped).
   Full detail:
   [`agent-api-container-restart-mid-attempt.md`](end-to-end-test/bugs-fixes-while-test/agent-api-container-restart-mid-attempt.md).

### 2.6 The harness's own "final decision" parsing is unreliable
`write_day()` picks the last assistant-role message with non-empty
content, scanning backward through the trace. When the real final
decision never arrived (see §2.2), this silently falls back to an
**earlier planning message** ("Let me gather fundamentals, news...") and
presents it as if it were the day's conclusion. Every one of the 22
`response.json` summaries said `"action": "none"`, and most looked like
legitimate "no trade today" outcomes at a glance — only a full scan of the
raw tool-call trace revealed that many of those weren't real decisions at
all. Documented in
[`replay-agent-never-executed-a-trade.md`](end-to-end-test/bugs-fixes-while-test/replay-agent-never-executed-a-trade.md).

### 2.7 Infra bugs found before/while bringing the stack up (Steps 01-04)
All individually documented, one file each, in
[`bugs-fixes-while-test/`](end-to-end-test/bugs-fixes-while-test/AGENTS.md):
- CRLF line endings on all 7 `entrypoint.sh` files (Windows checkout, no
  `.gitattributes`) crash-looped every container using one — fixed.
- Shared `.env`/`.env-example` data-root variables were relative,
  host-mode paths, landing on the container's read-only root filesystem
  instead of the mounted `/data` volume — blocked 6 of 10 services —
  fixed.
- `VINU_SHARED_WATCHLIST_PATH` unset — bulk backfill silently processed
  zero tickers and reported `done` — fixed.
- FinBERT scoring is manual-only, nothing in the runbook calls it —
  documented, run manually, not fixed (scope decision).
- `news_price_causality` quadratic blowup — rebuilt/re-sorted its full
  candle/market-benchmark index per article instead of once per symbol;
  never finished for real AAPL/TSLA article volume. Fixed and benchmarked:
  **304.8x speedup** on real production data (40.34s → 0.13s per 300
  articles).
- `POST /research/run` crashed on `"user_idea": null"` (the exact payload
  the checklist documents) — the auto-propose fallback only existed on
  the sibling `/research/ensure` route — fixed, regression tests added.
- `HypothesisRegistry()` crashed on every real research call — its default
  path used `Path.home()`, non-writable/nonexistent in the read-only
  container — fixed via a `VINU_RESEARCH_DATA_ROOT`-aware default.
- The documented `/simulator/simulate` route (by `strategy_name`) can
  never work for a research-promoted strategy — structural, not a race
  condition, since `vinu-strategy` has zero awareness of research
  artifacts. Fixed in the docs: use `/simulator/simulate/custom` with the
  approved run's own `strategy_code`.

## 3. What still needs doing (priority order)

1. **Implement a real tokenizer for `vinu-agent`**, matching
   `qwen36-35B`'s actual tokenizer, replacing the flat
   `len(text)/4` character-count heuristic in
   `vinu_agent/agent/loop.py::_estimate_tokens`.
2. **Fix the `max_tokens = 128000` hardcoded constant** in
   `loop.py:305` to reflect the real deployed model's context window
   (32,000 for `qwen36-35B`) — ideally sourced from config or queried from
   the LLM server's own `/v1/models` response rather than hardcoded at
   all, so it stays correct if the model is swapped.
3. **Investigate why 13/22 days ended the ReAct loop without a final
   decision** — separate from the context-size issue, since several of
   those days didn't show a context-exceeded error, meaning there's
   likely a second contributing cause (iteration budget, tool-call error
   handling, or something else) still to isolate.
4. **Investigate the real cause of the `agent-api` container restart**
   (§2.5.2) — ruled out OOM, root cause still unknown; worth checking
   Docker Desktop/WSL2-level logs if it recurs.
5. **Investigate the recurring `features-api`/fundamentals flakiness**
   (§2.3, 9/22 days) — a real, moderately frequent failure independent of
   the LLM/context issues.
6. Once the above are fixed, **re-run the one-month replay** and confirm
   the agent actually reaches, and executes on, real trade decisions
   before re-attempting the full 8-question ritual verification
   (`05-one-month-agent-verification.md`) — that verification can't
   meaningfully complete against a month where no trades occurred.
