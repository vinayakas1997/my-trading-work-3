# All possible supporting indicators

Every one of these gets snapshotted as a raw-value column at the moment
a must-condition fires (per Decision 1 in `01-planning.md`). No
selection/filtering here — the point is to record everything available
and let Layer 4's analysis decide later which ones actually separate
outcomes.

## A. Already computed — the 28 angles (`vinu-initial-analysis`)

These already run per symbol on their own cycle; nothing new to build,
just snapshot their latest output at trigger time.

- `shock_personality`
- `shock_clustering`
- `trend_lifecycle`
- `trend_session_structure`
- `regime_analysis`
- `drawdown_deep_dive`
- `pnl_attribution`
- `peer_relative_strength`
- `news_price_causality`
- `garch` (volatility)
- `kalman_filters`
- `arima`
- `exponential_smoothing`
- `chronos`
- ~~`moirai`~~ — **excluded (Decision 5)**: permanently pinned to a
  statistical `fallback_proxy`, never real pretrained weights (its
  `uni2ts` package needs `torch==2.4.1`, conflicting with the shared
  `torch==2.13.0+cpu` install). Not merely deprioritized.
- `timesfm`
- `tips_regime_aware_transformer`
- `patchtst`
- `lpatchtst`
- `itransformer`
- `lstm`
- `dlinear`
- `tft`
- ~~`moment`~~ — **excluded (Decision 5)**: same reason, permanently on
  a statistical fallback proxy, not real pretrained weights.
- `kronos`
- ~~`lag_llama`~~ — **excluded (Decision 5)**: same reason, permanently
  on a statistical fallback proxy, not real pretrained weights.
- `timer_timerxl`
- `backtesting_44_metrics`

## B. Classic price/trend indicators

- SMA / EMA of various lengths (e.g. 5, 10, 20, 50, 100, 200), and price
  distance from each
- ADX(14) — trend strength
- MACD (line, signal, histogram)
- RSI(14)
- Stochastic oscillator
- Bollinger Band width / %B
- ATR(14) — volatility
- Rate of change (ROC) over multiple lookbacks
- Ichimoku cloud components (Tenkan, Kijun, Senkou spans)
- Parabolic SAR

## C. Volume / participation indicators

- Volume relative to N-day average (e.g. vol / avg_volume_20)
- On-balance volume (OBV)
- Volume-weighted average price (VWAP) distance
- Accumulation/distribution line
- Money flow index (MFI)

## D. Volatility / risk-state indicators

- Realized volatility (multiple lookbacks)
- Implied volatility / IV rank (if options data available)
- CVaR / tail-risk estimate (already used as a gate in `vinu-live`'s
  entry chain — worth also recording, not just gating on)
- Beta / correlation to index or sector over trailing window
- GARCH-forecast volatility (from angle A above)

## E. Market microstructure / liquidity

- Bid-ask spread — **live-only for now.** Confirmed against
  `vinu-stock-price/vinu_stock/providers/quote.py`: `AlpacaQuoteProvider`
  only fetches the *latest* NBBO quote (used today for the live liquidity
  gate), no historical bid/ask series is pulled or stored. Can be
  snapshotted going forward for new trigger events, but can't be
  backfilled for past ones until a historical quote data source exists.
  High-low range remains a usable proxy for the historical rows in the
  meantime.
- Order book depth / imbalance (if available) — same live-only caveat
- Slippage estimate at current size
- Borrow availability / cost (for shorts)

## F. Market context / regime

- Time of day / session (open, mid-day, close)
- Day of week
- Distance to next earnings/news event
- Broad market regime state (risk-on/risk-off, VIX level or equivalent)
- Sector/peer relative strength (angle A above)
- Correlation regime (DCC/shrinkage covariance, already computed in
  `vinu-live`'s `_check_runtime_correlation`)

## G. Strategy/meta context

- Which must-condition(s) fired (if a strategy has more than one)
- How many candles since the must-condition first fired (relevant once
  the grace-window mechanism exists)
- Current portfolio exposure / correlation to existing open positions
  at trigger time
- Broker/account state (degraded, halted) at trigger time

## H. The complete, exploded column list

Sections B-G above describe each indicator compactly (e.g. "SMA/EMA of
various lengths"), but each concrete variant becomes its own column when
actually wired in — per the earlier discussion, one column per
individual term, not one shared column per family. This section is that
explosion, written as the literal column name each one would use. `✅`
marks columns implemented in `signal_evidence/compute.py` today (exact
key names, not renamed here) — all via `vinu_tools`' real indicator
library, never hand-rolled (see
`06-mistake-duplicated-indicator-logic.md`). Everything else is still
just a candidate, not yet wired into any angle.

**From B — classic price/trend:**
- `sma_5`, `sma_10`, `sma_20`, `sma_50`, `sma_100`, `sma_200` ✅
  (implemented — `sma_100`/`sma_200` will simply be absent for triggers
  early in a ticker's history that don't have 100/200 bars yet)
- `ema_5`, `ema_10`, `ema_20`, `ema_50`, `ema_100`, `ema_200` ✅ (implemented)
- `dist_from_sma_5`, `dist_from_sma_10`, `dist_from_sma_20`,
  `dist_from_sma_50`, `dist_from_sma_100`, `dist_from_sma_200` ✅
  (implemented, derived from the `sma_*` columns above:
  `(price - sma_N) / sma_N`)
- `dist_from_ema_5`, `dist_from_ema_10`, `dist_from_ema_20`,
  `dist_from_ema_50`, `dist_from_ema_100`, `dist_from_ema_200` ✅
  (implemented, same derivation from `ema_*` above)
- `adx` ✅ (implemented, ADX(14), via `vinu_tools`)
- `macd_line`, `macd_signal`, `macd_histogram` ✅ (implemented — via
  `vinu_tools`' shared internal `_macd()`, not the two separate wrapper
  modules, so EMA12/EMA26 aren't computed twice; histogram is
  `macd_line - macd_signal`)
- `rsi` ✅ (implemented, RSI(14), via `vinu_tools`)
- `stoch_k`, `stoch_d` ✅ (implemented as `stoch_k_14`/`stoch_d_14`, via
  `vinu_tools`' `stochastic` module — period/smooth deliberately NOT
  configurable, see the note on this below)
- `bollinger_band_width`, `bollinger_percent_b` ✅ (implemented, derived
  from `vinu_tools`' `bollinger` module's `bb_upper`/`bb_mid`/`bb_lower`:
  `(upper-lower)/mid`, `(close-lower)/(upper-lower)` — period likewise
  not configurable)
- `atr_14` ✅ (implemented, via `vinu_tools`, same module
  `drawdown_deep_dive/drawdown.py` already uses)
- `roc_5`, `roc_10`, `roc_20` ✅ (implemented, via `vinu_tools`)
- `ichimoku_tenkan`, `ichimoku_kijun`, `ichimoku_senkou_a`,
  `ichimoku_senkou_b` ✅ (implemented — was NOT in `vinu_tools`, so a
  real new `ichimoku` module was added there first, following its own
  conventions, rather than hand-rolled inline; standard 9/26/52 periods,
  values NOT forward-shifted the way a charted cloud normally is, since
  this is a point-in-time snapshot not a chart plot)
- `parabolic_sar` ✅ (implemented — also added to `vinu_tools` as a new
  module, Wilder's original algorithm. `vinu_tools`' pre-existing
  `supertrend` is a genuinely different indicator, not a substitute for
  real Parabolic SAR, hence the new module)

**New candidates found while auditing `vinu_tools` (not previously
listed anywhere in this design) — all now implemented:**
- `cci_20`, `williams_r_14`, `supertrend`, `aroon_up`/`aroon_down`,
  `high_low_spread`, `open_close_return`, `momentum_10` ✅ (all
  implemented, via `vinu_tools`)
- `cmf_20` ✅ (implemented, Chaikin Money Flow — a bounded rolling
  oscillator, a legitimate new indicator but NOT the same as
  `accumulation_distribution_line` below, which is an unbounded
  cumulative running total using a different formula)

**A configurability trap caught while wiring `stoch_k`/`stoch_d`,
`bollinger_*`, and `aroon_*`**: `vinu_tools`' multi-output modules only
return every named column from one call (avoiding redundant
recomputation) when called with a name that matches none of their own
columns — but that also makes them silently use THEIR OWN hardcoded
default params, ignoring any period this angle might configure. Making
`STOCH_PERIOD`/`BOLLINGER_PERIOD`/`AROON_PERIOD` overridable via
`get_angle_setting` (matching this file's own convention for adx/rsi)
would have been a live KeyError the first time anyone actually changed
one of those settings. Fixed by leaving those three as plain,
non-overridable constants — honest about what the single-call
optimization actually computes, and Section H never asked for multiple
lengths of these anyway (unlike SMA/EMA/ROC).

**From C — volume/participation:**
- `volume_vs_avg20` ✅ (implemented, now via `vinu_tools`' `volume_ratio`
  module, replacing the last hand-rolled rolling-mean version)
- `obv` ✅ (implemented, via `vinu_tools`)
- `vwap_dist` ✅ (implemented — bars sliced into per-session groups by
  UTC calendar date from `bar_ts` before calling `vinu_tools`' `vwap`
  module independently per slice, so each session gets its own VWAP
  starting from 0 rather than drifting cumulative-since-first-bar; see
  `06-mistake-duplicated-indicator-logic.md` item 5)
- `accumulation_distribution_line` ✅ (implemented — also added to
  `vinu_tools` as a new module, explicitly distinguished in its own
  docstring from `chaikin_money_flow`/`cmf_20` above, which is a
  different, bounded-oscillator formula, not a substitute)
- `mfi_14` ✅ (implemented — also added to `vinu_tools` as a new module,
  same parametric-period convention as `cci`/`williams_r`)

**From D — volatility/risk-state:**
- `realized_vol_10`, `realized_vol_20`, `realized_vol_60`
- `iv_rank` (only if options data becomes available)
- `cvar_95`
- `beta_vs_index`, `beta_vs_sector`
- (GARCH-forecast volatility is already covered as the whole `garch`
  angle column in Section A — not duplicated here as its own column)

**From E — market microstructure/liquidity** (live-only until a
historical quote source exists, per Section E's own note):
- `bid_ask_spread`
- `order_book_imbalance`
- `slippage_estimate`
- `borrow_cost`

**From F — market context/regime:**
- `session_time_of_day`
- `day_of_week`
- `days_to_next_earnings`
- `days_to_next_news_event`
- `market_regime_state`
- `vix_level`
- `correlation_regime_dcc`
- (peer/sector relative strength is already covered as the whole
  `peer_relative_strength` angle column in Section A)

**From G — strategy/meta context:**
- `must_condition_name` (already a fixed schema field on every row, per
  Decision 1 — listed here for completeness, not a new column to add)
- `candles_since_trigger`
- `portfolio_exposure_pct`
- `correlation_to_open_positions`
- `broker_degraded_flag`
- `trading_halted_flag`

## I. Readily workable vs. needs planning

"Readily workable" means: computable today using tools/data this
codebase already has internally (bars already fetched, or an existing
internal module already doing the calculation) — the same pattern
`adx`/`rsi`/`volume_vs_avg20` already used, no new external data source
and no new mechanism required. "Needs planning" means it's blocked on
something that doesn't exist internally yet — a new read capability
(`read_as_of()`, still deferred), a live-only data path with no
historical source, or a data feed this codebase has no evidence of
having at all (checked directly, not assumed).

### Readily workable (bars + existing internal tools only)

**Confirmed audited against `vinu_tools`' real 24-indicator library, not
assumed** (see `06-mistake-duplicated-indicator-logic.md` item 2) — most
of Section B/C turned out to already exist there, ready to reuse rather
than build:

**All of the below is now implemented in `signal_evidence/compute.py`**
— every candidate indicator identified in this file, nothing left unwired:

- **Wired directly via `vinu_tools`, zero new math**: `sma_*`, `ema_*`,
  `adx`, `rsi`, `stoch_k`/`stoch_d`, `atr_14`, `roc_5`/`10`/`20`, `obv`,
  `volume_vs_avg20`.
- **Wired via a small derived step on top of a `vinu_tools` output**
  (arithmetic on an already-computed value, not new indicator math):
  `dist_from_sma_*`/`dist_from_ema_*`, `macd_line`/`macd_signal`/
  `macd_histogram`, `bollinger_band_width`/`bollinger_percent_b`.
- **Wired via a real design decision, not just a formula** (see
  `06-mistake-duplicated-indicator-logic.md` item 5): `vwap_dist` —
  `vinu_tools`' `vwap` has no session reset, so bars are sliced into
  per-session groups (by UTC calendar date from `bar_ts`) before calling
  it, giving each session its own VWAP.
- **Wired, newly discovered while auditing `vinu_tools`** (wasn't
  previously listed in this design at all): `cci_20`, `williams_r_14`,
  `supertrend`, `aroon_up`/`down`, `high_low_spread`,
  `open_close_return`, `momentum_10`, `cmf_20`.

**`realized_vol_10`/`20`/`60`** (Section D) — plain rolling return
volatility, bars only.

**`cvar_95`** (Section D) — confirmed a real, existing internal module
already does this computation: `vinu-tools/vinu_tools/compute/risk/
value_at_risk.py`. Not yet reused for this purpose, but the calculation
itself doesn't need building from scratch.

**`beta_vs_index`/`beta_vs_sector`** (Section D) — needs another
symbol's bars (an index/sector proxy), but `vinu-stock-price`'s
`get_candles` already fetches bars for any symbol string, not just the
one being analyzed — an extra internal fetch, not a new external source.

**`market_regime_state`** (Section F) — confirmed a real, existing
module: `vinu-research/vinu_research/market_regime_analogue.py`'s
`get_market_regime_stats_for_today()`. Reuse, not new work.

**`vix_level`** (Section F) — likely workable the same way as
`beta_vs_index` (just another symbol fetched via `get_candles`), IF the
price provider actually carries a VIX-equivalent symbol — not
independently confirmed, flagged here rather than assumed.

**`session_time_of_day`, `day_of_week`, `candles_since_trigger`**
(Sections F/G) — derivable directly from `bar_ts`, no lookup needed at
all. `vinu_tools` also has a `session` module giving a categorical
bucket (`asia`/`london`/`ny_regular`/`london_ny_overlap`/`off_hours`) as
a ready-made alternative to a hand-rolled time-of-day bucketing — note
its row dicts need a key named `ts`, not `bar_ts` like every other
indicator wired so far, a silent bridging trap if copied blindly.

**`correlation_regime_dcc`** (Section F) — the calculation already runs
inside `vinu-live`'s `_check_runtime_correlation`; reusing it here means
extracting/calling that existing logic, not inventing new math.

### Needs planning (blocked on something that doesn't exist yet)

**All 25 active angle columns (Section A)** — blocked on `read_as_of()`
not existing yet (the point-in-time-safe historical read discussed
above). Deferred by explicit decision, not forgotten.

**~~`ichimoku_tenkan`/`kijun`/`senkou_a`/`senkou_b`, `parabolic_sar`,
`mfi_14`, `accumulation_distribution_line`~~ — no longer blocked, now
implemented** (see `06-mistake-duplicated-indicator-logic.md` item 4).
These were confirmed genuinely absent from `vinu_tools`' original
24-indicator library, so real new modules were added there (following
its own conventions) rather than hand-rolled inline in the angle —
`vinu_tools` is now a 28-indicator library.

**`iv_rank`** (Section D) — needs options data. No evidence anywhere in
this codebase (`vinu-stock-price`, `vinu-news`, or elsewhere) of an
options data source at all — checked directly, found nothing. A real
external dependency, not just unwired.

**`bid_ask_spread`, `order_book_imbalance`, `slippage_estimate`,
`borrow_cost`** (Section E) — confirmed live-only earlier in this same
file (Section E's own note): no historical quote/order-book/execution
source exists, so these can only ever be populated for triggers
happening from now forward, never backfilled.

**`days_to_next_earnings`** (Section F) — needs an earnings calendar
feed. Checked `vinu-stock-price` and `vinu-news` directly for one —
nothing found. A real external dependency.

**`days_to_next_news_event`** (Section F) — `vinu-news` does fetch news
articles already, so this is closer to workable than
`days_to_next_earnings`, but needs a small amount of new logic (finding
the nearest future news timestamp relative to a historical trigger,
which itself needs care not to leak look-ahead the same way angle
outputs do) — not zero-effort, kept here rather than the workable list
until that's thought through.

**`portfolio_exposure_pct`, `correlation_to_open_positions`,
`broker_degraded_flag`, `trading_halted_flag`** (Section G) — all
depend on live broker/account/position state (`vinu-live`/`vinu-agent`'s
broker module). Meaningless for historical backfill by definition (a
past trigger has no "current open positions" to speak of) — these only
become real once the live detector exists, so they're blocked on that,
not on anything in this file's own scope.
