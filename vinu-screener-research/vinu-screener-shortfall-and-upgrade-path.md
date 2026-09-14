# vinu-screener: shortfall, gaps, and upgrade path

Written 2026-09-14, after a pre-real-money gate-conflict audit of the vinu-components monorepo. Everything below is grounded in the actual code (file:line citations from a direct investigation), not assumption — where something is uncertain, it's marked as such.

## What vinu-screener actually is today

`vinu-screener` is a candidate ticker screening/ranking pipeline (`vinu_screener/pipeline/pipeline.py`'s `ScreenPipeline`, driven by `vinu_screener/rankers/runner.py`'s `RankerRunner`):

1. Fetch OHLCV for a configured universe of symbols (`vinu_screener/scan/data_source.py`, via `vinu-stock-price`).
2. Compute configured factors (`FactorSpec` — indicators like momentum, RSI, etc. via `IndicatorFactory`).
3. Apply a hard filter (binary pass/fail on bounds).
4. Score survivors with a weighted factor sum (`factor_score`).
5. Apply a risk overlay (bounded additive penalties — momentum-chase, breakdown, abnormal volume, stale/degraded data, etc.).
6. Apply a concentration overlay (penalize picking too many symbols from the same sector *within this batch*).
7. Rotate near-score ties for stability, optionally gate turnover.
8. Return a ranked list, top-N highlighted.

It also has a separate rule-based `ScanMonitor` (`vinu_screener/scan/monitor.py`) that fires condition-based alerts (not ranking) on a schedule, and a `serve` HTTP API plus a `scan` CLI loop for continuous ranker re-runs.

The engineering quality of what exists is good — bounded penalties, fail-open data-quality handling, no-lookahead care, batch-fetch optimization, hysteresis on rotation. The problem isn't that vinu-screener is badly built. It's that **it's an island**: a well-built ranking engine that nothing downstream actually depends on yet.

## The core finding: it doesn't feed the live loop

This is the one that matters most, and it directly answers "how much and where should it impact":

- **There is no automated path from vinu-screener's ranked output into vinu-agent's watchlist, vinu-live's trading universe, or vinu-portfolio's allocation.** The only real cross-service consumer is a human typing `/rank <ranker_id>` in Telegram (`vinu-agent/vinu_agent/channels/telegram.py:169-192`), which reads `GET /screener/rankers/{id}/latest` and prints it as a message. Nothing programmatic reads that response.
- A separate, confusingly same-named mechanism — an LLM-driven "screener" agent *team* inside vinu-agent (`agent/team.py`, `agent/screener_summary_writer.py`) — is what actually populates `TickerSummaryStore`/the real watchlist. It has nothing to do with `vinu_screener`'s `ScreenPipeline`. If you've been assuming "the screener" feeds the watchlist, it's this other thing, not the one in `vinu-screener/`.
- Telegram's `/track <TICKER>` command (manual, one ticker at a time) is the actual way a symbol enters `vinu-news`/`vinu-stock-price` watchlists — again, disconnected from `ScreenPipeline`'s ranked list.
- `vinu-screener`'s own `serve/pairlist_cache.py` and `router.py` docstrings describe the pairlist endpoint's purpose as "whatever calls this endpoint (another Vina service, an operator's dashboard)" — written speculatively, before any real caller existed. No service in the repo calls it.

**Net effect: `vinu-screener` currently produces a ranked list that nobody automatically acts on.** It's not broken — it's unconnected. Running it today gives you a report a human can read in Telegram, not a signal that changes what the system trades.

## Six concrete shortcomings

### 1. No automated downstream consumer (above) — the blocking one
Fix priority: highest. Everything else on this list is moot until this exists.

### 2. Zero portfolio-awareness
`ScreenPipeline.run()` takes only `snapshots: dict[symbol -> fields]` and an optional sector map — no held positions, no account state, no regime signal, no correlation-with-current-holdings. The "concentration overlay" only diversifies *within the current ranking batch* (penalizes picking two names from the same sector in one run) — its own docstring explicitly says real portfolio-level concentration capping "belongs to vinu-portfolio's allocation stage, not this screener-side overlay" (`pipeline/concentration.py:11-12`). So a screener run today could rank five symbols #1-#5 that are all already 80% correlated with what the portfolio already holds, and nothing here would know or care.

### 3. No feedback loop — factor weights are static forever
`FactorSpec.weight` values are set once via API/CLI config and never move. No code path reads a screened candidate's *actual trading outcome* (did it become a trade plan, was that trade plan profitable, did the confluence score real returns) back into the ranker's weights. Compare this to what the rest of the system now has, post-audit: `vinu-research`'s TradeScore calibration is adaptive and sample-gated; vinu-portfolio's regime/outcome-confidence tilts move with real evidence. vinu-screener's scoring is the one major piece still frozen at whatever weights a human typed in once.

### 4. Narrow data surface — OHLCV only
The only real data adapter is `HttpStockDataSource`, which calls `vinu-stock-price`'s candles endpoints — pure price/volume technicals. Grepping the whole package for news, sentiment, fundamentals, options, order-book, or correlation signals turns up nothing wired. The risk overlay *has* fields named for these (`llm_confidence`, `llm_risk_flag`, `deep_analysis_risk_flag`) — but they're placeholders inherited from the pattern this was ported from (`daily_stock_analysis`), never actually populated by anything inside vinu-screener today.

### 5. Data-quality risk checks were dead code until this session
`data_stale`/`data_fetch_degraded` risk penalties existed in `risk_overlay.py` since the module was written, but nothing ever set the fields they read — every candidate scored as if its data were always fresh and fetched cleanly. **This was fixed in this session** (`rankers/runner.py` now computes bar-age staleness and reads the batch-fetch-failure signal `ScanMonitor` already used elsewhere). Noting it here because it's a good example of the exact failure pattern this whole document is about: a real mechanism, fully implemented, silently never fed real data.

### 6. The continuous scan loop is a separate, easy-to-forget process
`vinu-screener scan` (the CLI subcommand that actually re-runs rankers on an interval, default once/day) is architecturally distinct from `vinu-screener serve` (the HTTP API). Running the API does not run the scan loop. `docker-compose.yml` only defines the API service — no `scan` worker container was found. If nobody is separately running `vinu-screener scan`, the ranked snapshots Telegram reads from are however stale the last manual run left them.

## "How much and where should it impact?" — a concrete answer

This was the open design question from the earlier conversation. Given what's actually in the codebase, the right shape (mirroring the bounded-tilt pattern already proven in vinu-portfolio's regime/outcome-confidence multipliers, and vinu-research's TradeScore calibration) is:

1. **Where**: at the point a symbol is considered for a trade plan at all — i.e., before `author_trade_plan` runs, or as an input to the LLM "screener" agent team that currently populates `TickerSummaryStore`. Not a hard gate (screener rank alone should never veto a symbol outright — that's what hard filters inside the pipeline are already for), but a size/priority *tilt*, same philosophy as everything else in this stack.
2. **How much**: `Candidate.final_score` is already a real, usable magnitude (`factor_score - risk_penalty - concentration_penalty`, `pipeline/candidate.py:29-31`) and is already present in the API's JSON payload (confirmed: Telegram's formatter reads `final_score` off the response today). A bounded tilt on position size — e.g. `±20-30%`, the same bound size used everywhere else in this codebase — keyed off a symbol's percentile rank within its last screener run, would be consistent with the rest of the system's design philosophy and wouldn't require inventing a new mechanism, just wiring one.
3. **What it should NOT do**: become a second, competing gate against vinu-research's TradeScore or vinu-portfolio's regime tilt. It should answer "does the market-wide technical picture support this symbol at all," not "should this specific trade happen" — that's TradeScore's job. Keep it as an upstream prioritization signal, not a duplicate downstream veto.

## Capabilities it should have before being trusted as a real input

In priority order (matches the shortcomings above):

1. **A real consumer.** Wire `ScreenPipeline`'s ranked output into either (a) the LLM screener agent team's context (cheapest, least new code — the team already exists and already populates the watchlist, just isn't reading this), or (b) a direct bounded size tilt as described above. Until this exists, nothing else on this list matters.
2. **Portfolio-awareness.** At minimum, pass currently-held symbols/sectors into `ScreenPipeline.run()` so the concentration overlay can penalize a candidate that's redundant with what's *already* held, not just redundant within the current ranking batch.
3. **A feedback loop.** Once a screened candidate's downstream trade plan closes (win/loss, realized return), feed that back into factor weights — same adaptive, sample-gated, human-approved pattern as TradeScore calibration. Don't reinvent the mechanism; reuse it.
4. **A guaranteed-running scan loop.** Either add `scan` as its own supervised process in `docker-compose.yml`, or fold its interval logic into `serve` so the API can't silently go stale without a human noticing.
5. **A wider data surface — eventually, not first.** News/sentiment and correlation-with-holdings matter more than order-book depth or options positioning for a system at this stage; don't chase the full "high-end screener" feature list from the earlier architecture discussion until items 1-3 are real. A screener with five signals that actually influence trading beats one with twenty that don't.

## Bottom line

vinu-screener is not under-built — it's under-connected. The fix isn't "add more signals," it's "wire the good signal that already exists into something that acts on it," then close the feedback loop the same way the rest of the system now does.
