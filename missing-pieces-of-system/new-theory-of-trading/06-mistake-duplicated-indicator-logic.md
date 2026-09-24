# Mistake: hand-rolled ADX/RSI instead of reusing vinu-tools' existing library

**Priority: high.**
**Status: not fixed yet -- this file records the mistake and what needs
to be done.**

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

## What needs to be done

1. **Refactor `signal_evidence/compute.py`** to call `vinu_tools`'s real
   `adx`/`rsi` modules instead of `_adx()`/`_rsi()`. Interface
   difference to bridge: `vinu_tools`'s `compute(rows: list[dict], *,
   name: str) -> dict[str, list[float | None]]` takes a list of row
   dicts (not a pandas Series), so this needs `bars.to_dict("records")`
   (or equivalent) at the call site, then reading the named output
   column back out of the returned dict. Delete `_adx()`/`_rsi()` once
   the replacement is verified against the existing test suite
   (`tests/test_signal_evidence.py`) -- same engineered-crossing fixture,
   same assertions, just backed by the real library instead of the
   hand-rolled math.
2. **Re-check the REST of `all-possible-supporting-indicators.md`'s
   Section I ("readily workable") against `vinu-tools`'s indicator list
   before wiring anything else in.** The list of 24
   (`vinu_tools/compute/indicators/_module_names.py`) already covers
   `sma`, `ema`, `macd`, `macd_signal`, `atr`, `bollinger`, `stochastic`,
   `obv`, `vwap`, `volume_ratio`, `roc`, `chaikin_money_flow`, `aroon`,
   plus a few not yet listed in this design at all (`cci`,
   `williams_r`, `supertrend`, `momentum_n`, `session`,
   `high_low_spread`, `open_close_return`, `daily_return`,
   `volatility_20d`). Section I currently describes most of Section
   B/C as "buildable with new pandas code" -- that's now known to be
   wrong for most entries; they should say "reuse `vinu_tools`" instead,
   and the newly-noticed extra indicators (`cci`, `williams_r`,
   `supertrend`, `aroon`, `session`) should probably be added to Section
   H/I as additional candidate columns not previously listed at all.
3. **General rule going forward, not just for this one fix**: before
   hand-implementing ANY indicator/factor math for this design, check
   `vinu_tools/compute/indicators/_module_names.py` and
   `vinu_tools/compute/registry.py` (461 alpha factors, 24 TA
   indicators, 11 recipe presets) first. This codebase already has a
   large, purpose-built library for exactly this kind of computation --
   the default assumption should be "check vinu-tools before writing
   new indicator math," not the other way around.
