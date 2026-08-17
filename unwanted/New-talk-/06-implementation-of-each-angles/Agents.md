---
name: implementation-of-each-angles-agent-instructions
status: decided
purpose: self-contained, step-by-step instructions for implementing any one of the 31 angles against the shared backtest infrastructure — written so an agent with no memory of prior sessions can pick up exactly one angle and finish it correctly, without re-deriving decisions already made.
---

# Agents.md — How to Implement One Angle

You are implementing exactly one angle from the table below. Read this
whole file before touching code — most of the mistakes it warns about
were made once already and are cheap to avoid the second time.

## Before you start

Read, in this order:

1. `04-enhancement-of-each-angle/{NN}-{name}.md` — the decided design for
   *this specific angle*. Its §3 (decided parameters) has the real
   `min_observations`, refit cadence, horizon, and any timeframe changes
   decided for it — these are not always the same as DLinear's, and not
   always the same as what `spec.yaml` currently says (see "Known
   gotchas" below).
2. `05-storage-enhancement-levels/plan.md` — what the shared infrastructure
   is and where it lives.
3. `05-storage-enhancement-levels/angle-validation-checklist.md` — the
   real-data checklist you must pass before this angle counts as done.
4. The real existing code at
   `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/{name}/`
   — `compute.py`/`spec.yaml` and any submodules. Read it directly; don't
   assume the design doc's description of "what the code does today" is
   still current.
5. `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/dlinear/backtest.py`
   and `compute.py` — the one finished, proven example. Group A angles
   follow this shape closely; Group B angles follow it loosely (see below).

## Real data source and validation window (decided)

This supersedes the `yfinance`-based approach used for DLinear's original
check — confirmed working end to end, use this for every angle from here on.

- **Provider: Alpaca**, not `yfinance`. Credentials live in
  `alpaca-details/details.md` (`API-KEY`, `SECRET-API-KEY`,
  `MARKET-DATA-URL=https://data.alpaca.markets/v2`). Treat them as
  sensitive: read them from that file at request time, never print them,
  never paste them into `01-implementation.md`/`02-real-scenario.md` or
  any other committed file. Confirmed working with a real request —
  `GET {MARKET-DATA-URL}/stocks/{SYMBOL}/bars?timeframe=1Min&start=...&end=...&feed=iex`,
  headers `APCA-API-KEY-ID`/`APCA-API-SECRET-KEY`. One format gotcha
  already hit: pass `start`/`end` as `%Y-%m-%dT%H:%M:%SZ`, not Python's
  default `.isoformat()` output (which includes a `+00:00` offset Alpaca's
  API rejects with a 400).
- **Fetch 1-minute bars only, then derive every other timeframe by
  aggregation** — the same real path production uses. Import
  `aggregate_bars`/`interval_to_seconds` from
  `vinu-stock-price/vinu_stock/query/aggregate.py` (it natively supports
  `5m/15m/30m/1h/4h/1d/1wk/1mo/6mo`, including `4h`, which most providers
  don't offer natively) and run every declared timeframe through it from
  one real 1-minute pull, rather than requesting each timeframe from
  Alpaca separately.
- **Validation window: ~6 months of real 1-minute data**, for every
  angle, every timeframe — confirmed available on this account's feed
  (checked 6 months back, real bars returned, no gap). This replaces the
  earlier per-timeframe window table built around `yfinance`'s much
  shorter intraday history limits (7 days for 1min, 60 days for 5min/
  15min) — those limits don't apply to Alpaca, so there's no reason to
  shrink the window per timeframe anymore. One 6-month 1-minute fetch
  covers every timeframe this angle declares.
- **Symbols for anything cross-symbol: AAPL and SPY, fixed.** Any angle
  whose design involves a relationship between symbols (correlation,
  relative strength, peer comparison, multi-ticker fusion once that's in
  scope) uses this same pair every time, decided once here rather than
  picked ad hoc per angle — so results are comparable across angles that
  each look at the same pair from a different angle (pun unavoidable).
  Single-symbol angles keep using AAPL alone, consistent with DLinear's
  check.
- **Two-phase timeframe checking (decided after ARIMA's real runtimes came
  in).** A full 6-month real-data check across every declared timeframe is
  expensive for any angle that refits a model per step — ARIMA's own
  numbers: 1D 14.7s, 4H 106.7s, 1H 421s, 15min 459s, and 5min/1min slower
  still. Running all of that for all 31 angles before making any progress
  isn't the right trade. Split into two phases instead:
  - **Phase 1 (do this for every angle, in order)**: run the real-data
    checklist only against the **coarsest 1-2 timeframes the angle
    declares** — `1D` when it's declared (it almost always is and is
    always cheap), plus the next-coarsest declared one if `1D` isn't
    available or isn't alone enough to be convincing (e.g.
    `drawdown_deep_dive` declares `15min, 1H, 1D` with no `4H` — use `1D`
    there, `1H` as the second if wanted). This proves the angle's own
    wiring (tags, hit definition, storage, query) works — that's what
    changes per angle. It does **not** re-prove the shared harness itself,
    which DLinear and ARIMA already did.
  - **Phase 2 (deferred, tracked, not skipped)**: come back later and run
    the remaining declared timeframes for every angle in one pass, now
    that Phase 1 has gotten real implementations in place for all of them.
    Record which timeframes are Phase-1-checked vs. still-pending in each
    angle's `01-implementation.md` so this isn't silently forgotten.
- **The API round-trip is part of the check, not optional.** After
  writing a real backtest's output through `AngleStorage`, actually read
  it back (`read_latest`/`read`) and run at least one real `query_slice`
  — confirm the data you get back matches what you wrote, not just that
  `write()` didn't raise. This is checklist items 5-6 in
  `angle-validation-checklist.md`, restated here because it's easy to
  treat "it wrote without error" as sufficient when it isn't.

## The four groups — which procedure applies

Check `plan.md`'s status table for this angle's group before writing any
code — the two groups need genuinely different implementations, not just
different parameters.

**Group A (walk-forward forecaster, e.g. arima, lstm, tft)** — follow
DLinear's shape:
1. If the angle trains a model, split its existing `compute.py` so the
   trained model object is returned alongside the result fields (see
   DLinear's `_fit_and_forecast`) — `compute()`'s own external behavior
   must stay unchanged; only add an internal seam.
2. Write `angles/{name}/backtest.py`: a `{name}_step(step: WalkForwardStep) -> StepResult`
   function with the angle's actual forecast/hit logic, and a
   `run_{name}_backtest(...)` function that wires `tag_row`, a
   `WeightsStore`-saving closure (only if the angle trains a model), and
   `run_walk_forward(...)` with this angle's own decided
   `min_observations`/`horizon`/`refit_cadence` from its design doc.
3. If the angle's hit definition isn't simple direction-match (e.g. ARIMA's
   CI-coverage), implement that comparison inside `{name}_step` — the
   shared harness has no opinion on what a "hit" means, that's entirely
   the angle's own logic.

**Group B (not a forecaster, e.g. shock_clustering, pnl_attribution)** —
do **not** force this into `run_walk_forward`. Read the angle's own design
doc §5 (storage/querying/API shape) for what its actual output looks like,
and use whichever shared pieces genuinely apply:
- `_tagging.tag_row` almost certainly still applies (every stored row
  still benefits from consistent session/day/week/quarter tags).
- `AngleStorage`/`RunLog` still apply (still writing tier2/tier3 parquet
  through the same storage class).
- `query.py`'s `query_slice`/`unnest_predictions` still apply if the
  angle's results get grouped/aggregated later.
- The walk-forward *loop* itself, and the weights store, likely don't
  apply — these angles aren't training a model at every step or scoring a
  rolling one-step-ahead forecast. Don't invent a fake `step_fn` just to
  reuse the harness; write whatever loop or one-shot computation the
  angle's own design doc actually describes.

**Group C (deferred)** — don't implement. If you've been asked to work on
`cross_attention_gcn_news_price_fusion` specifically, stop and check with
whoever assigned it — its own design doc says the prerequisite (real
multi-ticker training) doesn't exist yet.

**Group D (redundant, no work planned)** — don't implement. `ml_model_pipeline`
and `news_first_analysis` are intentionally left as-is.

## The procedure, step by step

1. Implement the code (per the group-specific guidance above).
2. Write unit tests in `tests/test_{name}_backtest.py` (or extend the
   existing `tests/test_{name}.py`), matching the existing style — real
   objects, `tempfile.TemporaryDirectory()`, no mocking. Cover at minimum:
   correct row count, tags matching standalone `tag_row`, and (Group A
   only) weights round-tripping to a model that reproduces its own
   recorded forecast.
3. Run the real-data validation checklist
   (`05-storage-enhancement-levels/angle-validation-checklist.md`) for
   **every** timeframe this angle's design doc decided on (check §3 —
   don't just use whatever `spec.yaml` currently says; see "Known
   gotchas"). Fetch real data per "Real data source and validation window
   (decided)" above — Alpaca, 1-minute bars, aggregated to every declared
   timeframe, ~6 months, AAPL (+ SPY for cross-symbol angles) — and run
   all 7 checklist items, including the API round-trip (write, read back,
   query).
4. Run the full test suite for both `vinu-initial-analysis` and
   `vinu-tools` (`python -m pytest -q` in each package root). Confirm no
   *new* failures — the pre-existing `shock_clustering`/`shock_personality`
   `KeyError: 'bar_ts'` failures are tracked separately and don't block you,
   but anything else failing that wasn't failing before your change is
   your bug to find, not to ignore.
5. Create `06-implementation-of-each-angles/{NN}-{name}/` and write:
   - `01-implementation.md` — real files touched (new vs. edited), how it
     was actually implemented, what was tested and how, and any bugs
     found and fixed along the way. Follow `05-dlinear/01-implementation.md`'s
     level of detail once it exists, or `05-storage-enhancement-levels/implementation-summary.md`
     in the meantime.
   - `02-real-scenario.md` — one concrete real example: the real function/
     API call you made, a small real data sample, and the real output that
     came back. This is the proof-of-work, not a description of what
     should happen.
6. Update `plan.md`'s status table (folder link + status) for this angle.

## Known gotchas (already hit once — don't re-hit them)

- **`weights_sink` takes 4 arguments, `WeightsStore.save` takes 5.** The
  harness has no concept of `angle_name`; every angle's own glue code must
  wrap the save call in a small closure that binds its own name (see
  DLinear's `_save_weights` in `backtest.py`). Passing `weights_store.save`
  directly to `weights_sink=` will crash on the first call.
- **`spec.yaml`'s current `time_formats` may be stale.** Several design
  docs decided to widen an angle's timeframes (e.g. beyond the `1D`-only
  most angles currently declare in real code); if this angle's design doc
  §3 decided a different set than `spec.yaml` currently has, update
  `spec.yaml` as part of this implementation — don't validate against the
  old, narrower list and call it done.
- **Daily (or coarser) bars always tag `session="closed"`** — a midnight
  UTC timestamp never lands inside a real trading session. That's correct
  behavior, not a bug, but it means a `session`-grouped query example for
  a 1D-only angle is a meaningless artifact; use `day_of_week`/`month`/
  `quarter` for those instead. Only intraday timeframes get real
  session/subsession variation.
- **A naive intraday data fetch can silently return regular-hours-only
  bars.** First caught with `yfinance` (which excludes pre/post-market
  data unless you pass `prepost=True`) — Alpaca's IEX feed does include
  premarket/afterhours trades by default, but still double-check the
  session/subsession distribution on any new fetch (like
  `02-real-scenario.md`'s intraday example does) rather than assuming —
  don't let a check "pass" while only ever exercising `ny/markethours`.
- **`min_observations` is decided per angle, not copied from DLinear.**
  DLinear's is 100 because its own design doc says so; don't assume every
  other angle's is also 100 — check that angle's own §3.

## Per-angle lookup table

`time_formats (current)` is what the real `spec.yaml` declares today —
check the angle's own design doc §3 for whether that's also the decided
target or needs widening as part of this work.

| # | Angle | Group | Design doc | Code | `time_formats` (current) |
|---|---|---|---|---|---|
| 01 | arima | A | [04-enhancement-of-each-angle/01-arima.md](../04-enhancement-of-each-angle/01-arima.md) | `angles/arima/` | 1D |
| 02 | backtesting_44_metrics | B | [02-backtesting_44_metrics.md](../04-enhancement-of-each-angle/02-backtesting_44_metrics.md) | `angles/backtesting_44_metrics/` | 1D, 1W, 1M, 6M |
| 03 | chronos | A | [03-chronos.md](../04-enhancement-of-each-angle/03-chronos.md) | `angles/chronos/` | 1D |
| 04 | cross_attention_gcn_news_price_fusion | C | [04-cross_attention_gcn_news_price_fusion.md](../04-enhancement-of-each-angle/04-cross_attention_gcn_news_price_fusion.md) | `angles/cross_attention_gcn_news_price_fusion/` | 1D |
| 05 | dlinear | A | [05-dlinear.md](../04-enhancement-of-each-angle/05-dlinear.md) | `angles/dlinear/` | 1D |
| 06 | drawdown_deep_dive | B | [06-drawdown_deep_dive.md](../04-enhancement-of-each-angle/06-drawdown_deep_dive.md) | `angles/drawdown_deep_dive/` | 15min, 1H, 1D |
| 07 | exponential_smoothing | A | [07-exponential_smoothing.md](../04-enhancement-of-each-angle/07-exponential_smoothing.md) | `angles/exponential_smoothing/` | 1D |
| 08 | garch | A | [08-garch.md](../04-enhancement-of-each-angle/08-garch.md) | `angles/garch/` | 1D |
| 09 | itransformer | A | [09-itransformer.md](../04-enhancement-of-each-angle/09-itransformer.md) | `angles/itransformer/` | 1D |
| 10 | kalman_filters | A | [10-kalman_filters.md](../04-enhancement-of-each-angle/10-kalman_filters.md) | `angles/kalman_filters/` | 1D |
| 11 | kronos | A | [11-kronos.md](../04-enhancement-of-each-angle/11-kronos.md) | `angles/kronos/` | 1D |
| 12 | lag_llama | A | [12-lag_llama.md](../04-enhancement-of-each-angle/12-lag_llama.md) | `angles/lag_llama/` | 1D |
| 13 | lpatchtst | A | [13-lpatchtst.md](../04-enhancement-of-each-angle/13-lpatchtst.md) | `angles/lpatchtst/` | 1D |
| 14 | lstm | A | [14-lstm.md](../04-enhancement-of-each-angle/14-lstm.md) | `angles/lstm/` | 1D |
| 15 | ml_model_pipeline | D | [15-ml_model_pipeline.md](../04-enhancement-of-each-angle/15-ml_model_pipeline.md) | `angles/ml_model_pipeline/` | 1D, 1W, 1M |
| 16 | moirai | A | [16-moirai.md](../04-enhancement-of-each-angle/16-moirai.md) | `angles/moirai/` | 1D |
| 17 | moment | A | [17-moment.md](../04-enhancement-of-each-angle/17-moment.md) | `angles/moment/` | 1D |
| 18 | news_first_analysis | D | [18-news_first_analysis.md](../04-enhancement-of-each-angle/18-news_first_analysis.md) | `angles/news_first_analysis/` | 15min, 1H, 1D |
| 19 | news_price_causality | B | [19-news_price_causality.md](../04-enhancement-of-each-angle/19-news_price_causality.md) | `angles/news_price_causality/` | 1min, 15min, 1H, 1D |
| 20 | patchtst | A | [20-patchtst.md](../04-enhancement-of-each-angle/20-patchtst.md) | `angles/patchtst/` | 1D |
| 21 | peer_relative_strength | B | [21-peer_relative_strength.md](../04-enhancement-of-each-angle/21-peer_relative_strength.md) | `angles/peer_relative_strength/` | 1D |
| 22 | pnl_attribution | B | [22-pnl_attribution.md](../04-enhancement-of-each-angle/22-pnl_attribution.md) | `angles/pnl_attribution/` | 1D |
| 23 | regime_analysis | B | [23-regime_analysis.md](../04-enhancement-of-each-angle/23-regime_analysis.md) | `angles/regime_analysis/` | 1D, 1W, 1M |
| 24 | shock_clustering | B | [24-shock_clustering.md](../04-enhancement-of-each-angle/24-shock_clustering.md) | `angles/shock_clustering/` | 1D |
| 25 | shock_personality | B | [25-shock_personality.md](../04-enhancement-of-each-angle/25-shock_personality.md) | `angles/shock_personality/` | 1D |
| 26 | tft | A | [26-tft.md](../04-enhancement-of-each-angle/26-tft.md) | `angles/tft/` | 1D |
| 27 | timer_timerxl | A | [27-timer_timerxl.md](../04-enhancement-of-each-angle/27-timer_timerxl.md) | `angles/timer_timerxl/` | 1D |
| 28 | timesfm | A | [28-timesfm.md](../04-enhancement-of-each-angle/28-timesfm.md) | `angles/timesfm/` | 1D |
| 29 | tips_regime_aware_transformer | A | [29-tips_regime_aware_transformer.md](../04-enhancement-of-each-angle/29-tips_regime_aware_transformer.md) | `angles/tips_regime_aware_transformer/` | 1D |
| 30 | trend_lifecycle | B | [30-trend_lifecycle.md](../04-enhancement-of-each-angle/30-trend_lifecycle.md) | `angles/trend_lifecycle/` | 15min, 1H, 4H, 1D |
| 31 | trend_session_structure | B | [31-trend_session_structure.md](../04-enhancement-of-each-angle/31-trend_session_structure.md) | `angles/trend_session_structure/` | 15min, 1H, 4H |

## Related files

- `plan.md` — the overview, the group definitions, the build order, and
  the live status table (update it when you finish an angle).
- `05-storage-enhancement-levels/plan.md` and `angle-validation-checklist.md`
  — the shared infrastructure and the real-data checklist referenced
  throughout this file.
