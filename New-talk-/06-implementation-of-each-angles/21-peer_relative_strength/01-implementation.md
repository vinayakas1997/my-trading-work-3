---
name: peer_relative_strength-implementation
status: phase-1-done
purpose: the real record of implementing peer_relative_strength's backtest and the proposed forward-return validation enhancement.
---

# 21 — peer_relative_strength — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/peer_relative_strength/backtest.py` | New | `run_relative_strength_backtest()` (existing raw rows, tagged day-of-week/week/month/quarter only — no session/subsession) + `run_forward_return_validation()` (the design doc's proposed enhancement: joins each row to its own forward 5/10/20-day return, aggregates Pearson correlation + bootstrapped CI per peer×quarter). |
| `vinu-initial-analysis/vinu_initial_analysis/angles/_helpers.py` | Edited | Added `calendar_quarter_key()` (moved out of news_price_causality/backtest.py's local copy, now shared) and `pearson_with_ci()` (generalized from news_price_causality/correlation.py's bootstrap technique, per the design doc's explicit "same method already used" instruction). |
| `vinu-initial-analysis/vinu_initial_analysis/angles/news_price_causality/backtest.py` | Edited | `_quarter_key` now imports the shared `calendar_quarter_key` instead of defining its own copy — no behavior change, just de-duplication now that a second angle needs the identical function. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/peer_relative_strength/spec.yaml` | Edited | `time_formats` widened from `[1D]` to the decided 6. |
| `vinu-initial-analysis/tests/test_peer_relative_strength_backtest.py` | New | 4 tests. |

## How it was implemented

Group B, and structurally unlike any angle built so far: `compute.py`
already produced real, correct output (one row per symbol×peer×sampled
date, 63-day rolling correlation + 20-day relative return) — no bug to
fix, no refactor needed to `compute.py` itself. The actual work was the
design doc's own proposed enhancement: **forward-return validation**,
turning the existing descriptive rows into a tested signal by checking
whether `relative_return_20d` (or correlation) says anything about what
the stock actually does next.

`run_forward_return_validation` reuses `compute()`'s existing output
plus `_aligned_closes()` (already a private module-level helper in
`compute.py`, imported directly the same way other angles' backtest.py
files import private `_fit_and_forecast`/etc. helpers) to compute each
row's actual forward N-day return via `.shift(-N)` on the aligned daily
close series, then groups by (peer, real calendar quarter) and runs
`pearson_with_ci()` — genuinely shared infrastructure now, not
angle-specific: this is the same bootstrap-CI technique
`news_price_causality/correlation.py` already used, generalized into
`_helpers.py` per the design doc's own explicit instruction to reuse it
rather than reinvent it. `calendar_quarter_key()` was also promoted to
`_helpers.py` at the same time, since news_price_causality's own
`backtest.py` had a near-identical local `_quarter_key` — de-duplicated
rather than left as two copies that could silently drift.

Tagging deliberately drops `session`/`subsession` (the design doc's
explicit call: one row already = one trading day's computation, no
intraday dimension to tag) — implemented by filtering `_tagging.tag_row`'s
output down to the 4 date-only fields, not by hand-rolling a second
tagging function.

## Testing

4 new tests, synthetic data with a fake `price_client` (`get_watchlist`/
`get_candles`) providing 2 synthetic peers over 400 synthetic trading
days. Covers: date-only tagging (no session/subsession columns present),
`insufficient_data` status at exactly the rolling-window floor, forward-
return correlations bounded in [-1,1] with valid CI ordering, empty
output when there are no peers at all.

**Real-data validation (Phase 1: `1D`)**: real AAPL as the symbol, real
TSLA + JNJ as peers (the only 3 symbols with cached price data in this
project; MSFT/GOOGL aren't cached) — full real 1D history (2022-01→2026,
1025 real trading days) → 394 relative-strength rows in 0.04s, 32
forward-return-validation (peer, quarter) buckets in 0.22s. Storage
round-trip verified for both outputs (zero mismatches), `query_slice`'s
grouped average-correlation-by-peer matched a hand pandas `groupby`
exactly (JNJ: 0.128, TSLA: 0.414).

**A second real, pre-existing data-corruption instance found**: JNJ's
own `live/2026_20260309.parquet` is truncated, identical failure
signature to AAPL's `known-issues.md` entry from angle 14 — updated
that entry rather than opening a new one, since this confirmed the
pattern was systemic (a live-ingest atomicity gap), not a one-off. Worked
around at the time by loading archive+live parquet directly via pandas,
excluding both known-bad files. **Since fixed in a dedicated pass**
(`known-issues.md` Resolved #3 — atomic writes + resilient per-file
reads + the corrupt files deleted after a full-cache audit found a third
instance on TSLA); the workaround above is no longer necessary for future
runs.

**Real finding — mostly no significant forward-return predictability on
this real sample**: across all 32 (peer, quarter) buckets, almost every
forward-return correlation (5/10/20-day) came back non-significant
(p > 0.1) — 2 of the 96 (32 buckets × 3 horizons) real combinations
crossed p<0.05 (2023-Q1's 10-day, 2023-Q3's 20-day), consistent with
chance alone across that many comparisons, not a real signal. This is a
genuine, honest negative result, exactly the kind the design doc
anticipated as a real possible outcome ("could just as easily come back
near-zero") — not evidence the methodology is broken, evidence that on
this particular real sample (2 peers, ~4 years, AAPL) relative strength/
co-movement doesn't detectably predict forward returns at these
horizons. A larger peer basket and more data would be needed before
drawing a stronger conclusion either way.

**A real bug found and fixed in `pearson_with_ci` itself, discovered
later while implementing angle 24 — corrected here retroactively**: the
bootstrap CI computed above was originally always the degenerate
`[-1, 1]` regardless of real correlation strength or sample size (a
`scipy.stats.bootstrap` un-paired-resampling mistake, not a data issue —
full diagnosis in `known-issues.md` #1/Resolved). This implementation
record originally attributed the wide CIs to small per-quarter sample
size; that attribution was wrong. Fixed in `_helpers.py`
(`paired=True` resampling), and this angle's real numbers above were
re-run with the fix — the qualitative finding (no real forward-return
predictability) is unchanged, but the CI bands themselves are now real
and informative (e.g. `[0.21, 0.85]` for 2023-Q1's 10-day correlation,
not `[-1.0, 1.0]`).

**Full `vinu-initial-analysis` suite**: 320 passed (up from 316
pre-this-angle — the 4 new tests), 2 skipped, the same 11 pre-existing
`shock_clustering`/`shock_personality` failures (as of this angle's own
turn — `shock_clustering`'s 3 were later fixed in angle 24, see that
angle's own pass count), no new failures.

## Related files

- `02-real-scenario.md` — the real example (corrected CI numbers).
- `../plan.md` — overall status table.
- `../known-issues.md` — updated corrupt-parquet-file entry (now confirmed on 2 symbols) and the `pearson_with_ci` bootstrap-CI fix (#1/Resolved).
- `../24-shock_clustering/01-implementation.md` — where the `pearson_with_ci` bug was actually found and fixed.
- `../../04-enhancement-of-each-angle/21-peer_relative_strength.md` — the decided design.
