# vinu-strategy — Test Log

**Status:** Not started (YAMLs exist, containers not up yet)

## What will be tested

Only the **easy** and **medium** tiers — the complex tier does not run
through `vinu-strategy` at all (see
[../../scope-responsibilities/vinu-strategy.md](../../scope-responsibilities/vinu-strategy.md)
and [../vinu-research/test-log.md](../vinu-research/test-log.md)).

- `GET /strategies` lists `e2e_easy_sma_crossover` and
  `e2e_medium_trend_vol_filter`.
- `POST /strategies/e2e_easy_sma_crossover/evaluate` and
  `POST /strategies/e2e_medium_trend_vol_filter/evaluate` for AAPL, TSLA,
  JNJ across the Stage 1 date range, pulling real features (`vinu-tools`)
  and correlation/regime context (`vinu-initial-analysis`).
- `GET /weights` history retrieval for both strategies.
- Risk constraints: `VINU_STRATEGY_MAX_WEIGHT` (0.25) and
  `VINU_STRATEGY_CASH_FLOOR` (0.10) are actually enforced, not just
  configured.
- Medium tier's rule stack specifically: `weak_trend_halve`,
  `elevated_volatility_halve`, `high_vol_regime_halve`, and `bear_exit`
  firing correctly and in the right order (rules apply sequentially, so
  order matters).

## Expected output

- Both strategies produce weights that respect `MAX_WEIGHT` and
  `CASH_FLOOR` on every rebalance date, for all 3 tickers.
- Easy tier weights change only on actual 20/50 SMA crossover events —
  spot-checkable against the raw price series.
- Medium tier weights visibly tilt down during high-volatility periods
  and low-ADX (weak trend) periods; TSLA should trigger the volatility
  rule more often than JNJ given its typically higher baseline
  volatility — if it doesn't, that's worth checking the
  `volatility_20d gt 0.03` threshold (see the known gap in
  `vinu-strategy.md`).
- Bear-regime exit (`weight_set: 0.0`) fires identically in both
  strategies when `regime_analysis.regime == "bear"`.

## Bug / Fix Log

### Bug-1 — container crash-loops on startup, can't write its meta DB

- **Found during:** first `docker compose up -d --build` of the full stack.
- **Date:** 2026-07-31
- **Symptom:** `strategy-api` crash-loops. Logs show
  `OSError: [Errno 30] Read-only file system: '../data'`,
  `ERROR: Application startup failed. Exiting.`
- **Reproduction:** `docker compose up -d` then `docker compose logs strategy-api`.
- **Suspected cause:** `vinu-components/.env` sets
  `VINU_STRATEGY_DATA_ROOT=../data/strategy` — a local-dev-style relative
  path overriding the Dockerfile's correct default
  (`ENV VINU_STRATEGY_DATA_ROOT=/data`). Same shared host-directory-permission
  issue as [../vinu-stock-price/test-log.md](../vinu-stock-price/test-log.md)'s
  Bug-1 also applies here.
- **Severity:** blocker.

### Fixed-1

- **Root cause:** confirmed via `docker compose logs strategy-api` —
  same shared cause as
  [../vinu-stock-price/test-log.md](../vinu-stock-price/test-log.md)'s
  Fixed-1.
- **Fix applied:** `vinu-components/.env`'s `VINU_STRATEGY_DATA_ROOT`
  changed from `../data/strategy` to `/data`; host-directory ownership
  fixed via the shared `chown -R 100:101` fix.
- **Verification:** `docker compose ps` → `strategy-api ... (healthy)`,
  no tracebacks in `docker compose logs strategy-api`.
- **Status:** fixed.

Prerequisite for the actual strategy-evaluation tests above: real feature
data from `vinu-tools` and real correlation/regime data from
`vinu-initial-analysis`, which both need `vinu-stock-price` (and
`vinu-news` for the latter) populated first.
