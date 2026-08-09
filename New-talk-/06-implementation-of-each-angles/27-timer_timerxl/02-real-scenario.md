---
name: timer_timerxl-real-scenario
status: phase-1-done
purpose: one concrete, real example proving Timer's walk-forward backtest works against the real pretrained model, at full real-history scale.
---

# 27 — timer_timerxl — Real Scenario

The full real AAPL 1D history (1025 real bars, 2022-2026) — Timer's low
per-call cost made this affordable at full scale, unlike Chronos's much
more limited real sample.

## The call

```python
from vinu_initial_analysis.angles.timer_timerxl.backtest import run_timer_timerxl_backtest

df = run_timer_timerxl_backtest("AAPL", "1D", bars)  # 921 rows, 15.25s
```

## Real output — first row, horizon step 1 of 5

```json
{
  "model_backend": "pretrained", "checkpoint": "thuml/timer-base-84m", "n_patches": 1,
  "predictions": {
    "1": {
      "point": 139.04, "p10": 135.26, "p90": 142.83,
      "actual": 140.75, "hit": 1, "in_band": 1,
      "close_sq_error": 2.908, "close_abs_error": 1.705
    }
  }
}
```

`model_backend: "pretrained"` confirmed on every real row — the real
84M-param Timer model, not the fallback proxy.

## Storage + query round-trip, for real

```python
storage.write("AAPL", "timer_timerxl", df, granularity="1D", tier="tier2")
back = storage.read("AAPL", "timer_timerxl", granularity="1D", tier="tier2")
# zero column mismatches

unnested = unnest_predictions(back)
# 921 rows x 5 horizon steps -> 4605 rows, horizon cast back to int64

query_slice(unnested, ["horizon"], {"hit_rate": ("hit", "mean"), "coverage": ("in_band", "mean")})
#    horizon    n  hit_rate  coverage
#          1  921  0.498371  0.747014
#          2  921  0.489685  0.731813
#          3  921  0.490771  0.742671
#          4  921  0.494028  0.723127
#          5  921  0.501629  0.713355
```

## The real number: the largest real sample of any angle this session

| Horizon step | Directional accuracy | CI-coverage (nominal 80%) | RMSE | naive RMSE |
|---|---|---|---|---|
| 1 | 49.8% | 74.7% | 4.125 | 3.288 |
| 2 | 49.0% | 73.2% | 5.565 | 4.744 |
| 3 | 49.1% | 74.3% | 6.990 | 5.917 |
| 4 | 49.4% | 72.3% | 8.137 | 6.843 |
| 5 | 50.2% | 71.3% | 9.224 | 7.621 |

921 real walk-forward steps (vs. 21-25 for most other angles checked this
session) — a genuinely larger, more statistically meaningful real sample.
Directional accuracy sits essentially at coin-flip across every horizon
step; the post-hoc p10/p90 band's coverage runs consistently below its
nominal 80% target (a finding about the *bolted-on* statistical spread's
calibration, not the real model's own confidence — Timer has no native
uncertainty output, per the design doc's explicit caveat). RMSE/MAE both
consistently worse than the naive baseline at every step. Recorded
plainly — a real, honest result on this project's own equity data,
distinct from (and not directly comparable to) the source paper's own
benchmark universe.

## Related files

- `01-implementation.md` — how this was built and tested, including the
  MIN_OBSERVATIONS/patch-size fix and the spec.yaml correction.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist this satisfies.
