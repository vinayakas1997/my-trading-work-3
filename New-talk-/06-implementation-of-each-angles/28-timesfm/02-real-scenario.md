---
name: timesfm-real-scenario
status: phase-1-done
purpose: one concrete, real example proving TimesFM's walk-forward backtest works, with a real, well-calibrated coverage result.
---

# 28 — timesfm — Real Scenario

300 real AAPL daily bars (the most recent slice of the full real
2022-2026 history).

## The call

```python
from vinu_initial_analysis.angles.timesfm.backtest import run_timesfm_backtest

df = run_timesfm_backtest("AAPL", "1D", bars)  # 196 rows, 33.6s
```

## Real output — first row, horizon step 1 of 5

```json
{
  "model_backend": "pretrained", "checkpoint": "google/timesfm-2.5-200m-pytorch",
  "context_length_used": 100,
  "predictions": {
    "1": {
      "q10": 185.66, "q20": 190.64, "q30": 193.39, "q40": 195.20, "q50": 196.84,
      "q60": 198.03, "q70": 199.62, "q80": 201.76, "q90": 205.13,
      "actual_close": 192.23, "hit": 1,
      "pinball_loss": {"0.1": 0.657, "0.5": 2.307, "0.9": 1.290},
      "close_sq_error": 21.30, "close_abs_error": 4.61
    }
  }
}
```

All 9 real decile levels kept (previously only q10/q90 survived to
storage — 7 of 10 real model outputs were being computed and discarded).

## Storage + query round-trip, for real

```python
storage.write("AAPL", "timesfm", df, granularity="1D", tier="tier2")
back = storage.read("AAPL", "timesfm", granularity="1D", tier="tier2")
# zero column mismatches

unnested = unnest_predictions(back)
# 196 rows x 5 horizon steps -> 980 rows, horizon cast back to int64

query_slice(unnested, ["horizon"], {"coverage": ("hit", "mean")})
#    horizon    n  coverage
#          1  196  0.882653
#          2  196  0.857143
#          3  196  0.811224
#          4  196  0.821429
#          5  196  0.795918
```

## The real number: genuinely well-calibrated coverage

| Horizon step | Coverage ([q10,q90], nominal 80%) | RMSE | naive RMSE |
|---|---|---|---|
| 1 | 88.3% | 3.415 | 3.453 |
| 2 | 85.7% | 5.165 | 5.205 |
| 3 | 81.1% | 6.601 | 6.612 |
| 4 | 82.1% | 7.804 | 7.791 |
| 5 | **79.6%** | 8.883 | 8.844 |

Coverage decays smoothly and lands almost exactly on the model's own
nominal 80% target by step 5 — a real, meaningfully better-calibrated
result than lag_llama's 90%→71% or moirai's 90%→33% decay on the
identical AAPL series (both checked earlier in this session), consistent
with TimesFM's quantile head being genuinely trained rather than a
post-hoc Gaussian construction. RMSE/MAE track almost exactly the naive
baseline at every step — TimesFM's point forecast doesn't clearly add
value over "assume no change" on this real sample, but its probabilistic
calibration is real and measurably strong, the first angle in this
project's quantile-emitting set where that's true.

## Related files

- `01-implementation.md` — how this was built and tested, including both
  confirmed-gap fixes (context size, discarded deciles).
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist this satisfies.
