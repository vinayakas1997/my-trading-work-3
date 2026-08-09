---
name: kronos-real-scenario
status: phase-1-done
purpose: one concrete, real example proving Kronos's walk-forward backtest actually works — real Alpaca data in, a real 102M-parameter financial foundation model call, real nested full-OHLC output, real storage/query round-trip.
---

# 11 — kronos — Real Scenario

Same 525 real AAPL 1-hour bars (Alpaca) used for Chronos's Phase 1 check
— deliberately the same window, for a fair side-by-side.

## The call

```python
from vinu_initial_analysis.angles.kronos.backtest import run_kronos_backtest

df = run_kronos_backtest("AAPL", "1H", bars)  # 9 real steps, ~50s total
```

## Real output — one full step

```json
{
  "symbol": "AAPL", "timeframe": "1H", "bar_ts": 1786021200, "step_index": 0,
  "session": "ny", "subsession": "premarket",
  "day_of_week": "thursday", "week_of_month": 1, "month": 8, "quarter": 3,
  "status": "ok",
  "model_backend": "pretrained", "checkpoint": "NeoQuasar/Kronos-base",
  "last_close": 314.88,
  "predictions": {
    "1": {"open": 313.36, "high": 314.51, "low": 312.12, "close": 313.46,
          "actual_close": 313.345, "predicted_direction": "down", "actual_direction": "down",
          "hit": 1, "close_sq_error": 0.0136},
    "2": {"open": 312.17, "high": 312.55, "low": 310.69, "close": 311.01,
          "actual_close": 309.55, "predicted_direction": "down", "actual_direction": "down",
          "hit": 1, "close_sq_error": 2.1312}
  }
}
```

Real, full OHLC per horizon step — not just close — genuinely forecast
by the model, not fabricated.

## Storage + `unnest_predictions` round-trip, for real

```python
storage.write("AAPL", "kronos", df, granularity="1H", tier="tier2")
# -> run_id "fc4a30cc0b81", read back: 9 rows, exact match
# nested predictions dict survives the real parquet round-trip byte-for-byte

flat = unnest_predictions(back)  # 9 rows -> 45 rows

query_slice(flat, ["horizon"], {"hit_rate": ("hit", "mean")})
#  horizon  n  hit_rate     rmse
#        1  9  0.666667  2.7176
#        2  9  0.444444  2.6115
#        3  9  0.666667  2.4410
#        4  9  0.444444  2.9658
#        5  9  0.555556  2.3981
```

Matched a hand-computed pandas `groupby` exactly.

## Naive baseline comparison (real data)

| Horizon step | naive RMSE | Kronos RMSE | Kronos better? |
|---|---|---|---|
| 1 | 1.9245 | 2.7176 | No |
| 2 | 2.2855 | 2.6115 | No |
| 3 | 1.7066 | 2.4410 | No |
| 4 | 1.7309 | 2.9658 | No |
| 5 | 1.5417 | 2.3981 | No |

Same honest pattern as ARIMA/Chronos/exponential_smoothing/iTransformer —
naive wins on this real (small, n=9) sample. Naive's RMSE values here are
identical to Chronos's own naive-baseline run on the same window — a
useful consistency check that both angles' wiring is correct.

## Related files

- `01-implementation.md` — how this was built and tested, including the
  512-context gap found in the code's own unrelated constants.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist this satisfies.
