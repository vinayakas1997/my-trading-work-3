---
name: trend_lifecycle-real-scenario
status: phase-1-done
purpose: one concrete, real example proving the signal-outcome backtest and confidence calibration actually work, and the real (inconclusive, small-sample) calibration finding.
---

# 30 — trend_lifecycle — Real Scenario

Full real AAPL 1D history (1025 real bars, 2022-2026).

## The calls

```python
from vinu_initial_analysis.angles.trend_lifecycle.backtest import (
    run_signal_outcome_backtest, run_confidence_calibration,
)

df = run_signal_outcome_backtest("AAPL", bars, time_format="1D")  # 16 rows, 0.16s
calib = run_confidence_calibration(df)  # 2 populated buckets
```

## Real output — signal type distribution across 4 real years

```
book_profits         6
accumulate            4
re_entry               3
hold                    2
insufficient_data       1
```

## Real output — one signal-outcome row

```json
{
  "symbol": "AAPL", "bar_ts": 1648512000, "signal_type": "insufficient_data",
  "stated_confidence": 0.0, "lifecycle_stage": "sideways",
  "outcome_mature": true, "actual_subsequent_drawdown_pct": -0.2779,
  "day_of_week": "tuesday", "week_of_month": 5, "month": 3, "quarter": 1
}
```

## Real output — mature `book_profits` outcomes

| stated_confidence | stop_would_have_helped |
|---|---|
| 0.53 | True |
| 0.43 | True |
| 0.48 | False |
| 0.49 | True |
| 0.49 | False |
| 0.53 | False |

## Real output — confidence calibration

| confidence_bucket | n | actual_success_rate |
|---|---|---|
| [0.4, 0.5) | 3 | 50.0% |
| [0.5, 0.6) | 3 | 50.0% |

## Storage round-trip, for real

```python
storage.write("AAPL", "trend_lifecycle_signal_outcomes", df, granularity="1D", tier="tier2")
storage.write("AAPL", "trend_lifecycle_confidence_calibration", calib, granularity="1D", tier="tier2")
# both read back with exact row-count matches
```

## The real number: is the hand-tuned confidence formula calibrated?

Both populated buckets measured a 50% real success rate against stated
confidences in the 0.43-0.53 range — close enough that nothing here
obviously flags the formula as badly miscalibrated, but each bucket has
only **n=3** real signals over 4 years of real AAPL daily data (peak
detection with a 20-bar structural lookback is inherently selective).
Recorded honestly as **inconclusive at this sample size** — not a
validation of the formula, not a refutation either. A meaningfully larger
real sample (more symbols, a longer date range, or finer timeframes once
Phase 2 runs) would be needed before trusting this calibration curve as
a real answer.

## Related files

- `01-implementation.md` — how this was built and tested, including the
  design decision to replay lower-level building blocks directly rather
  than looping `compute()` itself.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist this satisfies.
