# vinu-screener: shortfall, gaps, and upgrade path

Written 2026-09-14 (original audit), updated 2026-09-15 after two implementation
rounds closed several of the gaps below. Everything is grounded in the actual
code (file:line citations from direct investigation), not assumption — where
something is still uncertain or deliberately deferred, it's marked as such.

**Status: partially complete (`(pcomp)`).** vinu-screener now has a real
strategy, a real automated consumer, a sizing tilt, and held-symbol
awareness — all implemented and tested. What's still missing is listed in
full under [Pending](#pending--not-yet-built).

## What vinu-screener actually is today

`vinu-screener` is a candidate ticker screening/ranking pipeline (`vinu_screener/pipeline/pipeline.py`'s `ScreenPipeline`, driven by `vinu_screener/rankers/runner.py`'s `RankerRunner`):

1. Fetch OHLCV for a configured universe of symbols (`vinu_screener/scan/data_source.py`, via `vinu-stock-price`).
2. Compute configured factors (`FactorSpec` — real registered indicators: `pct_change`, `rsi`, `sma`, `ema`, `slope`, `macd`, etc. via `IndicatorFactory`; no indicator literally named "momentum" exists).
3. Apply a hard filter (binary pass/fail on bounds).
4. Score survivors with a weighted factor sum (`factor_score`).
5. Apply a risk overlay (bounded additive penalties — momentum-chase, breakdown, abnormal volume, stale/degraded data, **and now already-held**, see below).
6. Apply a concentration overlay (penalize picking too many symbols from the same sector *within this batch* — still batch-only, see Pending).
7. Rotate near-score ties for stability, optionally gate turnover.
8. Return a ranked list, top-N highlighted.

It also has a separate rule-based `ScanMonitor` (`vinu_screener/scan/monitor.py`) that fires condition-based alerts (not ranking) on a schedule, and a `serve` HTTP API plus a `scan` CLI loop for continuous ranker re-runs — **`scan` is already backgrounded automatically inside the same container** (`vinu-screener/entrypoint.sh` runs `vinu-screener scan &` before `exec vinu-screener serve`), a correction to the original audit below.

## RESOLVED: it now feeds the live loop

The original core finding was that nothing automatically consumed vinu-screener's ranked output. This is now fixed, in two independent, ships-inert pieces:

- **A real recipe exists.** `vinu_screener/rankers/seed.py`'s `seed-default` CLI command (wired into `entrypoint.sh`, idempotent) creates a `core_starter` ranker on first boot: a curated ~50-ticker starter universe (not the full ~8000-symbol catalog, see Pending), three real factors (`pct_change` short/medium momentum, a mild `rsi` overbought penalty), and sane price/liquidity hard filters. The universe list is **not baked into the Docker image** — it's read from an optional JSON file at `VINU_SCREENER_SEED_CONFIG` (default: the same host-mounted `/data` volume the ranker DB already lives in), falling back to the built-in default if that file doesn't exist.
- **A real automated consumer exists.** `vinu-agent`'s watchlist-bootstrap mechanism (`agent/scheduler_workers.py`'s `discover_new_tickers`/`bootstrap_new_tickers`) now has a second seed source alongside the static operator list: when `VINU_AGENT_SCREENER_RANKER_ID` is set, `vinu_agent/tools/screener_client.py` pulls the screener's current top-N and merges it in. New symbols get bootstrapped into `TickerSummaryStore` exactly like a manually-tracked ticker. Ships inert — unset the env var and behavior is byte-for-byte unchanged from before this existed.

The old "confusingly same-named" note still holds: the LLM-driven "screener" agent *team* inside vinu-agent (`agent/team.py`) is a separate mechanism from `vinu_screener`'s `ScreenPipeline` — the wiring above connects them, but they remain architecturally distinct pieces.

## Where it now impacts trading (implemented)

The original "how much and where should it impact" design question is now answered concretely, not just theoretically:

- **Discovery** (implemented, see above): screener rank influences *which new tickers* enter the watchlist.
- **Position sizing** (implemented): `vinu-research/vinu_research/trade_plan_authoring.py` now has a `_screener_rank_size_multiplier` — a symbol's percentile rank in the screener's latest run nudges `TradePlan.position_size_pct` by a bounded ±30% (`config.screener_rank_size_tilt_bound`, same shape as the existing regime tilt), composed multiplicatively alongside the existing TradeScore-tier and regime multipliers. Ships inert (`config.screener_ranker_id` empty by default); fails open to neutral 1.0 on any fetch problem. This is exactly the "upstream prioritization signal, not a duplicate veto" design the original audit called for — it never gates a trade, only sizes it.
- **Not a gate**: as originally specified, screener rank still never competes with or overrides vinu-research's TradeScore gate or vinu-portfolio's regime tilt — it only ever tilts size.

## Shortcomings — updated status

### 1. ~~No automated downstream consumer~~ — RESOLVED
See "RESOLVED: it now feeds the live loop" above.

### 2. Zero portfolio-awareness — PARTIALLY RESOLVED
`RankerRunner.run()` now accepts `held_symbols: frozenset[str]`, fetched from vinu-agent's real broker positions (`vinu_screener/rankers/holdings_client.py`) once per scheduler tick. A held symbol gets a modest risk-overlay penalty (`already_held`, 5.0 points, not a veto) — reuses the existing `RiskCheck` mechanism, no new pipeline stage. **This is held-SYMBOL awareness, not held-SECTOR awareness** — a real scoping decision, not an oversight: no service in this codebase joins real positions with sector data anywhere (vinu-agent's `Position` and vinu-portfolio's `weights` both carry `symbol`, never `sector`). Sector-level concentration against real holdings (the original ask) stays unbuilt — see Pending. Ships inert (`VINU_AGENT_API_URL` empty by default).

### 3. No feedback loop — factor weights are static forever — STILL PENDING, DELIBERATELY
Unchanged from the original finding, and explicitly not attempted in either implementation round: this needs real closed trade outcomes from screener-sourced picks to exist before there's anything to tune against or any way to honestly test a weight-adjustment mechanism. Building a "dormant" version now would be speculative code nothing can verify. See Pending for the intended shape once real data exists.

### 4. Narrow data surface — OHLCV only — STILL PENDING
Unchanged. Still no news/sentiment/fundamentals/options/order-book signal wired in; the risk overlay's `llm_confidence`/`llm_risk_flag`/`deep_analysis_risk_flag` fields remain inherited placeholders, never populated.

### 5. ~~Data-quality risk checks were dead code~~ — RESOLVED (pre-existing fix, unrelated to this round)
Already fixed in the session that produced the original audit (`data_stale`/`data_fetch_degraded` now genuinely computed in `runner.py`). Kept here for the historical record of the exact failure pattern this whole doc is about.

### 6. ~~The continuous scan loop is a separate, easy-to-forget process~~ — CORRECTED, not actually a gap
The original audit's claim was wrong: `vinu-screener/entrypoint.sh` already backgrounds `vinu-screener scan &` inside the same container `serve` runs in — confirmed by reading the file directly during round 1's implementation. No docker-compose change was needed.

## Pending / not yet built

In rough priority order:

1. **Feedback loop + weight tuning.** Once a screener-sourced pick's trade closes (win/loss), feed that back into `FactorSpec.weight` — same adaptive, sample-gated, human-approved pattern as `vinu-research`'s TradeScore calibration (`compute_calibration_metrics`, `min_sample=30` gate). Requires real trading history first; explicitly not started.
2. **Sector-level concentration against real holdings.** The concentration overlay still only diversifies *within one ranking batch* — it has no idea what's already held. Requires a new sector-tagging data source somewhere in the system (doesn't exist today for any service), a materially bigger piece of work than the held-symbol version already built.
3. **Wider universe.** `core_starter`'s ~50-ticker list is a deliberate starting subset, not the real ~8000-symbol catalog. Widening it means solving the "don't pay for full history on symbols nobody wants" problem first — `CoarseFilter`/`coarse_select` exists (`scan/universe.py`) but is only wired into the separate `ScanMonitor`, never the ranker path. DSA (the repo this design was ported from) solves this with one cheap "whole-market snapshot" API call from China-market providers (Sina/Tushare/AkShare) vinu-stock-price has no equivalent of; Polygon (already a configured provider here) has a comparable "grouped daily bars" endpoint that could fill this role later — noted, deliberately not built, since vinu-stock-price is being kept untouched for now per explicit direction.
4. **Wider data surface.** News/sentiment and correlation-with-holdings matter more than order-book depth or options positioning for a system at this stage — still nothing wired.

## Bottom line

vinu-screener is no longer purely "under-connected" — it has a real recipe, a real discovery consumer, and a real (if narrow) sizing/risk influence on actual trades, all shipping inert until explicitly configured. What's left is real trading history (for the feedback loop) and two genuinely separate, bigger pieces of infrastructure (sector-tagging, a cheap full-market data source) — not more wiring of what already exists.
