# 04. Pipeline checkpoints: the plan for review (2026-10-07)

Written as a system designer would: every step has an entry check, an exit check, a decider (code or LLM), a recorded reason, and a path back. Status is what I verified in the code and the running stack, not what the design says.

## Principles

1. **The AI proposes. Code decides.** The LLM writes strategies and explains results. Whether a strategy is promoted is decided by deterministic checks on stored numbers, never by the LLM's own words.
2. **Numbers come from records, not text.** Sharpe, drawdown, deflated Sharpe, holdout, stress, PBO are read from the stored backtest and validation records. A figure typed by an LLM is never evidence.
3. **Fail closed.** Missing data, a missing number, or a check that did not run is a rejection with a reason, never a pass.
4. **Every rejection carries a reason that goes back** to the writer (retry) or to the operator (log).
5. **One strategy, every bar size.** A strategy is tested on 15m, 1h, 4h and 1d with the same code. Promotion is per bar size, and the approved strategy records the bar size it passed on.
6. **The promotion bar is never lowered to get a result.** If nothing passes, widen the candidates, not the bar.
7. **One source of truth per fact**, and every stage writes what it did, so a run can be replayed and audited.

## The pipeline, checkpoint by checkpoint

| # | Step | Checkpoint (what is checked) | Decided by | On failure | Status |
|---|---|---|---|---|---|
| D0 | **Data readiness** (before anything) | Per ticker and per bar size: bars fresh to the last close; no truncated response; no unexplained gaps; enough history for the window | code | skip that ticker or bar size, record why | **Partly.** Truncation is now flagged and followed. No single readiness gate that blocks a run on stale or thin data. |
| 1 | Screener top 10 | Ranker snapshot fresh; flags for stale or degraded data; held names handled | code | use the last good list, log it | Built; verified top 10 flows to the planner. |
| 2 | Initial analysis | Angle values checked against an independent calculation; angles with too few observations marked `insufficient_data`, not silently zero; window ends at the latest complete bar; summary written only when enough angles have data | code | ticker not "ready", retried next cycle | Built; Sharpe, drawdown, returns verified for 10 tickers. Window ends Oct 1 (stale), news history thin, model angles off by design. |
| 3 | **Strategy intake** (all three sources) | Normalise to one definition: code, parameters, bar sizes, source, rationale. Then: safe-code check; output contract (one weight per bar); only real indicators; runs on a sample | code | reject with the exact reason to the writer | **Partly.** Contract check and safe-code check built today and live. Indicator-name check missing (the AI invented names). The ready-made and user-added sources are not normalised the same way. |
| 4 | **Backtest on all bar sizes** | Same code on 15m, 1h, 4h, 1d; full history loaded; costs and delay applied; minimum number of trades; no look-ahead | code | per-bar-size reason back to the writer | **Missing as designed.** Bar size flows through the tools now, but runs are separate per bar size, not one strategy across all four. |
| 5 | Optimise | Parameter grid per bar size; walk-forward on later windows; overfitting estimate (PBO); completeness of the grid | code | reasons back to the writer | Built; works (a 16-point sweep ran, PBO 0.30). |
| 6 | **Statistical bar** | Deflated Sharpe, out-of-sample holdout, stress windows, PBO, minimum trades, correlation to the existing book, all computed from stored records | **code only** | structured reasons to the writer | **The gap.** The code exists, but the AI path never fills the numbers it needs. Nothing from the AI path can pass. |
| 7 | Review by the risk critic | Explains the results; may add concerns; **cannot override step 6** | LLM (advisory) | reasons to the writer | Built; today it decides PASS or STOP. Needs demoting to advisory. |
| 8 | Retry loop | At least 3 distinct attempts, each fed the previous failure reasons; real budget; every stop reason stored | code | after the budget: STOP with all reasons | Built today (minimum 3 attempts, false-PASS fix, no early quit). |
| 9 | Approved candidate | Saved with source, run ids, code hash, bar size, and numbers copied from the records | code | none | **Partly.** Saved, but the bar size is lost and the numbers are the AI's text. |
| 10 | Risk gatekeeper | Limits: drawdown, exposure, liquidity, concentration, correlation | code limits, then LLM review | stays at bench | Built; never exercised. |
| 11 | Capital allocator | Size by formula; kill switch; re-check step 6 | code | stays pending | Built; never exercised. The step 6 check is correct but starved of data. |
| 12 | Paper trading | Order guard (only an active strategy); mandate limits; plans per ticker and bar size; fills reconciled against the broker | code | order refused, logged | Built; never exercised. |
| 13 | Live feedback | Live results against the backtest's expectation (hit rate, slippage, drawdown); small drift means re-optimise, large drift means back to step 3 with the reason; decay scan; auto-retire | code | as stated | Built; never exercised. |
| 14 | Observability | LLM gateway history; run logs; which of the 41 edges have carried real data; a daily health report | code | alert | Partly. The gateway and edge recorder exist; half the edges are unseen; no daily report. |

## The three sources, same gate

| Source | Enters at | Then |
|---|---|---|
| AI-written (planner picks a ticker) | step 3 | steps 4 to 13 |
| Ready-made (11 in `vinu-strategy/strategies`, already in bar-size variants) | step 3, through the research service's strategy validation | steps 4 to 13, never trading on their own |
| User-added (raw idea via Thesis Intake, or a new strategy file) | step 3 | steps 4 to 13; a raw idea first goes through the research team to become code |

## Build order (proposed)

1. **Step 6 and 9 together.** After a PASS, run the research service's validation on the strategy's stored code, so the bar's numbers are computed and saved on the artifact with its bar size. Until this exists nothing can trade.
2. **Step 4.** One strategy, all four bar sizes, one comparison table, promotion per bar size.
3. **Step 7.** Make the risk critic advisory. Code decides.
4. **Step 3 and D0.** Indicator-name check; a readiness gate that blocks runs on stale or thin data.
5. **Exercise the back half** (steps 10 to 13) with one controlled paper order, once there is a strategy that passes. This needs your explicit OK.
6. **Step 14.** Daily health report and edge coverage.

## Decisions I need from you

1. **Who decides PASS:** code only (recommended), or code plus the critic with a veto both ways?
2. **Across bar sizes:** is a strategy promoted if it passes on any one bar size (recommended, recorded per bar size), or must it pass on all four?
3. **Minimum trades per bar size** before a result counts (I suggest 30, so a lucky handful of trades can't pass).
4. **Attempts and cost:** 3 attempts per strategy is set. One strategy across 4 bar sizes is about 4 backtests per attempt, which is cheap next to the model time. Confirm.

## Decisions taken (2026-10-07, by me as designer, on the owner's instruction to proceed)

1. **Who decides PASS:** code only. The risk critic stays as advice (build step 3, below).
2. **Across bar sizes:** a strategy is promoted when it clears the bar on any one bar size; that bar size is stored on the artifact (`bar_interval`) and the full table of all four is stored with it (`bar_evidence`).
3. **Minimum trades:** 30 per bar size (the existing `min_trades_for_pass`, now enforced in the per-bar verdict as well).
4. **Attempts:** 3 per strategy stays.

## Build log

### Step 1 and 2 (done): one strategy on every bar size, judged by code, numbers from records
- New `vinu_research/bar_validation.py` and route `POST /research/validate-code`: the same code is run unchanged on 1d, 4h, 1h and 15m (windows 4y / 3y / 2y / 1y), each through the full research checks (in-sample, holdout, stress, deflated Sharpe), and each bar size gets its own verdict: loop passed, at least 30 trades, `meets_promotion_bar`. Returns a comparison table and the chosen bar size (highest deflated Sharpe among those that cleared).
- The research response now carries the simulator's own numbers (`attempt`: Sharpe, drawdown, return, trade count, win rate), `pbo` and `interval`, so nobody parses report text.
- PBO needs a set of parameter trials; a fixed rule has none, so it is recorded as `None` with `pbo_waived: true` and not required for that bar size (a real PBO above 0.7 still blocks). Deflated Sharpe, holdout and stress still apply.
- `Artifact` gained `bar_interval` and `bar_evidence` (stored, migrated).
- The agent's artifact writer now calls `validate-code` right after a research PASS: it replaces the model's typed Sharpe/drawdown with the measured ones and the bar size; if no bar size clears the bar the artifact is DISABLED with the table; if the check cannot run the model's numbers are NOT trusted (deflated Sharpe 0, holdout/stress unknown), so it fails the promotion bar closed.
- The strategy code a model writes as `class Strategy(BaseStrategy)` without imports (what the agent prompt asks for) is put in the form the loop runs (`UserStrategy` plus imports) before testing.

### Found while checking it on the live stack (the "win rate 1.8%" oddity)
Six recipe templates (crossover, ADX crossover, supertrend, MACD, VWAP, momentum/mean-reversion trend branch) returned `state.astype(int).diff()`. The simulator treats each bar's weight as the position held on that bar, so the position was held for ONE bar at each cross and flat the rest of the time. Every sweep and every research PASS built on those templates measured one-bar blips, not trend strategies (win rate 1-2%, huge turnover on 15m and 1h; AMD crossover 5/60, 1d: Sharpe 0.77 and 42 trades as written, Sharpe 1.13 and 23 trades with a held position; 15m was Sharpe -13).
- Fixed in `generator.py`: the templates now hold the state (long while true, flat otherwise, no shorting); the supertrend template had never been a supertrend (a one-bar 3-ATR jump entry) and is now a real one with ratcheting bands.
- The model prompts (`idea_generator/prompt.md`, `llm_generator.py`) now say what the weights mean, with the crossover example, so a model does not write the one-bar form either.
- Tests run each recipe's generated code and check the average holding length is above one bar and nothing goes short.
- Results computed with the old templates are not evidence of anything. The pre-fix AMD "PASS" (Sharpe 0.61, win rate 1.8%) is void.
