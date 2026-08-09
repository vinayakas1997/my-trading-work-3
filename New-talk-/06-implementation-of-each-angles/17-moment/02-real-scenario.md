---
name: moment-real-scenario
status: phase-1-done
purpose: one concrete, real example proving moment's walk-forward backtest actually works, and the real measured CI-coverage/RMSE numbers.
---

# 17 — moment — Real Scenario

125 real AAPL daily bars (Alpaca, same cached dataset as lag_llama/moirai/lstm).

## The call

```python
from vinu_initial_analysis.angles.moment.backtest import run_moment_backtest

df = run_moment_backtest("AAPL", "1D", bars)  # 21 rows, 0.03s
```

## Real output — first row, horizon step 1 of 5

```json
{
  "symbol": "AAPL", "timeframe": "1D", "bar_ts": 1766966400, "step_index": 0,
  "session": "closed", "subsession": null,
  "day_of_week": "monday", "week_of_month": 5, "month": 12, "quarter": 4,
  "status": "ok", "model_backend": "fallback_proxy",
  "last_close": 273.28,
  "predictions": {
    "1": {
      "point": 273.04, "p10": 268.06, "p90": 278.03,
      "actual_close": 272.54, "hit": 1,
      "pinball_loss": {"0.1": 0.448, "0.9": 0.549},
      "close_sq_error": 0.252, "close_abs_error": 0.502
    }
  }
}
```

## Storage + query round-trip, for real

```python
storage.write("AAPL", "moment", df, granularity="1D", tier="tier2")
back = storage.read("AAPL", "moment", granularity="1D", tier="tier2")
# every shared column matched exactly -- zero mismatches

unnested = unnest_predictions(back)
# 21 rows x 5 horizon steps -> 105 rows

query_slice(unnested, ["horizon"], {"coverage": ("hit", "mean")})
#    horizon   n  coverage
#          1  21  0.857143
#          2  21  0.809524
#          3  21  0.714286
#          4  21  0.619048
#          5  21  0.666667
```

## The real number, compared against naive

| Horizon step | Coverage ([p10,p90]) | RMSE | naive RMSE | MAE | naive MAE |
|---|---|---|---|---|---|
| 1 | 85.7% | 3.245 | 3.198 | 2.246 | 2.259 |
| 2 | 81.0% | 5.184 | 5.085 | 4.191 | 3.911 |
| 3 | 71.4% | 7.611 | 7.262 | 6.410 | 6.061 |
| 4 | 61.9% | 9.776 | 9.132 | 8.470 | 8.092 |
| 5 | 66.7% | 11.906 | 10.844 | 10.129 | 9.547 |

Coverage decays overall but ticks up slightly between step 4 and 5 — with
only 21 real backtest steps, one flipped hit/miss moves the rate by ~5
points, so this is read as small-sample noise, not a real reversal.
RMSE/MAE track close to naive at every step, slightly worse throughout on
this real sample — consistent with the design doc's own framing of this
as the simplest, "bottom-of-the-barrel" comparison point among the three
fallback-proxy angles. Recorded plainly, same convention as every other
angle's real finding this session.

## Related files

- `01-implementation.md` — how this was built and tested.
- `../16-moirai/02-real-scenario.md` — the angle this one's shape was copied from.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist this satisfies.
