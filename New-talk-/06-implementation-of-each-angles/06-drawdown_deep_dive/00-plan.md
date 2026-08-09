---
name: drawdown_deep_dive-implementation-plan
status: proposed
purpose: what will actually be done to implement drawdown_deep_dive against the shared infrastructure, and how it will be checked.
---

# 06 — drawdown_deep_dive — Implementation Plan

## What the real code looks like today

`drawdown.py`'s `get_drawdowns()` already does rolling-peak tracking and
trough updates with a **fixed** threshold (`drop_threshold_pct`, code
default -3.0, not -2.0 as the design doc's summary line says — a minor
doc/code mismatch, irrelevant either way since both get replaced by
k×ATR%). It has **no recovery tracking at all** — no `recovery_ts`, no
duration, no speed, no checkpoints. `attribute_drawdown()`'s
`news_driven_pct` formula is explicitly rejected by the design doc (§7)
in favor of honest formation/recovery news counts.

This is **not** a walk-forward angle (Group B, per `Agents.md`) — and
unlike `backtesting_44_metrics`'s fixed-cadence rolling loop, it's not
even a fixed-step scan: it's a **state machine over the whole bars
series that emits a variable number of episode rows**, data-dependent,
not one row per candle.

## What I will actually do

1. **Reuse the real, existing ATR(14) indicator** —
   `vinu_tools.compute.indicators.atr.atr.compute()` — rather than
   reimplementing it. One honest note: this is a plain `SMA(true_range,
   14)`, not Wilder's exact recursive smoothing formula. The design doc's
   emphasis was on the *period* (14, "Wilder's standard convention") and
   the rolling/no-lookahead property — both satisfied by the real
   function (confirmed by reading its source: each output only uses past
   values, genuinely no lookahead). Not treated as identical to Wilder's
   formula, just close enough to what was actually decided.

2. **New `drawdown.py` function**, `detect_drawdown_episodes(symbol,
   bars, k, min_threshold_pct=-0.5)`:
   - Extends the existing rolling-peak/trough state machine with:
     `threshold_pct_used = -max(k * atr_pct_at_peak, abs(min_threshold_pct))`
     computed from the ATR at the *peak* candle (matches §4's
     `atr_pct_at_peak` field).
   - Recovery detection reuses the existing exact condition (a later
     candle's `high` exceeds the *original* peak's `high` — already
     correctly handles the "one long episode for a persistent downtrend"
     case per §7's own explanation, not something I need to redesign).
   - Once an episode's boundaries (peak_idx, final trough_idx,
     recovery_idx or "still open") are known, a second pass slices
     `bars.iloc[peak_idx:trough_idx+1]` (formation) and
     `bars.iloc[trough_idx:recovery_idx+1]` (recovery, if recovered) to
     find the first candle crossing 25/50/75% cumulative progress —
     the shape checkpoints. Can't be computed incrementally during the
     scan since the trough keeps moving until the episode closes.
   - `status: "open"` episodes (never recovered by the end of the data)
     keep their formation fields, leave every recovery field `null`.

3. **News split**: for each finalized episode, filter the already-fetched
   `news` list into `formation_news` (peak_ts ≤ ts ≤ trough_ts) and
   `recovery_news` (trough_ts ≤ ts ≤ recovery_ts, only if recovered) —
   plain timestamp filtering, no attribution-weight formula (that's
   exactly what's being replaced).

4. **k-sweep, run for real, not assumed**: the design doc's own
   "Open/unresolved" flags that the 1.5/2/2.5/3 sweep hasn't actually
   been run. `backtest.py` runs `detect_drawdown_episodes` once per k
   value in the sweep and reports whether the resulting episode
   count/avg-duration/avg-drop are stable across k — a real, measured
   answer, not deferred again.

5. **Storage shape**: one row per episode (Layer 1), tagged by `peak_ts`
   via `tag_row`. No weights store (nothing trained). Not run through
   `run_walk_forward` at all — a plain function call over the full
   `bars` DataFrame, since there's no per-step future-comparison contract
   that applies here.

6. **Widen `spec.yaml`** to the decided 6 timeframes (currently
   `15min, 1H, 1D` per the earlier per-angle discussion; the design doc
   was updated mid-session to widen this to the standard 6 — checking
   spec.yaml's current real state before assuming which one it's at).

7. **Unit tests** — synthetic OHLC series with a hand-constructed
   drawdown-then-recovery shape, checking: episode detection fires at
   the right candle, `threshold_pct_used` matches `k * atr_pct_at_peak`
   (floored), recovery fields populate correctly, an unrecovered episode
   at the end of the series gets `status: "open"` with null recovery
   fields, and shape checkpoints land on the expected candles for a
   hand-built monotonic formation/recovery.

## How I will check it

Real Alpaca data, same policy as every other angle. Given this angle
detects *rare* events (drawdowns), the usual "Phase 1 = coarsest
timeframe, ~6 months" window may simply not contain any real episodes at
some k values — that's fine and will be reported honestly (a
`n_episodes=0` result is a real, valid outcome for a calm 6-month window,
not a failure), rather than stretched into a longer window just to force
a non-empty result.

1. Real ATR(14)-as-%-of-price computed on real bars, spot-checked against
   a hand computation for one window.
2. Real detection run at k=2 (default) — report however many real
   episodes (if any) it finds, with full lifecycle fields.
3. Real k-sweep (1.5/2/2.5/3) on the same real data — report whether
   episode count/avg-duration stays stable, as a genuine measured
   finding, not assumed.
4. Storage round-trip + a real `query_slice` (e.g. avg `drop_pct` by
   `day_of_week`, carrying `n`) if any episodes exist; if zero episodes,
   this step is honestly reported as untestable on this window rather
   than faked.
5. Full test suite, both packages.
6. Write `01-implementation.md`/`02-real-scenario.md`, update `../plan.md`.

## Open items

None blocking — proceeding straight to implementation.
