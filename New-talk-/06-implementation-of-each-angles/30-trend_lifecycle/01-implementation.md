---
name: trend_lifecycle-implementation
status: phase-1-done
purpose: the real record of building the signal-outcome backtest and confidence-calibration check this angle's design doc proposed, on top of its already-sound peak-detection and KNN-matching core.
---

# 30 — trend_lifecycle — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/trend_lifecycle/backtest.py` | New | `run_signal_outcome_backtest()` (replays every real historical peak as "the current peak," generates the leak-free signal `compute()` would have produced, joins it to that peak's own real, already-known subsequent outcome) + `run_confidence_calibration()` (buckets those outcomes by stated confidence, reports real measured success rate per bucket). |
| `vinu-initial-analysis/vinu_initial_analysis/angles/trend_lifecycle/spec.yaml` | Edited | `time_formats` gained `1W` (the confirmed config gap — the code's own internal `_MIN_PEAK_DROP_PCT`/`_LOOKAHEAD_BARS` dicts already had a `1W` entry never exposed) and `1min`/`5min` (per the design doc's "Decided parameters" table, which explicitly lists all 6 standard timeframes plus 1W as the final value — see the note below on a table/prose inconsistency found in the design doc itself). |
| `vinu-initial-analysis/tests/test_trend_lifecycle_backtest.py` | New | 4 tests. |

## A documentation inconsistency found, not a code bug (third instance this session)

Same pattern already found in `shock_personality`'s design doc: SS3's
"Decided parameters" table explicitly lists the final timeframe value as
"1min, 5min, 15min, 1H, 4H, 1D, 1W" and says it "supersedes the earlier
decision to deliberately exclude 1min/5min" — but §7's rationale prose
still argues "Why 1min/5min are deliberately not added," with the
tick-noise reasoning that decision predates. Followed the table (the
explicitly-marked final decided value) over the unsynced prose, same
resolution rule applied to `shock_personality`'s identical situation.
This is now a confirmed *pattern*, not a one-off — worth naming since a
third occurrence suggests whatever batch process widened these tables to
the standard 6 systematically didn't re-sync the prose underneath in
every file it touched.

## How it was implemented

Group B, and the first angle this session with a genuinely
**self-accumulating, stateful** design (`compute()` reads its own prior
output back from `AngleStorage` via a global `load_config()` call to
grow its pattern library across runs) rather than a stateless
computation over a bars window. This ruled out the most obvious
approach — replaying `compute()` itself step-by-step through an
expanding window — since `compute()`'s storage/config coupling is
process-global, not parameter-injectable, and forcing that open for an
isolated backtest would have been fragile.

Instead, `backtest.py` calls the same lower-level building blocks
`compute()` itself calls (`detect_peaks`, `capture_all_peaks`,
`find_similar`, `classify`, `generate_signals`) directly against the
full real `bars`, once. This is possible without introducing a leak
specifically because the *real, already-correct* walk-forward safety in
this codebase lives in `find_similar`'s `before_ts` argument, not in an
external temporal loop — passing each peak's own `bar_ts` as `before_ts`
reproduces exactly what `compute()` would have shown a user at that
moment in time, for every historical peak, without needing to actually
re-run detection/capture from scratch at every point in history.
Verified this understanding is correct by confirming `capture_all_peaks`'
own `drawdown_pct`/`outcome_mature` fields are computed by scanning
*forward* through the same real `bars` from each peak's own index — a
peak's own recorded future outcome, never fed into an *earlier* signal's
matching (that's what `before_ts` blocks).

`stop_would_have_helped` (a `book_profits` signal's real usefulness) is
defined as: the real subsequent drawdown was worse than the suggested
exit threshold (`actual_subsequent_drawdown_pct < suggested_exit_pct`,
both negative numbers) — i.e. taking the suggested stop would have
locked in a better result than holding through the real move.
`would_have_stopped_early` is the milder companion check (whether the
real drop reached the suggested level at all, not necessarily worse than
holding to the end).

## A small retroactive addition, made while implementing angle 31

`run_signal_outcome_backtest`'s output rows didn't originally carry the
peak snapshot's own `session` field (trend_lifecycle's native
premarket/regular/afterhours/closed taxonomy, distinct from the shared
calendar-tagging scheme's own session concept) — added once angle 31
(`trend_session_structure`), which explicitly depends on it for its own
proposed per-session confidence-calibration breakdown, needed it. A
one-line addition (`snap.get("session")` was already in scope), not a
design change.

## Testing

4 new tests, a real deterministic-ish swinging synthetic price series
(sine wave + trend + noise — guarantees multiple genuine peaks/troughs
of varying shape, not identical repeats). Covers: tagged rows present
with the right shape (no `session` column, date-only tags — matching the
existing 1D-scope tagging convention already used by
`peer_relative_strength`/`regime_analysis`/`shock_personality`), every
mature `book_profits` row has a real, non-null outcome, empty input on
no detected peaks, calibration buckets carry `n` and a bounded success
rate, and a real bug caught in my own first draft: `run_confidence_calibration`
crashed on a genuinely empty DataFrame with no columns (`KeyError:
'signal_type'`) — fixed with an explicit empty/no-columns guard before
the `groupby`.

**Real-data validation (Phase 1: `1D`)**: full real AAPL 1D history
(1025 real bars) → 16 real signal rows in 0.16s (structural peak
detection with a 20-bar lookback is inherently selective — only 16
qualifying peaks over ~4 years of real daily data). 6 real `book_profits`
signals, all with mature (fully known) real outcomes. Storage round-trip
verified for both new outputs (`trend_lifecycle_signal_outcomes`,
`trend_lifecycle_confidence_calibration`, zero mismatches, same
distinct-angle-name-suffix convention as `backtesting_44_metrics`/
`news_price_causality`/`regime_analysis`).

**Real finding — the confidence formula looks roughly reasonable on this
small real sample, but the sample is too thin to trust strongly**: the
two populated confidence buckets ([0.4,0.5) and [0.5,0.6)) both measured
a 50% real success rate against stated confidences of ~0.43-0.53 — close
enough to not obviously flag the formula as badly miscalibrated, but
each bucket has only n=3 real signals, far too few to draw a real
conclusion from. Recorded honestly as inconclusive on this sample size,
not as either a validation or a refutation of the hand-tuned formula —
exactly the kind of real, measured (if statistically weak) answer this
enhancement was built to produce, consistent with the design doc's own
framing that the calibration result "is a real, measured finding once
this backtest runs, not assumed."

**Full `vinu-initial-analysis` suite**: run after this angle; see
`../plan.md`'s status table entry for the pass count.

## Related files

- `02-real-scenario.md` — the real example.
- `../plan.md` — overall status table.
- `../../04-enhancement-of-each-angle/30-trend_lifecycle.md` — the decided design.
