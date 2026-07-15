# Advanced Vision Plan — Part 2: Trustworthy Multi-Signal Strategy Research

## Objective

Turn the strategy research loop from "price + technical indicators only, with narrative-only news/ML context" into a system where **ML scores, session timing, and news are real per-bar inputs the strategy can act on** — not just commentary the Risk Critic talks about after the fact — while fixing the measurement bugs that would otherwise make every result from that expanded system unfalsifiable.

This plan is the direct output of hands-on testing done this session: running all 6 services locally against real AAPL data, running the LLM-driven refinement loop (`vinu-research`) at daily/15m/1h timeframes against a live local model (`qwen36-35B` @ `localhost:8009`), and tracing every "that's odd" result back to root cause in the actual code. Every bug below was reproduced, not inferred.

---

## The core mental model

Today, `generate_weights(data)` — the function every LLM-generated strategy implements — sees exactly one tier of information:

| Tier | What | State today |
|---|---|---|
| **1. Price + technical indicators** | OHLCV + `sma_20`, `rsi_14`, etc. (23 named indicators + Alpha101/158/360 + curated packs, all in `vinu-features`) | Works. Verified today across daily/15m/1h. |
| **2. ML-derived scores** | 9 models in `vinu-features/compute/ml_models/` (linear/ridge/lasso/elastic_net/logistic/random_forest/lightgbm/xgboost/catboost) | Built, wired to a worker pipeline, **but the score is fabricated** — see Bug #7. |
| **3. News / correlation / session** | `vinu-news`, `vinu-correlation` | Exists only as **narrative text** fed to the Risk Critic post-hoc. The strategy code itself is blind to it at decision time. |

The single highest-leverage architectural change in this plan is collapsing tiers 2 and 3 into tier 1's shape: real numeric columns merged into the same per-bar `data` DataFrame that already carries `sma_20`/`rsi_14`, via the same `indicator_data` merge point in `vinu-simulator/engine/custom_sim.py`. Once that's true, "news changes the trade" and "session changes the trade" become literal, testable facts instead of aspirational LLM narrative.

**Why fix measurement before adding signal sources**: if news-fusion (tier 3) is layered on top of an ML pipeline that's currently measuring in-sample noise (tier 2), a good-looking backtest afterward is unfalsifiable — you can't tell whether it's the new signal or the old overfitting artifact. Bugs must be fixed in dependency order, not vision order.

---

## Bugs found this session (root-caused, several already fixed)

| # | Component | Bug | Status | Why it matters |
|---|---|---|---|---|
| 1 | `vinu-stock-price` | `CatalogStore` opens sqlite with default `check_same_thread=True`, but the backfill orchestrator runs each symbol in a `ThreadPoolExecutor` — every job throws `sqlite3.ProgrammingError` on first write. Combined with `concurrent.futures.wait()` instead of `.result()`, the exception is **silently swallowed**: backfill reports "0 years attempted, 0 rows," no error at all. | **Not fixed** — routed around by calling the underlying function single-threaded. | Silent zero-data failures are the most dangerous class of bug: nothing downstream knows the data never arrived. |
| 2 | `vinu-stock-price` | Alpaca provider never sent `feed=iex`; this account's plan 403s on SIP (the default) for all historical bars. | **Fixed** (`providers/alpaca.py`) | Blocked all real data ingestion until found. |
| 3 | `vinu-features` | `_normalize_rows()` only recognized `ts`/`timestamp`/`sort_ts` as the bar-timestamp key, but `vinu-stock-price`'s candles API returns `bar_ts`. Every row was silently dropped — feature runs "succeeded" with `row_count: 0`. | **Fixed** (`engine/engine.py`) | Cross-service contract mismatch; would have silently broken every feature computation. |
| 4 | `vinu-research` CLI | `run_main()` does `asyncio.run(loop.run(...))` then, separately, `asyncio.run(tools.close())` in a `finally` block. Two different event loops — httpx clients created in the first are torn down under the second, raising `RuntimeError: Event loop is closed`. **This happened on every single CLI invocation**, success or failure. | **Fixed** (`cli.py` — collapsed into one `asyncio.run()`) | Nobody running `vinu-research run` ever saw the final report, the approve prompt, or a saved strategy file, regardless of strategy quality. |
| 5 | `vinu-simulator` | Any fully-invested (100% notional) target weight always failed to buy: `cost = notional × (1 + fees + slippage + impact)` always exceeds `cash` when the target is exactly 100%, since no buffer was reserved. The buy was silently skipped — forever, every rebalance day. | **Fixed** (`engine/simulator.py` — shrink-to-fit loop instead of skip) | This is why the very first backtest ("SMA 10/30 on AAPL daily") showed 0 trades and Sharpe 0.00 — it wasn't that the strategy never signaled, it's that every signal's buy order silently failed. |
| 6 | `vinu-simulator` | Sharpe/CAGR/Sortino annualization hardcoded `√252` (1 row = 1 day) everywhere in `metrics.py`. Feeding 15m/1h bars through unchanged produces nonsense (treats 26 15-minute bars as 26 trading days). | **Fixed** — added `periods_per_year_for_interval()`, threaded through `compute_full_metrics`/`compute_extended_metrics`/`_get_basic_sharpe`, and added `interval` to `SimulationConfig` + `CustomSimulateRequest`. | Prerequisite for any intraday work at all — without this, every intraday metric reported today would have been fabricated. |
| 7 | `vinu-features` | **Every one of the 9 ML models fits and predicts on the identical array** (`model.fit(arr, y); model.predict(arr)`). `train_test_split` appears nowhere in the codebase. Reproduced live: `random_forest` on a `momentum` preset run against real AAPL data gave **0.878 correlation** between `ml_score` and true forward return — a random forest memorizing training noise, not a forecast. | **Not fixed** — reproduced and root-caused only. | This is the biggest blocker to trusting tier 2 at all. Any strategy built on `ml_score` today is backtesting against training residuals. |
| 8 | `vinu-research` loop | LLM-generated strategy code referenced a `session` column (`data.get('session', ...)`) and the Risk Critic suggested "session filter to skip London volatility" — **but no such column is ever computed anywhere in `vinu-features`.** The filter is dead code; the LLM hallucinated a feature that doesn't exist. | **Not fixed** (needs building — see Phase 2 below) | Confirms tier 3 doesn't exist as a real input; the critic's own suggestions can't currently be trusted to correspond to real, working code. |
| 9 | `vinu-research` loop | The PASS/REFINE/STOP verdict's performance bar is a hardcoded magic constant: `meets_performance_bar = sharpe_ratio >= 1.5 and max_drawdown > -0.08` (loop.py:815). Not exposed via `ResearchConfig` or CLI at all, and not interval-aware — the same 1.5/-8% bar is demanded of a 15m strategy as a daily one, even though intraday costs make that bar close to unreachable for a simple crossover. | **Not fixed** | Directly blocks user-defined risk targets (see Phase 5). |
| 10 | `vinu-research` loop | The MaxDD circuit-breaker's log message uses a broken format string (`"MaxDD %.1%% exceeds threshold %.1%%, stopping"` — `%.1%%` is not a valid format spec), so `LOG.warning(...)` throws internally and the message is silently dropped. The loop still stops correctly, but the *reason* never reaches the log. | **Not fixed** — cosmetic | Low priority, but caused real confusion when diagnosing why a run stopped after 1–2 iterations instead of the requested `max_iterations`. |
| 11 | `vinu-research` CLI | Output file naming (`output/{symbol}_{strategy_class_name}.py`) has no interval/timestamp/run-id component — rerunning the same symbol at a different interval or time silently overwrites the previous saved strategy. | **Not fixed** — cosmetic | Lost the 15m run's saved strategy file when the 1h run wrote to the same path minutes later. |
| 12 | `vinu-features` | `vinu-simulator`'s `/health` and `vinu-research`'s references to `/indicators/{symbol}` are dead/stub code: `/health` always reports dependent services as unhealthy even when they're up (never actually checks them); `/indicators/{symbol}` on `vinu-features` doesn't exist (404) and the client method calling it (`ResearchTools.get_indicators`) is unused by the actual loop. | **Not fixed** — non-blocking, but worth cleaning up so it stops looking like a real integration point. | Low priority. |
| 13 | `vinu-research` loop | The Risk Critic's suggestions are never verified against the next iteration's actual code. Concretely observed: iteration 2 of the 1h AAPL run generated `signal = (fast_ma > slow_ma).astype(int).diff()` — a state bug that fires a nonzero weight only on the single bar where the crossover happens, never *holding* the position — collapsing win rate from 24% to 1%. The critic's own reasoning never diagnosed this; it kept suggesting generic filters (ADX, RSI) instead of catching that position-holding itself was broken. | **Not fixed** — needs the verification layer in Phase 4. | This is the deepest, hardest-to-fix issue: good-sounding critique text doesn't mean the critique is correct, and nothing today checks that it is. |

---

## How the bugs relate to each other (dependency graph)

```
#1 CatalogStore thread-safety  ──┐
#2 Alpaca feed=iex              ─┼─→ blocks any real data ingestion (fixed enough to proceed)
#3 bar_ts field mismatch        ─┘

#5 buy-sizing (100% notional)   ──→ blocks ANY fully-invested backtest from ever showing a trade
#6 interval-aware annualization ──→ blocks ANY intraday (15m/1h) metric from being meaningful
#4 CLI event-loop crash         ──→ blocks seeing ANY result at all, regardless of correctness

#7 ML train/test split          ──→ blocks trusting tier-2 (ML) features
#8 no session column            ──→ blocks tier-3 (news/session) features from being real
#9 hardcoded PASS bar           ──→ blocks user-defined risk targets
#13 unverified critic suggestions ─→ blocks trusting ANY iteration-over-iteration "improvement"
```

Read top to bottom: #1–#6 were plumbing/correctness bugs that had to be fixed (or routed around) just to get a trustworthy *baseline* result at any timeframe — done this session. #7–#9 and #13 are what's standing between that baseline and the actual vision (news + ML + session-aware strategies with a verifiable, user-controllable research loop).

---

## Phased implementation plan

### Phase 0 — Close out the found-but-unfixed correctness bugs
*Small, independent, no design decisions required. Do these first because they're cheap and every later phase benefits from a clean base.*

| Step | File(s) | What |
|---|---|---|
| 0.1 | `vinu-stock-price/vinu_stock/catalog/store.py` | Fix `sqlite3.connect()` thread-safety (either `check_same_thread=False` with a lock, or a thread-local connection factory) |
| 0.2 | `vinu-stock-price/vinu_stock/backfill/orchestrator.py` | Replace `concurrent.futures.wait(futures.keys())` with iterating `.result()` on each future so exceptions surface instead of vanishing — audit for the same swallowed-exception pattern elsewhere in the codebase (this exact shape hid bug #1 from us for hours) |
| 0.3 | `vinu-research/vinu_research/loop.py` | Fix the `%.1%%` format string in the MaxDD early-stop warning |
| 0.4 | `vinu-research/vinu_research/cli.py` | Include `interval`, a timestamp, and/or `run_id` in the saved-strategy output filename |
| 0.5 | `vinu-simulator/vinu_simulator/server/routes_read.py` | Make `/health` actually check dependent services instead of returning static `False`s |
| 0.6 | `vinu-research/vinu_research/tools.py` | Remove the dead `get_indicators()` / `/indicators/{symbol}` client method (unused by the loop, and the endpoint doesn't exist) |

### Phase 1 — Fix the ML measurement problem (tier 2 becomes trustworthy)

| Step | File(s) | What |
|---|---|---|
| 1.1 | `vinu-features/compute/ml_models/runner.py` | Add a single time-ordered holdout split (e.g. first 80% train / last 20% test, no shuffling — this is a time series) applied once, before dispatch, so all 9 models get it for free rather than patching each model file |
| 1.2 | `vinu-features/compute/ml_models/runner.py` | Report out-of-sample metrics (correlation / information coefficient between `ml_score` and true forward return, computed **only on the held-out slice**) alongside the score, not just raw predictions |
| 1.3 | `vinu-features/compute/ml_models/registry.py` | Add a `select_best(models, X, y)` helper that runs several models, ranks by out-of-sample IC, and returns the winner — this is the real version of "the AI chooses the model," done by measurement rather than an LLM guessing |
| 1.4 | `vinu-features/compute/ml_models/*/​*.py` (all 9) | No change needed if 1.1 is done at the `runner.py` choke point — confirms the fix doesn't need to touch 9 files individually |
| 1.5 | Regression check | Re-run the exact reproduction from this session (`momentum` preset + `random_forest` + `forward_return_1` on AAPL) and confirm the reported OOS correlation drops from the fabricated 0.878 to something realistic (likely near zero for a 5-feature random forest on 131 rows — that itself is a useful, honest finding) |

### Phase 2 — Session as a real feature (closes bug #8, smallest of the tier-3 work)

| Step | File(s) | What |
|---|---|---|
| 2.1 | `vinu-features/compute/indicators/session/session.py` (new) | Pure function of bar UTC timestamp → `asia` / `london` / `ny_regular` / `london_ny_overlap` / `off_hours` — register it like any other indicator |
| 2.2 | `vinu-features/compute/registry.py` | Register `session` in the indicator catalog so it can be requested like `sma_20` |
| 2.3 | `vinu-simulator/vinu_simulator/service.py` | Add `session` to the `requested_indicators` list merged into `data` in `simulate_custom`, so strategy code's `data.get('session', ...)` (already written by the LLM today, currently a no-op) starts actually working |
| 2.4 | Validation | Re-run the exact 15m/1h AAPL research loop from this session with `session` now real, and check whether the critic's own "skip London session" suggestion, once actually wired, changes the outcome — this is a clean before/after because we already have the "broken" baseline on record |

### Phase 3 — News as a real per-bar feature (tier 3, the deepest unknown)

*Do this only after Phase 1 and 2 land — it's the biggest scope item and the plan below assumes we don't yet know exactly what `vinu-news`'s LLM analysis currently extracts per article. First step is a recon pass, not a build.*

| Step | File(s) | What |
|---|---|---|
| 3.1 | `vinu-news/vinu_news/analysis/**` (read-only recon) | Inspect what the existing LLM-analysis pipeline actually stores per article today — sentiment score? category/type? impact score? confidence? This determines how much of 3.2–3.4 is "expose it" vs. "build it" |
| 3.2 | `vinu-correlation` (new numeric export) | Add a per-timestamp numeric feature export — e.g. `news_sentiment_ewma`, `hours_since_last_headline`, `news_type_flag` — distinct from the existing narrative `/story` endpoint, which stays as-is for the critic |
| 3.3 | `vinu-features` or `vinu-simulator` | Wire the new correlation export into the same `indicator_data` merge point used for `session` in Phase 2, so news becomes just another column `generate_weights()` can read |
| 3.4 | Validation | A/B test: same strategy idea, same symbol/dates, with and without the news column available, and confirm the LLM-generated code actually conditions on it (not just references it and ignores it, the way `session` was referenced-but-dead before Phase 2) |

### Phase 4 — Post-hoc news/trade attribution reporting (the analysis-layer half of your point 1)

*Independent of Phase 3 — this doesn't require news-as-a-feature, it's a separate report generated after a backtest completes.*

| Step | File(s) | What |
|---|---|---|
| 4.1 | `vinu-research` or a new small module | For each trade in a completed run, query `vinu-correlation`/`vinu-news` for articles in a configurable window around the trade timestamp (e.g. ±6h) |
| 4.2 | Same | Classify each matched article (using whatever `vinu-news` already extracts per 3.1, or a lightweight LLM classification pass if it doesn't) and aggregate win/loss rate by news type |
| 4.3 | Same | Track story persistence — does the same underlying event show up across consecutive days' articles, and does trade performance change across that persistence window |
| 4.4 | `vinu-research/vinu_research/loop.py` | Feed the **structured** output of 4.2/4.3 into the Risk Critic's prompt in place of (or alongside) today's loose narrative "story blocks" — e.g. "trades within 6h of earnings-type news: 15% win rate vs 55% baseline" is something the critic and next-iteration Quant Coder can act on; free-text narrative isn't |

### Phase 5 — Configurable risk targets + verified suggestions (closes bugs #9 and #13)

| Step | File(s) | What |
|---|---|---|
| 5.1 | `vinu-research/vinu_research/config.py` | Add `target_max_drawdown` (hard gate, e.g. default -0.30 per your stated preference) and remove the hardcoded `sharpe_ratio >= 1.5` cliff |
| 5.2 | `vinu-research/vinu_research/loop.py` | Restructure the PASS decision: reject any candidate breaching `target_max_drawdown` outright; among survivors (across the iteration budget, not just the latest one), keep the one with the best Sharpe — maximization, not a threshold to clear |
| 5.3 | `vinu-research/vinu_research/models.py` / metrics reporting | Surface Sortino alongside Sharpe in every report (cheap — the return series is already computed) so a "smooth until it isn't" strategy shape is visible, not hidden behind a single number |
| 5.4 | `vinu-research/vinu_research/loop.py` | Add a cheap static verification pass on LLM-generated code before it's trusted: does the weight series actually hold nonzero values across multiple consecutive bars (catches the `.diff()` bug from #13); does it reference only columns that actually exist in `data` (catches the `session` hallucination from #8, and would catch the next one of these) |
| 5.5 | `vinu-research/vinu_research/cli.py` | Expose `--target-max-drawdown` (and keep `--interval`, added ad hoc this session via env var only, as a real CLI flag too) |

---

## Additional top-level suggestions (beyond what was directly discussed)

1. **A golden-strategy regression suite.** Every bug in the table above was found by manual, hours-long investigation — none of it would have been caught by an automated test. A small suite of 2–3 known strategies (e.g. "always 100% long," "SMA 10/30 on a synthetic trending series with a known trade count") run against fixed synthetic data on every change to `vinu-simulator`/`vinu-features` would have caught bugs #5, #6, and #7 immediately instead of requiring a live investigation session. This is cheap relative to the cost of silent failures we kept finding.

2. **Realistic cost-model review.** The buy-sizing bug (#5) exists because a 100%-notional target leaves no room for `transaction_cost_pct` + `slippage_pct` + Almgren-Chriss market impact. Worth a deliberate pass over whether those default cost assumptions (0.1% fee, 0.05% slippage) are realistic for the account/broker this is meant to model, especially once intraday (15m) strategies are in scope — we already saw 420% annual turnover at 15m; costs dominate the outcome at that turnover rate more than the signal does.

3. **Unify `interval` as a first-class concept, not an env-var afterthought.** This session added `interval` support to `vinu-simulator` and `vinu-research` because it was needed for the 15m/1h test — but it's currently plumbed through as a `ResearchConfig` field settable only by env var, with no CLI flag. Once Phase 5.5 adds it properly, also audit `vinu-features` and `vinu-correlation` for the same gap (does correlation's market-hours-only logic behave correctly at non-daily granularity? Untested.).

4. **Multi-symbol / portfolio mode is unverified.** `ResearchConfig` already has `portfolio_beta_hedge_lookback_days` and a `universe` parameter on the CLI, implying portfolio-level backtests are supported — but everything tested this session was single-symbol (AAPL only). Before building more single-symbol features (news, session, ML), worth a quick check that the existing portfolio path still works given how much of `vinu-simulator` changed this session (interval, buy-sizing, annualization).

5. **LLM call logging should be a first-class `vinu-research` feature, not a test-script hack.** `e2e_llm_test.py` wraps `chat_json` ad hoc to log every prompt/response/duration for debugging — that's exactly the kind of tracing that should live in `vinu-research` itself (and would slot naturally into the `vinu-complete-manager` dashboard already planned in `project-enhancement-plan/enhancement-plan-1.md` — the two plans should share the same tracing infrastructure rather than building it twice).

6. **Decide the PASS-bar defaults deliberately, not by feel.** Phase 5 makes MaxDD a hard gate and Sharpe a maximization target — but "-30% MaxDD as the hard gate" was a number from conversation, not backtested against what's actually achievable per timeframe. Once Phase 0–2 land, worth running the same SMA10/30-on-AAPL baseline across a longer history (the 6-month window used this session is thin — `min_trades_for_pass` of 30 is barely clearable at daily granularity) to sanity-check the gate before it becomes the thing every future strategy is judged against.

---

## Suggested order of attack

**Phase 0 → Phase 1 → Phase 2 → Phase 5 → Phase 4 → Phase 3**, with Phase 3 last because it's the biggest unknown (depends on a recon pass into `vinu-news` we haven't done yet) and everything else is independently valuable even if news-fusion turns out to be a bigger lift than expected. Suggestion #1 (regression suite) is worth threading through every phase as each fix lands, not saved for the end — it would have made this entire session faster.

------------------------------------

Good question to separate from implementation — let me think through the architecture, not just the code.

The mental model
Right now your strategy's generate_weights(data) sees exactly one tier of information: price + technical indicators (SMA, RSI, etc. — the indicator_data merged into data in custom_sim.py). Everything else — news, correlation "story blocks," ML scores — only exists as narrative text fed to the Risk Critic after the fact. The critic can talk about news and sessions, but the strategy code itself is blind to them at decision time. That's the single most important thing to understand before planning anything: your vision (news changes the trade, session changes the trade) requires those things to become columns in the same DataFrame the strategy reads, not just commentary in a critique.

So there are really three tiers of "strategy input," at very different levels of readiness:

Tier	What	State today
1	Price + technical indicators (23 named + Alpha101/158/360 + packs)	Solid, works, what we tested today
2	ML-derived scores (9 models in the registry)	Built but broken — no train/test split, so any score is fabricated
3	News/correlation/session-derived features	Doesn't exist as a decision-time input at all — only as post-hoc narrative
Why the order matters (not just preference)
If you build news-fusion (your point 2) on top of an ML pipeline that's currently measuring in-sample noise (point 3), you won't be able to tell whether a good-looking backtest is real or an artifact of two compounding overfitting problems. Fix measurement before you add more signal sources — otherwise every new "improvement" is unfalsifiable.

Phase 1 — Fix the ML measurement problem. (The train/test split gap, already scoped.) This isn't optional infrastructure, it's the ruler you'll use to judge everything after it, including whether news/session actually help.

Phase 2 — Turn ML scores and session into real per-bar features, same shape as sma_20/rsi_14 today. Once runner.py produces a trustworthy out-of-sample ml_score, and a session column exists (a pure function of bar timestamp — Asia/London/NY/overlap), both just get merged into data alongside the technical indicators. This is mechanically the smallest of the four changes, and it's what makes your point 4 ("best time window for London session") a real, testable question instead of LLM-hallucinated dead code like we saw today.

Phase 3 — Turn news into a per-bar feature, not just a narrative. This is architecturally the same move as Phase 2, but the hard part is different: you need vinu-correlation/vinu-news to produce something numeric-per-timestamp (e.g. hours_since_last_headline, news_sentiment_ewma, news_type_flag) rather than the free-text "story" it returns today. I haven't checked what the news LLM-analysis pipeline currently extracts per article (sentiment? category? impact score?) — that's the first thing to go look at before designing this column, since if it already tags articles by type, most of the hard work is done; if it only stores raw text + a summary, that's a real build.

Phase 4 — Post-hoc attribution reporting (your point 1: which news type caused which losing trades, story persistence across days). This doesn't need to feed the strategy at decision time — it's a separate analysis that runs after a backtest: take the trade list, look up news in each trade's window, classify, aggregate win/loss by type. This is exactly the kind of structured-not-narrative summary that should also get fed back into the Risk Critic's prompt (today it gets loose "story blocks"; it should get "trades within 6h of earnings-type news: 15% win rate vs 55% baseline" — a sentence like that is something the critic can act on, versus prose it currently can't verify against).

Phase 5 — Wire Phase 4's findings into the Quant Coder + Critic loop as structured suggestions, and (tying back to our earlier conversation) verify the next iteration's code actually implements them, not just claims to.

Where correlation fits specifically
vinu-correlation should be the thing that answers "was this trade news-related, and did the story evolve" — it already half does this (story/drawdown endpoints). The gap is it currently produces narrative for the critic, not structured per-trade attribution and not a numeric feature for the strategy. I'd extend it in two directions, not replace it: (a) a numeric export (features tier), (b) a structured attribution report keyed by trade (analysis tier) — same underlying data, two different consumers.

My honest recommendation on where to start
Phase 1 (ML split fix) is small, well-understood, and I already have the failure reproduced with a concrete number (0.878 correlation). Phase 2 (session as a feature) is also small and closes a real hole we found today (the hallucinated session column). Both are cheap, both are prerequisites for everything else, and both are independently useful even if you never get to news fusion. I'd do those two before touching news at all — news fusion (Phase 3) is the biggest unknown and depends on inspecting what vinu-news's analysis actually extracts today, which I haven't done yet.

Want me to go look at what vinu-news's LLM analysis pipeline actually captures per article first (cheap, tells us how big Phase 3 really is), before we lock in the plan?

