# Chain run: problems found, how each was fixed, and what is still left to do

Living log of the real run (Alpaca paper, equities only). Chain under test:
screener top 10 -> initial analysis -> planner -> research + simulation -> gate (risk, confidence) -> paper order.

Rule for every entry: **Fixed** means the cause is removed and a guard test or script stops it coming back. **Left to do** is anything that still needs a person, a setting, data, or a later change. Nothing is marked fixed that was not re-checked.

Last updated: 2026-10-05.

---

## A. Fixed (cause removed, guard in place)

| # | Problem found | Fix | Guard | Left to do |
|---|---|---|---|---|
| 1 | The simulator's HTTP 422 ("No weight data generated", the candidate's code produced nothing) was labelled an infrastructure fault and stopped the whole research run. | A 422 is now a candidate failure the loop replaces. 401, 403 and 5xx stay infrastructure. (`vinu-research/vinu_research/tools.py`) | `vinu-research/tests/test_simulator_422_is_a_candidate_failure.py` | none |
| 2 | One bad candidate (4xx) tripped the circuit breaker, which then silenced the service for every later call. | The breaker ignores 4xx and only counts 5xx and connection errors. (`vinu-infra/client.py`) | `vinu-infra/tests/test_breaker_ignores_client_errors.py` | none |
| 3 | The LLM sometimes returned JSON with raw newlines inside strings, which failed to parse. | `json.loads(text, strict=False)` in both LLM clients. | `vinu-infra/tests/test_llm_json_with_raw_newlines.py` | none |
| 4 | The screener could only rank the 8 tickers in the price store, not its universe of 50. | `scripts/sync_universe.py` adds the missing tickers to the watchlist and backfills. Price store now holds 50. | the script's `--status` mode shows universe vs store | Re-run the script whenever a ranker universe changes. |
| 5 | The screener's batch fetch used a fixed 30 s timeout; 50 symbols need about 38 s, so the ranker got zero candidates. | Chunks of 20 symbols, timeout `30 + 3 s * symbols`. (`vinu-screener/.../scan/data_source.py`) | `tests/test_data_source.py` (timeout test) | none |
| 6 | Every ticker was flagged "stale" every Monday and lost 10 points, which buried the real scores. | Staleness counts business days (`numpy.busday_count`). (`rankers/runner.py`) | `tests/test_stale_data_counts_business_days.py` | none |
| 7 | The planner had no ranker ID configured, so it cycled on nothing. | `VINU_AGENT_SCREENER_RANKER_ID=core_starter` and `VINU_AGENT_SCREENER_TOP_N=10` in `.env` and `.env-example`. | `test_the_planner_is_pointed_at_a_screener_ranker_and_takes_the_top_ten` | none |
| 8 | The local LLM context (16K) was too small for the agent teams. | 40K context, saved in `.env` and `.env-example`. VRAM 6.6 of 8.1 GB. | `test_the_local_llm_context_is_big_enough_for_the_agent_teams` | If the GPU or the model changes, re-check the context against VRAM. |
| 9 | One angle tool returned 9.7 MB (META cluster F) in one prompt; the biggest logged call was 2.4M tokens. | Angle tools keep the newest rows and report the true count; the agent loop caps any tool result at 100K characters. | `test_angle_tools_bound_their_output.py`, `test_tool_result_cap.py` | The cap truncates; if a team needs more rows, it must ask for them in steps. |
| 10 | A config test read my local `.env`, so it passed or failed by machine. | Made hermetic. | `vinu-agent/tests/test_config.py::test_defaults_to_false` | none |
| 11 | **The research team looped for 2.5 hours (389 LLM calls) without reaching a backtest.** The agent loop compacts its memory when the estimated context reaches `max_context_tokens`. llama.cpp reports the live context size at `data[0].meta.n_ctx`; the resolver only read top-level fields, so the 40192-token model resolved to the 8000 fallback with no clear error. The loop compacted nearly every step, the agent forgot what it had fetched, and it fetched it again. | `resolve_context_window` also reads `meta`, and logs a warning when `/models` answers without any context size. Verified inside the container: resolves to 40192. (`vinu-agent/vinu_agent/agent/llm.py`) | `vinu-agent/tests/test_context_window_from_llamacpp_meta.py` | A run with no time or call budget can still run long; see B2. |
| 12 | A finished screener bootstrap that stored no summary was logged as "bootstrapped new tickers" (TSLA: full analysis, but the cross-cluster analyst timed out so there was no JSON block, nothing stored, no log). | Bootstrap counts a ticker only if a summary row exists afterwards, and logs the miss; the writer warns when there is no JSON block. The ticker stays new and is retried next cycle. | `vinu-agent/tests/test_bootstrap_counts_only_stored_summaries.py` | The cross-cluster analyst still times out on some tickers (B1). |
| 13 | Three tickers bootstrapped in parallel made the local LLM answer "Context size has been exceeded" on 14K to 17K-token prompts. The server had 4 slots sharing one 40,192-token pool (`kv_unified`), so concurrent big prompts overflowed it. | `LLAMA_ARG_N_PARALLEL=1` (compose `HINDSIGHT_LLM_PARALLEL`, default 1): one slot, full 40K, extra requests queue. Verified in the server log: `n_slots = 1, n_ctx_slot = 40192`. | `test_the_local_llm_runs_one_slot_so_concurrent_prompts_queue_instead_of_overflowing` | Calls now queue, so total time per cycle grows with the number of tickers; see B2 (per-ticker time limit). If the GPU or model changes, re-check slots against VRAM. |
| 14 | The planner and significance workers died at startup with `sqlite3.OperationalError: disk I/O error` on the summary store (twice), and the planner then waited its full 30 minutes. A host-side poller I was running was reading the same WAL database across the Windows/Linux bind mount; the file itself was healthy (4 rows, `integrity_check` ok, after a WAL checkpoint with the container stopped). Stopping the poller made the container open the file normally. Cause is strongly suggested, not proven in isolation. | Recovered with a backup, then a WAL checkpoint from the host with the container stopped. New `scripts/stack_db.py` reads a store from inside the container. Rule added to the project memory: never read stack databases from the host while it runs. | `scripts/stack_db.py` (the only supported way to peek) | A transient I/O error on startup still costs a whole 30-minute planner cycle: the worker should retry sooner (B2). The earlier "readonly database" warnings in the reflection stores may be the same cause; not re-checked. |
| 15 | Most cluster reads were cut off: a sub-agent delegation has a 60-second ceiling (`VINU_AGENT_TOOL_TIMEOUT`), one cluster read takes about 30 s on the local 9B model and longer when it queues. META's stored summary said 6 of 7 clusters "timed out" and had 0 angles with data. | `VINU_AGENT_TOOL_TIMEOUT=900` and `VINU_AGENT_SUMMARY_PARALLELISM=1` (one ticker at a time; parallel tickers only queue on one LLM slot). META's junk row was deleted so it is bootstrapped again. | `test_a_sub_agent_delegation_may_outlast_several_slow_local_llm_calls` | The 900 s ceiling is generous on purpose; a delegation that hangs would now block for up to 15 minutes (B2: per-ticker budget). |
| 16 | The RSI recipe crashed for every symbol (MSFT, NVDA, all dates). It read a stored column named from the period, and the grid sends the period as a float, so it asked for `rsi_14.0`. The simulator then reported 'No weight data generated', which hid the crash. The research team saw 'all 12 grid points failed' and moved on. | Recipe now computes RSI from the close price, so any period works. The simulator names the crash when every symbol crashes. | `vinu-research/tests/test_every_recipe_runs_on_plain_ohlcv.py` (every recipe, float params, plain OHLCV); `test_custom_sim.py::test_every_symbol_crashing_names_the_crash_not_empty_data`. Commit 95a88dc5. | Only RSI was affected. Other recipes compute from price. |
| 17 | Walk-forward never ran in the real chain. Neither the `/sweep/grid` route nor the agent's tool passed a config into `run_sweep_grid`, so the overfitting check was skipped and every result said 'no walk-forward evidence'. | `run_sweep_grid` uses the config its tools carry when none is passed. | `test_sweep_grid.py::test_walk_forward_runs_when_the_caller_passes_no_config`. | None. |
| 18 | Once walk-forward ran, every window failed. A failed or empty candle fetch was cached with no expiry, and 12 identical candle requests ran at once (4 grid points x 3 windows), which made the stock API time out and reset connections. | Failed or partial fetches are never cached, and the swallowed error is logged. Identical concurrent requests share one fetch. | `test_price_client.py::test_a_failed_fetch_is_not_cached...`; `test_service.py::test_identical_concurrent_requests_share_one_fetch` and `test_a_failed_fetch_is_not_cached`. | The stock API is still slow under load. Not investigated. |
| 19 | META and TXN summaries were missing or empty. | Fixes 11 to 15 (summary stored only when it has content, one ticker at a time, 900 s delegation timeout). Checked at 00:40 UTC on 2026-10-06: all 10 summaries stored, 15 of 27 angles each. | The tests behind fixes 11 to 15. | 15 of 27 is the ceiling without the dormant models container. |

## B. Found, not fixed yet (the chain is stopped here)

### B1. RESOLVED 2026-10-06: all 10 summaries stored (see fix 19). Original finding: the planner stored only 4 of the top 10 summaries, and 2 of the 4 were empty

Top 10 from the screener: AMD, META, ACN, QCOM, TXN, NVDA, MSFT, CRM, CAT, TSLA.
`ticker_summaries.db` holds: AMD, QCOM, ACN, TXN.

- **QCOM and TXN:** every cluster reports 0 angles with data. Initial analysis has not produced angle data for them, so the summary is a "no data" note, not an analysis.
- **AMD:** summary says the cross-cluster step timed out. **ACN:** 5 of 7 clusters had data.
- **META, NVDA, MSFT, CRM, CAT, TSLA:** no summary stored; the bootstrap run logged only "bootstrapped new tickers" at 02:08 UTC.

Open questions to settle, in order:
1. Does initial analysis run for a ticker before the planner bootstraps it, or does the planner assume the data exists? If it assumes, the planner needs an "analysis ready" check (or must trigger the backfill) before it calls the screener team.
2. Why did 6 tickers get no row? (a per-cycle limit, a timeout, or a failure with no log line)
3. Why did the cross-cluster step time out on AMD?

What the run log showed (team_runs.db, 2026-10-05):
- META, NVDA, MSFT, CRM, CAT: bootstrap **failed** ("LLM call failed after 3 attempts") while the LLM was being restarted and while the 16K/oversize-prompt faults were still live. They have not been retried because the planner cycle was stuck on the ACN research run (fault 11). They are retried when the next cycle starts.
- TSLA: bootstrap finished with a real analysis but stored nothing (fault 12, fixed).
- Summary refreshes took 30 to 100 minutes per ticker (AMD 31 min, ACN 103 min). The single local LLM slot serves every team in turn, at about 53 tokens/s and 15 to 26 s per call; one slow team delays all the others.
- Open: QCOM and TXN hold "0 angles with data" summaries. Whether initial analysis has angle data for them is still to be checked; the planner does not wait for analysis before it bootstraps.

**Status: open.** A summary with 0 angles must not be treated as a finished analysis.

### B3. Partly open: what starts initial analysis for a new top-10 ticker (TXN now has 15 angles, so a run exists; the trigger is still unidentified)

Initial-analysis runs exist for 9 of the 10 tickers (computed 06:53 to 07:06 UTC today, while the planner was bootstrapping), but TXN has none (`latest-run` returns 404). Fetching a missing run returns `not_found`; it does not compute one. The caller that creates the runs has not been identified. Until it is, "screener top 10 -> initial analysis" is a hope, not a verified link: a new ticker with no run gets an empty summary. Needs: find the trigger, or add an explicit one (the planner, before it bootstraps a ticker, checks `latest-run` and calls `POST /analysis/run/{ticker}` when it is missing).

12 of the 27 angles never have data because they need the models container (`models-api`), which is dormant by design. Summaries show `angles_with_data` of about 14 to 15 of 27 because of that, not because of a fault.

### B2. Other known gaps

- A planner or significance worker that fails on startup (any exception) sleeps its whole interval before trying again. It should retry after a short delay, and the connection panel should show a worker that last failed.

- A research or screener team run has no wall-clock budget that stops it from the outside. After fix 11 it should finish by itself, but a stuck run still blocks the whole planner cycle (the cycle is serial). Needs a per-ticker time limit so one ticker cannot hold up the other nine.
- `research-api` logs a 404 every 10 s for `GET /health` on quant-core, features and initial-analysis; their health path or the probe is wrong. Noise now, but it hides real health information.
- The LLM can still receive a prompt over 40K tokens (it did at 02:33, "Context size has been exceeded"); the loop's compaction should prevent it now that it knows the real size. Re-check the log.

- No strategy has passed the promotion bar yet. GOOGL and AMZN failed on merit (costs ate the edge, or no edge). AAPL, MSFT and META need a re-run on the fixed stack. **The promotion bar stays where it is.**
- All five YAML live-decision strategies were rejected by the system's own tests (15m and 1h losing; 4h and daily not statistically significant). The live gate stays closed until a strategy is validated.
- No paper order has been placed. The paper-order test (injecting an EXECUTE row and forcing `/live/cycle`) was denied by the permission classifier. It needs a permission rule from the user, a natural trigger, or a manual paper order.
- Failure verdicts are not yet fed back to the idea generator. `diagnose_across` across tickers has not been run.
- The reflection stores show "readonly database" warnings, and the `reflection.synthesis->agent.idea_generator` edge has not been checked.
- Orders: cold-start capital scaling and whole shares can make tiny orders vanish; fractional shares and Alpaca minimums are unchecked.
- The strategy validation only tests the entry setup. Only sma, ema, rsi, adx and dist_from conditions are testable.
- The models-connection edges show `missing` by design (the models container is dormant).

## C. Dependencies and instructions for whoever continues

1. **Rotate the API keys** that were pasted into the chat earlier. Keys belong only in `vinu-components/secrets/` as files, never in `.env` or chat. Alpaca stays paper.
2. **Do not start the models container** (`models-api`). It stays dormant.
3. **Re-run `python scripts/sync_universe.py --status`** after any change to a ranker's universe.
4. **Local LLM** (hindsight-llm, port 8092, Qwen3.5-9B) must be up for the screener, research and live-decision teams. If it restarts, calls return 503 for a while; that is transient, not a code fault.
5. **Do not lower the promotion bar** to make a strategy pass. If research returns `no_strategy_found`, that is a valid answer; read the failure diagnosis it prints.
6. **Check the connection panel** (`GET /research/pipeline-edges`) after each change. It shows which hand-offs actually flowed.
7. Pre-existing failures unrelated to this work: 3 `test_shadow_evaluator_real_endpoint` errors in vinu-live; `test_empty_meanings` and a flaky `test_concurrent_writes` in research; about 16 failures and 2 errors in the agent tests from a missing `openai` package; collection errors in initial-analysis.

## D. Verified chain links

| Link | State |
|---|---|
| Screener -> top 10 | Works. |
| Screener top 10 -> planner | Wired and guarded. |
| Planner -> bootstrap summaries | **Works one ticker at a time after fixes 11 to 15: NVDA stored with 14 of 27 angles (7.6 min). Others in progress; summary list is in the next update.** |
| Planner triage -> research team | Reached (ACN). It looped without a backtest; cause fixed (11); re-run pending. |
| Research and simulation -> gate (risk, confidence) | Not yet reached. |
| Gate -> paper order | Not yet reached; blocked on permission (B2). |


## E. First research results on the fixed stack (2026-10-06)

Walk-forward now runs. On MSFT, RSI recipe, 2022-01-03 to 2026-09-01, 4-point grid: PBO 0.52, walk-forward verdict FAILED (Sharpe gap 1.06 over the 0.50 threshold; only 33% of out-of-sample windows positive). The system correctly refuses this strategy and says why.

Still open from the research stage:
- Failure reasons do not demonstrably reach the idea generator (check `idea_generator/prompt.md` and the manager prompt).
- `FACT-AUDIT FAIL` warnings on percentage claims in agent text (about 100 per hour). Unknown whether the LLM invents numbers or the checker mis-parses.
- Research runs end with 'maximum number of iterations' instead of a clean stop.
- No strategy has passed the promotion bar; no paper order yet.
