# Full system validation, 2026-10-06 (production-grade view)

Scope: every link from data to paper order, plus the live feedback loop. Method: read the running stack (container state, logs, stores, the pipeline-edges panel, the Alpaca paper account), reproduced faults directly, ran every package's test suite. Statuses mean:

- **PROVEN**: ran in the real stack and the output was inspected.
- **WIRED, NOT PROVEN**: code and connections exist, but no real data has ever gone through, so it has never been exercised.
- **BROKEN / GAP**: a fault or missing piece, with the fix or the recommendation.

Verdict: **not production-ready.** The front half (data to research) is proven and now fails safe. The back half (gate, funding, live orders, live feedback) is wired but has never carried a real strategy, because no strategy has passed the promotion bar.

## 1. Link by link

| # | Link | Status | Evidence | Gap and improvement |
|---|---|---|---|---|
| 0 | Containers and infra | PROVEN | 12 containers healthy; models container dormant on purpose; LLM one slot, 40,192 context. | `stock-api` shows 9 restarts in its life (exit 0, cause not found). Find the cause. Data folders are bind-mounted from a OneDrive path under Docker Desktop; use named volumes for production. |
| 1 | Price data | PROVEN, SLOW | All 10 tickers have bars through the Oct 5 close in 1d, 1h, 15m, 1m. | A single candle call takes 2 to 8 s with an idle CPU: daily/hourly candles are aggregated from 1-minute parquet on every request through one shared DuckDB connection, with no candle cache. This made parallel sweeps time out (fixed downstream by sharing fetches). Improve: cache or pre-materialise 1d/1h bars. Also: one `database is locked` during schema setup on a new connection in the ingest cycle (recovers next cycle); skip schema setup after the first connection per process. |
| 2 | News | WIRED | News API healthy, no errors in 2 h. | `models.finbert_score->news.backfill` has 12 misses by design (models container off). 3 news tests are stale (fakes lack the `headers` argument). |
| 3 | Screener top 10 | PROVEN | Top 10 stored; `screener.top->agent.planner_worker` flowing (13 received). | None found. |
| 4 | Initial analysis | PROVEN, PARTIAL BY DESIGN | Runs `vinu-initial-compute --all --continuous` for the whole watchlist, so no trigger is needed (B3 answered). 15 of 27 angles have data per ticker. | 12 angles need the dormant models container. They are retried every cycle and logged as full tracebacks (about 5,500 per 20 h). Improve: skip them when models are off and log one line. |
| 5 | Summaries and planner | PROVEN | All 10 summaries stored; planner loops (summary refresh, then research per ticker). | A lap takes about 1.5 h. Runs killed by a restart stay `running` forever (9 stale rows seen); add reconciliation at startup. 16 screener and 3 research runs failed earlier on 500/503 from the LLM before the one-slot fix; check that none recur. |
| 6 | Strategy writer (idea generator) | PARTIAL | Produces crossover, breakout, RSI recipes with parameter grids. | The 9B model gives weak ideas and often ends with "max iterations". Failure reasons are fed back by the manager prompt, but I have not seen the model use them. |
| 7 | Research and simulation | PROVEN after 4 fixes today | RSI recipe fixed (was crashing everywhere); walk-forward now runs and rejects the MSFT RSI strategy (Sharpe gap 1.06, 33% OOS positive windows); candle fetches share one request. | `walk_forward` verdict was never part of any earlier result. Re-run research for all 10 tickers on the fixed stack. |
| 8 | Optimise and retry | WIRED, NOT PROVEN | Sweep-refine, round cap, exhaustion rule, feedback to the idea generator are in code and prompts. | Needs a run where a candidate is refined into something better, and a run where the idea generator visibly changes approach after a failure. |
| 9 | Promotion to a strategy artifact | WIRED, NOT PROVEN | PASS creates a BENCHING artifact (`research_artifact_writer`). Artifact store is empty (0 rows). | Nothing has passed. The research team's PASS is lighter than the full promotion bar; the gatekeeper is the second check. |
| 10 | Fate keeper: risk gatekeeper, then capital allocator | WIRED, NOT PROVEN | Both workers cycle (3 cycles in 20 h) with nothing to review. Gatekeeper moves BENCHING to PEND; allocator moves PEND to ACTIVE, or PENDBLOCK if the kill switch is on. | Never ran with a real candidate. Edges `portfolio.risk_status->order_guard`, `portfolio.state->order_guard`, `halt_flag`, `breaker.limits`, and the entry guards show `never_seen`. |
| 11 | Portfolio allocation | PROVEN, WITH ONE RISK | Daily allocation runs; equity $96,614; `cold_start` tier deploys 9% ($8,695); drawdown and maturity edges flowing. | The daily allocation lists 11 YAML strategies, including `e2e_easy_sma_crossover` and `paper_smoke_test`, each at weight 0.0909. These are the strategies the validation gate rejected. They have no symbol, so the scheduler's `RESPECT_TRADE_PLAN_SYMBOLS` setting is probably what stops orders. Confirm this with a test, and drop non-ACTIVE strategies from the allocation. |
| 12 | Live scheduler (hourly) | WIRED, WAS SILENT | 0 rows in `scheduler_executions`; 38 allocation reads. | **Fixed today**: the `vinu-live-worker` entry skipped logging setup, so every cycle line was dropped. Rebuilt and restarted. Check its next cycle line. Known gap: `book.writes->live.scheduler` (scheduler orders not recorded in the book the breaker checks). |
| 13 | Live decision loop and trade plans | PROVEN IDLE | 299 trade-plan, approval and feedback cycles in 30 h; all empty. Fails closed when research is unreachable ("strategy validations unreadable, no new entries"). | Never carried a real plan. |
| 14 | Broker (Alpaca paper) | PROVEN | Account ACTIVE, equity $96,614.07, no positions, not blocked, market closed until 13:30 UTC. Keys exist only in the agent container. | Sep 9 history shows a 1,191.97-share AAPL sell after a 104-share buy: a sizing anomaly, not investigated. Fractional-share and Alpaca minimum handling untested. |
| 15 | Live feedback: minor versus major, back to the strategy writer | WIRED, NOT PROVEN | Decay scan with graduated responses exists. | I did not verify that a major failure sends the main reason back to the strategy writer. Needs a fault-injection test with a fake degraded paper strategy. |
| 16 | Reflection | PROVEN QUIET | Worker up, no errors in 2 h; `reflection.synthesis->idea_generator` flowing (366). | None found. |
| 17 | UI | NOT CHECKED | `vinu-ui` is not in the compose stack. | Decide whether it ships. |

## 2. Fixed in this validation (each with a test and a commit)

16. RSI recipe computed from a float-named column; every symbol crashed, hidden as "no weight data".
17. Walk-forward never ran in the real chain (no config passed).
18. A failed candle fetch was cached forever; 12 identical parallel fetches flooded the stock API. Failed fetches are no longer cached, and identical concurrent requests share one fetch.
19. All 10 summaries now stored (checked).
20. Hourly order scheduler ran with no logging.
21. Research health report claimed all three dependencies reachable while each probe returned 404; probes now use each service's real route and 4xx/5xx counts as unreachable.

## 3. Test suites (run on this host, package by package)

| Package | Result |
|---|---|
| infra | 509 passed |
| tools | 207 passed |
| stock-price | 149 passed |
| screener | 456 passed |
| simulator | 307 passed |
| portfolio | 292 passed |
| strategy | 168 passed |
| live | 950 passed |
| reflection | 206 passed |
| research | 1,394 passed, 2 failed (`test_empty_meanings` env test, flaky `test_concurrent_writes`; both unrelated) |
| agent | 1,559 passed, 16 failed: all in `test_llm.py` and `test_service.py`, need the `openai` package this host lacks. Not re-run in a container. |
| news | 145 passed, 3 failed: stale test fakes (missing `headers` argument), one llm-sentiment case |
| initial-analysis | 4 files fail at collection: they import modules that do not exist or need `statsmodels` locally. Test debt. |
| quant-core | no tests folder |

On Windows, `PYTHONPATH` entries need `;`, not `:`. A wrong separator produces false import errors.

## 4. What stands between this and production, in order

1. **Get one strategy through, for real.** Re-run research for all 10 tickers on the fixed stack. If none passes the unchanged bar, read each failure and widen the candidate pool (more recipes, per-regime strategies, longer history). Do not lower the bar.
2. **Exercise the back half with a controlled strategy** in a test environment: gatekeeper, allocator, order guard, kill switch, scheduler order, fill, reconciliation. Several edges show `never_seen` until this happens. The paper-order test was blocked by the permission classifier; it needs your explicit rule or your OK.
3. **Prove the live feedback loop** with a fake degraded paper strategy: a minor drop leads to optimisation, a major drop sends the main reason back to the strategy writer.
4. **Remove unvalidated strategies from the portfolio allocation** (item 11).
5. **Storage:** move data folders off the OneDrive bind mount; cache or pre-materialise daily and hourly candles; skip repeated schema setup per connection.
6. **Operations:** reconcile stale `running` runs at startup; quiet the 5,500 model tracebacks; add a per-ticker time budget in the planner; investigate the `stock-api` restarts and the Sep 9 sizing anomaly.
7. **Test debt:** run the agent suite inside a container that has `openai`; fix the 3 stale news tests and the 4 initial-analysis collection failures.
8. **Security:** rotate the API keys that were pasted earlier, after the test run.


## 5. Initial analysis value check (2026-10-06, after the first validation)

Method: for all 10 tickers, recompute values from the raw daily bars (06-17 to 10-01, the window the system uses) with independent code and compare to what initial analysis stored.

| Check | Before | After the fixes |
|---|---|---|
| Drawdown episodes (peak, trough, drop) | NVDA 7 of 7 exact. MSFT stored "0 drawdowns" although the true max was -9.5% (placeholder from a run with no price bars). | All 10 tickers, 51 of 51 episodes exact; worst episode equals the true maximum for every ticker. |
| Total return | Exact | Exact, 10 of 10 |
| Max drawdown (metrics angle) | ACN -10.6% stored vs -20.3% true; MSFT slightly off (starting price missing as a peak). | Exact, 10 of 10 |
| Sharpe (metrics angle) | CAGR over volatility: MSFT 5.34, standard formula 3.16. This number was shown to the idea generator. | Standard formula, equal to the simulator's and to the independent calculation, 10 of 10 (`cagr_over_vol` kept as its own field) |

Fixes (each with tests and a commit):
22. A ticker with no price bars yet got placeholder rows recorded as a completed run, so its real result was never computed (MSFT: 6 of 9 raw angles). The runner now computes and records nothing when the price service returns no bars, so the next cycle retries. MSFT recomputed.
23. The metrics angle's Sharpe and Sortino used the compounded return, which inflates short windows; they now use the standard definitions, with the same sample standard deviation as the simulator.
24. The metrics angle's max drawdown ignored the starting price.

Not covered by this check (cannot be recomputed exactly from bars): ARIMA, GARCH, exponential smoothing, Kalman filters, regime analysis, trend lifecycle and the 12 model angles. A different kind of check applies to them (backtest of the forecast against what happened).

Finding, not changed (design choice for you): at the daily timeframe, ARIMA, GARCH, exponential smoothing, Kalman filters and regime analysis return `insufficient_data` for all 10 tickers. Each needs 100 observations and the analysis window of about 3.5 months gives 72 daily bars. They work at 1H and finer. The strategies under research trade daily bars, so the daily-level model view is empty. Fix: a longer window for the daily timeframe (at least a year).

Risk, not changed: the runner's bar cache is keyed by (symbol, timeframe) and not by date window.


## 6. Full-system pass: tests in the real images and every API endpoint (2026-10-06, evening)

### 6.1 Why the earlier test runs were wrong, and the permanent fix
Tests had been run on the Windows host. The host lacks packages the images have (statsmodels) and the images lack packages the host has, so host runs gave false failures in both directions and hid real ones. Also, 7 of 11 running containers were older than their source code (the agent still ran the old research code in-process), because only the services being edited were rebuilt.

Permanent fixes (each guarded):
- `scripts/stale_images.py` and `scripts/stack.sh stale` list every running service older than its source (test and doc files ignored). `scripts/stack.sh deploy` rebuilds and recreates exactly those. `deploy` itself had a bug (it aborted under `pipefail` the first time anything was stale); fixed and guarded.
- `scripts/test_in_containers.sh [service ...]` runs every package's tests inside each service image, in a throwaway container with no data volumes, as root (the tests write a relative `data/` folder), with throwaway data roots for every service, and the host's current tests mounted over the image's code. It refuses to run against stale images.
- A guard test checks that every shell script parses (the runner itself was once committed with a syntax error).

### 6.2 Results in the real images (all 11 images rebuilt from current code)
| Package | Result in image |
|---|---|
| agent | 1,573 passed (8 skipped: cross-package) |
| research | 1,397 passed, 1 skipped |
| live | 947 to 950 passed |
| portfolio | 292 passed (in the 4 images that carry the research package; skipped in quant-core, which does not) |
| simulator | 307 passed |
| strategy | 168 passed |
| stock-price | 149 passed |
| screener | 456 to 457 passed |
| tools | 207 passed |
| infra | 442 passed in-image, plus the repo-level tests on the host (stack guards, compose wiring, edge manifest) |
| news | 147 passed, 1 skipped (needs torch) |
| reflection | 206 passed |
| initial-analysis | 385 passed, 6 skipped, 2 failed in the first in-image run; both fixed (see 6.6) |

Test fixes: news test fakes lacked the `headers` argument the code now sends; tests that need a second package or an unbuilt angle now skip explicitly (they pass in the images that carry both); the research concurrent-writes test shared one mutable record across four threads.

### 6.3 API sweep: every GET endpoint on every service
| Service | Result |
|---|---|
| stock, news, features, initial-analysis, quant-core, research | 0 server errors; 4xx only for deliberately fake ids or parameters. One slow call: `/news/watchlist/news` took 12 s. |
| live | 14 of 14 return 2xx (authenticated) |
| portfolio | 9 of 9 return 2xx (authenticated) |
| screener | 7 of 9 return 2xx; 1 bug fixed (below); the last is a legitimate 4xx |
| agent | 25 GET paths; 1 bug fixed (below), the rest answer correctly |

Bugs found and fixed (tests added):
- `GET /agent/sessions/{id}/events` held a stream open forever for a session that does not exist, which hung any client polling a wrong id. It now answers 404.
- `GET /screener/pairlist/{rule}` answered 503 (an outage, worth retrying) for a rule that does not exist. It now answers 404.

### 6.4 SQLite "database is locked" under concurrent opens: root cause found and fixed
Reproduced with a 12-thread test (round 0 failed). Switching a file to WAL and the first schema write need locks the busy timeout does not wait for, so concurrent opens of one database failed instantly. This is what killed the stock ingest cycle ("Ingest cycle failed: database is locked") and made the research concurrent-writes test fail one run in three. The shared base class now retries setup with backoff until a deadline, and the 8 other places that set WAL themselves use a shared `enable_wal` helper. A guard test fails if any service writes the raw pragma again.

### 6.5 Still open from this pass (not fixed)
- `GET /agent/trace/{ref}` matches any substring of the audit log, so a short made-up id like `x` returns `found: true`. Documented behaviour, misleading result; add a minimum length.
- `GET /agent/broker/order/{id}` answers 200 with an error inside the body for an invalid order id.
- Granularity names differ between APIs (`1D` on the angle routes, `1day` on the stage-1 routes).
- Initial analysis logs about 850 tracebacks per 20 minutes trying to reach the dormant models container; one line per cycle is enough.
- Research-api has no `vinu_api_key`, so it cannot call the protected services (agent, live, portfolio, screener). No call does this today (no 401 in 24 h of traffic); a future one would fail.
- Initial-analysis test suite takes about 30 minutes in-image; split the model-angle tests from the fast ones.


### 6.6 A real production bug found by the in-image run: news-price causality always said "no causality"
The in-image initial-analysis run failed `test_granger_detects_causality` (p = 1.0 where a clear causal signal was planted). Cause: statsmodels 0.15, the version in the image, removed the `verbose` argument; the angle passed it, got a TypeError, and a bare `except` turned that into "no causality, p = 1.0" for every ticker. The host run never saw it because the host has no statsmodels at all. Fixed (call without `verbose`, log the exception and return an `error` field instead of hiding it), guarded by a test, deployed. The second in-image failure (`test_admin`) needs torch for a model angle and now skips without it.

Not fixed, found while checking the stored results:
- The stored `news_price_causality` rows were computed with the bug and are treated as finished, like the MSFT placeholders before. They should be cleared and recomputed (same procedure as the metrics angle) once there is enough news to test.
- The news store only reaches back to about 2026-09-29, and the analysis window is 2026-06-17 to 2026-10-01, so only 0 to 12 articles per ticker fall inside it (NVDA 0, MSFT 12, AMD 5, TSLA 6, META 8). TXN has no articles at all although it is on the news watchlist. A causality test needs far more. Backfill news history (the news service has a backfill job) before relying on any news angle.
- The analysis window ends on 2026-10-01 while today is 2026-10-06, so everything after that (including the news from Oct 2 to 6) is not in any angle. Decide how often the window rolls.
