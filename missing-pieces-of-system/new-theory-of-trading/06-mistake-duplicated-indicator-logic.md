# Mistake: hand-rolled ADX/RSI instead of reusing vinu-tools' existing library

**Priority: high.**
**Status: items 1, 2, 4, and 5 are done. Item 3 (the general rule going
forward) is a standing practice, not a one-time task -- nothing left to
close there. Every candidate indicator identified anywhere in this
design doc is now wired into `signal_evidence/compute.py` -- 51
indicators recorded per trigger event, up from the original 3.**

## What happened

While building the `signal_evidence` angle (Decision 10,
`01-planning.md`), `adx` and `rsi` were implemented from scratch inside
`vinu-initial-analysis/vinu_initial_analysis/angles/signal_evidence/
compute.py` (`_adx()`, `_rsi()` -- hand-rolled Wilder-style pandas math).

This was a mistake. `vinu-tools` (`vinu_tools/compute/indicators/`)
already has a real, tested, working **24-indicator library**, and it
already includes both:
- `vinu_tools/compute/indicators/adx/adx.py`
- `vinu_tools/compute/indicators/rsi/rsi.py`

Both are genuine Wilder-style implementations, already exercised
elsewhere in this codebase (the alpha-factor/bench/backtest machinery
described in `vinu-tools`'s own `AGENTS.md`). The hand-rolled versions
in `signal_evidence/compute.py` duplicate this logic instead of reusing
it -- exactly the kind of reinvention this whole design effort has
otherwise been careful to avoid (see, e.g., Decision 9's reasoning for
why the ticker-coverage table is a derived pivot of `RunLog` rather than
a second, independently-written copy of the same facts -- duplication
risks the two silently disagreeing over time, which is the same risk
here: a bug fixed in `vinu_tools`'s `adx`/`rsi` would never reach
`signal_evidence`'s own copies).

## Why it wasn't caught before implementing

`vinu-tools`'s indicator library wasn't checked before writing
`signal_evidence/compute.py` -- the angle was built assuming ADX/RSI
needed to be written fresh, the same way `vinu-initial-analysis`'s own
classical-statistical angles (`arima`, `garch`, `kalman_filters`) each
implement their own math directly. That assumption was wrong for this
specific case: those angles predate `vinu-tools`'s indicator library (or
compute something `vinu-tools` doesn't cover), but plain ADX/RSI is
exactly the kind of common, already-solved indicator `vinu-tools` exists
to provide.

## What was done (item 1, fixed)

`signal_evidence/compute.py`'s `_adx()`/`_rsi()` are now thin wrappers
around `vinu_tools.compute.indicators.adx.adx.compute` /
`...indicators.rsi.rsi.compute`, following the exact same bridging
pattern `drawdown_deep_dive/drawdown.py` already uses for ATR (bars ->
`to_dict("records")` rows in, named column read back out of the returned
dict, e.g. `f"adx_{period}"`). Function names/signatures at the call
sites (`_adx(high, low, close, ADX_PERIOD)`, `_rsi(close, RSI_PERIOD)`)
were kept identical so `compute()`'s body didn't need to change at all --
only the two helper bodies did. The hand-rolled Wilder math is gone
entirely; `vinu_tools`'s own (simpler EMA-based, not exact Wilder
recursion) implementation is now the only version in this codebase.

Verified: `tests/test_signal_evidence.py`'s full 8-test suite (same
engineered-crossing fixture, unchanged) passes unmodified against the new
implementation -- it only asserts indicator keys are present and outcome
values are directionally correct, not exact ADX/RSI numbers, so no test
changes were needed.

## Item 2 (done): every vinu_tools indicator checked against Section H/I

Went through all 24 modules' real source (not just names) and
cross-checked each against `all-possible-supporting-indicators.md`
Section H's exploded column list. Full breakdown recorded in Section H/I
of that file directly; summary:

- **Exact match, wired directly** (same bridging pattern as adx/rsi --
  now actually implemented in `signal_evidence/compute.py`, not just
  identified): `sma_*`, `ema_*`, `atr_14`, `roc_5/10/20`, `stoch_k_14`/
  `stoch_d_14`, `obv`, `volume_vs_avg20` (via `volume_ratio`, replacing
  the last hand-rolled rolling-mean calc in the file).
- **Available but needs a small derived step on top** (not new
  indicator math, just arithmetic on an already-computed vinu_tools
  output) -- not yet wired: `dist_from_sma_*`/`dist_from_ema_*`
  (`(price - value) / value`), `macd_histogram` (`macd` minus
  `macd_signal` -- call the shared internal `_macd()` once rather than
  both wrapper modules, to avoid recomputing EMA12/EMA26 twice),
  `bollinger_band_width`/`bollinger_percent_b` (derived from `bb_upper`/
  `bb_mid`/`bb_lower`). `vwap_dist` has a real catch: vinu_tools' `vwap`
  is cumulative-since-first-bar with no session reset -- only meaningful
  if the caller slices to the current session's bars first, a real
  decision, not just wiring.
- **Newly discovered, not previously listed in this design at all** --
  not yet wired: `cci`, `williams_r`, `supertrend`, `aroon` (up/down),
  `high_low_spread`, `open_close_return`, `momentum_n`,
  `chaikin_money_flow` (`cmf`).
- **Looks similar but isn't the same indicator, needs a decision**:
  vinu_tools' `session` module gives a categorical bucket (`asia`/
  `london`/`ny_regular`/`london_ny_overlap`/`off_hours`), a reasonable
  stand-in for `session_time_of_day`, but its row dicts need a key named
  `ts`, not `bar_ts` like every other indicator here -- a silent
  bridging trap if copied blindly. `chaikin_money_flow` is NOT the same
  indicator as the design doc's `accumulation_distribution_line` (CMF is
  a bounded rolling oscillator; A/D line is an unbounded cumulative
  running total) -- a legitimate new indicator to add, not a substitute
  for the original entry.
- **Confirmed genuinely absent from vinu_tools** (Section I's original
  "needs planning" verdict stands): Ichimoku (no module at all),
  Parabolic SAR (`supertrend` is a different, unrelated stop-and-reverse
  indicator), MFI, the true Accumulation/Distribution line. Everything
  needing external data (`iv_rank`, `beta_vs_*`, bid/ask, earnings
  calendar, VIX, etc.) is untouched by this audit -- it was never
  expected to be in the indicator library to begin with.

**What got wired as a result**: `signal_evidence/compute.py` now records
ADX, RSI, SMA(5/10/20/50/100/200), EMA(same lengths),
dist_from_sma_*/dist_from_ema_* (derived), ROC(5/10/20), ATR(14),
Stochastic %K/%D(14,3), Bollinger band width/%B (derived from
bb_upper/mid/lower), MACD line/signal/histogram (via vinu_tools' shared
internal `_macd()`, not the two separate wrapper modules, to avoid
recomputing EMA12/EMA26 twice), Aroon up/down, CCI(20), Williams %R(14),
Supertrend, high-low spread, open-close return, momentum(10), OBV,
Chaikin Money Flow(20), and volume-vs-avg20 -- all via `vinu_tools`, all
vectorized once per bar history, per-trigger values read out by position
when each row is written (column-wise compute, row-wise write, matching
Decision 1's one-row-per-trigger-event schema). That's every "readily
workable" candidate from Section H/I now actually wired, except
`vwap_dist` (deliberately held back -- `vinu_tools`' `vwap` has no
session reset, so it needs session-sliced bars to be meaningful, a real
decision not made yet) and the columns confirmed genuinely absent from
`vinu_tools` (Ichimoku, Parabolic SAR, MFI, true A/D line).

**A real bug caught and fixed while wiring this**: the multi-output
`vinu_tools` modules (`stochastic`, `bollinger`, `aroon`) only return
their whole result dict (both/all named columns at once, avoiding
redundant recomputation) when called with a `name` that doesn't match
any of their own output columns -- but doing that also makes them
silently fall back to their OWN hardcoded default params, ignoring
whatever period this angle might have configured. An earlier draft of
this wiring made those periods configurable via `get_angle_setting`
(matching this file's own established convention for adx/rsi/etc.), which
would have been a live KeyError trap the first time anyone actually
overrode one of those three settings -- caught before landing, not in
production. Fixed by making `STOCH_PERIOD`/`STOCH_SMOOTH`/
`BOLLINGER_PERIOD`/`AROON_PERIOD` plain non-overridable constants instead
(honest about what's actually happening, and Section H never asked for
multiple lengths of these anyway, unlike SMA/EMA/ROC).

Verified: `tests/test_signal_evidence.py` extended to assert every new
key is actually present in a recorded payload, all 8 tests pass.

## Item 4 (done): the 4 genuinely-absent indicators, built as real vinu_tools modules

Ichimoku, Parabolic SAR, MFI, and the true Accumulation/Distribution line
were confirmed absent from `vinu_tools` (item 2 above) -- but rather than
hand-rolling them inline inside `signal_evidence/compute.py` (which would
repeat exactly the mistake this whole file is about, just for new
indicators instead of adx/rsi), they were added to `vinu_tools` itself as
four new real modules, following its established conventions exactly:

- `vinu_tools/compute/indicators/ichimoku/ichimoku.py` -- Tenkan(9)/
  Kijun(26)/Senkou A/B(52), standard periods, no configurable params.
  Deliberately NOT forward-shifted the way a charted Ichimoku cloud
  normally displaces Senkou A/B 26 bars ahead -- this is a point-in-time
  supporting-indicator snapshot, not a chart plot, documented directly in
  the module so a future reader doesn't mistake it for a look-ahead value.
- `vinu_tools/compute/indicators/parabolic_sar/parabolic_sar.py` --
  Wilder's original algorithm (AF start/step 0.02, max 0.2).
- `vinu_tools/compute/indicators/mfi/mfi.py` -- Money Flow Index,
  parametric period (default 14), same shared meta-helper convention as
  `cci`/`williams_r`.
- `vinu_tools/compute/indicators/accumulation_distribution_line/
  accumulation_distribution_line.py` -- the real, unbounded cumulative
  A/D line, explicitly distinguished in its own docstring from
  `chaikin_money_flow` (a different, bounded-oscillator formula already
  in `vinu_tools`, not a substitute).

All four registered in `_module_names.py` (24 -> 28 indicators total --
every place that hardcoded "24" was found and updated: `vinu-tools`'
`AGENTS.md`, its own `test_feature_spec.py` assertions, and the two
vinu-agent-facing tool descriptions in `features_tool.py` and the
research idea_generator's `prompt.md`, so an LLM agent calling
`list_available_features` isn't working from a stale count). Each has
real tests in `vinu-tools/tests/test_indicators.py` (warmup gating,
value bounds/direction where meaningful) -- full `vinu-tools` suite:
154 passed.

Then wired into `signal_evidence/compute.py` the same way as every other
indicator (bars -> `to_dict("records")` rows in, named column back out,
one vectorized pass per bar history). Ichimoku's wrapper uses the same
"one call returns every column" trick as stochastic/bollinger/aroon, but
safely this time -- Ichimoku has no PARAMS at all, so there's no override
for the trick to silently diverge from (unlike the earlier stochastic/
bollinger/aroon case, which had to be fixed for exactly that reason).
Verified: `tests/test_signal_evidence.py` extended to assert all 4 new
indicators' keys are present in a recorded payload, all 8 tests pass.

## Item 5 (done): vwap_dist -- the session-slicing decision, made and wired

The last open item. `vinu_tools`' `vwap` module is cumulative-since-
first-row with no session reset, so feeding it years of history would
just produce a slow-drifting long-run average, not a meaningful "today's
VWAP" -- flagged earlier as needing a real decision before it could be
wired, not just a formula on top.

**The decision**: slice bars into per-session groups by UTC calendar
date derived from `bar_ts`, and call `vinu_tools`' real `vwap` module
independently on each slice, so every session's VWAP starts fresh from
0. This angle has no exchange-local trading-session machinery (market
open/close in a specific timezone), so a UTC calendar day is the reset
boundary used -- consistent with how `trigger_time` elsewhere in this
same file already treats `bar_ts` as UTC. Implemented as
`_vwap_supporting()` in `signal_evidence/compute.py`: reuses vinu_tools'
actual VWAP formula per session rather than reimplementing the
money-weighted average math inline.

**Verified the fix actually does what it claims**, not just that a key
shows up: a dedicated test
(`test_vwap_dist_resets_per_session_not_cumulative_since_start`)
constructs two sessions at clearly different price levels (day 1 flat at
100, day 2 flat at 200) and confirms day 2's VWAP lands near 200, not
dragged toward day 1's level the way a cumulative-since-start VWAP
would. All 9 tests in `tests/test_signal_evidence.py` pass.

**Every candidate indicator identified anywhere in this design doc is
now wired in.** `signal_evidence/compute.py` records 51 supporting
indicators per trigger event (verified directly against a real recorded
payload), up from the original 3 this file started out flagging as a
mistake.

## Item 3 (standing rule, not a task to close)

**General rule going forward, not just for this one fix**: before
   hand-implementing ANY indicator/factor math for this design, check
   `vinu_tools/compute/indicators/_module_names.py` and
   `vinu_tools/compute/registry.py` (461 alpha factors, 24 TA
   indicators, 11 recipe presets) first. This codebase already has a
   large, purpose-built library for exactly this kind of computation --
   the default assumption should be "check vinu-tools before writing
   new indicator math," not the other way around.
