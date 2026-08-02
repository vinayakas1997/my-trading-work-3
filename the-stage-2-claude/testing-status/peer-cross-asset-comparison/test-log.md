# peer-cross-asset-comparison — Test Log

**Status:** VERIFIED (2026-08-02) — Item 1 implemented (Option A, new
`peer_relative_strength` angle) and validated end-to-end on real AAPL/TSLA/JNJ
data. See "Verification results" below.

## Verification results (2026-08-02)

- **Implemented Option A**: new folder
  `vinu_initial_analysis/angles/peer_relative_strength/` (`compute.py` +
  `spec.yaml`). Auto-discovered with no registration — confirmed present via
  `GET /analysis/angles`. Rebuilt `initial-analysis-api` image to bake it in.
- **Impl detail**: reusable universe-building from `shock_clustering`, but
  emits a *continuous* 63-day rolling Pearson correlation per (sampled bar,
  peer) plus a 20-day compounded excess-return vs the equal-weight peer
  basket — not shock-date-restricted. Correlations are sampled every 5 bars
  to bound row counts on multi-year windows.
- **Data**: `POST /analysis/run/{AAPL|TSLA|JNJ}?from_ts=1640995200&to_ts=1782950400
  &angle_names=peer_relative_strength` → 639 rows each (status completed).
- **Results (real, stored, readable via `GET /analysis/angle/...`)**

  | Ticker | vs SPY | vs AAPL/TSLA peer | vs JNJ |
  |---|---|---|---|
  | AAPL | 0.63 | 0.41 (TSLA) | 0.12 |
  | TSLA | 0.57 | 0.41 (AAPL) | 0.02 |
  | JNJ | 0.15 | 0.12 (AAPL) | — |

  Correlation bounded [-1,1], varies over time (not constant across series)
  in every ticker — the rolling window is actually rolling. **JNJ is visibly
  the low-correlation outlier** vs the tech cohort (max corr to any peer
  ~0.15), exactly the "JNJ chosen to break tech correlation" expectation.
  If it had NOT differed, the computation would be suspect.

## Bug / Fix Log

### Bug-1 — `pd.to_datetime` on int64 Series misparses unix timestamps
- **Found during:** first synthetic injection test of the new
  `_to_daily_close_series` in the container; `tz_localize("UTC")` raised
  `TypeError: index is not a valid DatetimeIndex or PeriodIndex`.
- **Date:** 2026-08-02
- **Symptom:** `pd.to_datetime(int_series)` defaulted to nanosecond units and
  returned a Series, not a DatetimeIndex, breaking `.tz_localize()`.
- **Reproduction:** `compute("AAPL", bars, ..., price_client=<FakePC>)`
  inside `initial-analysis-api`.
- **Severity:** minor (impl-only, caught during dev).

### Fixed-1
- **Root cause:** `pd.to_datetime` on an int Series needs `unit="s"` (unix secs)
  and a numpy array to yield a tz-aware DatetimeIndex.
- **Fix applied:** in `_to_daily_close_series`, changed to
  `pd.to_datetime(ts.to_numpy(), unit="s").tz_localize("UTC")`.
- **Verification:** synthetic run returned sane rolling corr (MSFT-constructed
  correlated 0.95, JNJ uncorrelated ~-0.07); then real AAPL/TSLA/JNJ runs
  above.
- **Status:** fixed.

## What will be tested / Expected output

- `POST /analysis/run/{ticker}?angle_names=<new angle name>` returns
  `{"status": "completed", "row_count": N}` with `N > 0` for AAPL, TSLA,
  and JNJ (run sequentially, not concurrently).
- `GET /analysis/angle/<new angle name>/AAPL` returns correlation values
  bounded in [-1, 1], not constant across the whole series.
- JNJ (chosen in Stage 1 specifically to break the tech correlation)
  should show visibly lower correlation to AAPL/TSLA than they show to
  each other. If it doesn't, the computation is suspect, not JNJ.
- Full detail: [../../scope-responsibilities/01-peer-cross-asset-comparison.md](../../scope-responsibilities/01-peer-cross-asset-comparison.md)

## Bug / Fix Log

_Nothing logged yet — testing has not started._
