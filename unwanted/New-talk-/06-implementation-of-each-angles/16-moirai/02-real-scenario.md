---
name: moirai-real-scenario
status: phase-1-done
purpose: one concrete, real example proving moirai's walk-forward backtest actually works, and the real measured CI-coverage decay compared against lag_llama's on identical data.
---

# 16 — moirai — Real Scenario

125 real AAPL daily bars (Alpaca, same cached dataset as lag_llama/lstm).

## The call

```python
from vinu_initial_analysis.angles.moirai.backtest import run_moirai_backtest

df = run_moirai_backtest("AAPL", "1D", bars)  # 21 rows, 0.02s
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
      "point": 273.68, "p10": 269.00, "p90": 278.36,
      "actual_close": 272.54, "hit": 1,
      "pinball_loss": {"0.1": 0.354, "0.9": 0.582},
      "close_sq_error": 1.307, "close_abs_error": 1.143
    }
  }
}
```

Only 2 quantile levels per step (`p10`/`p90`) — this angle's real code
never computes p25/p50/p75, unlike lag_llama's 5-level band.

## Storage + query round-trip, for real

```python
storage.write("AAPL", "moirai", df, granularity="1D", tier="tier2")
back = storage.read("AAPL", "moirai", granularity="1D", tier="tier2")
# every shared column matched exactly -- zero mismatches (lag_llama's own
# check found one cosmetic list-vs-ndarray artifact; moirai has no
# equivalent field)

unnested = unnest_predictions(back)
# 21 rows x 5 horizon steps -> 105 rows, horizon cast back to int64

query_slice(unnested, ["horizon"], {"coverage": ("hit", "mean")})
#    horizon   n  coverage
#          1  21  0.904762
#          2  21  0.714286
#          3  21  0.619048
#          4  21  0.428571
#          5  21  0.333333
```

## The real number: CI-coverage decay, compared against lag_llama on identical data

| Horizon step | moirai coverage (p10/p90) | lag_llama coverage (p5/p95) |
|---|---|---|
| 1 | 90.5% | 90.5% |
| 2 | 71.4% | 81.0% |
| 3 | 61.9% | 76.2% |
| 4 | 42.9% | 76.2% |
| 5 | 33.3% | 71.4% |

Both start at the same real step-1 coverage on this dataset, but
moirai's decays much faster. Two real, structural reasons, not a bug:
moirai's band is nominally narrower (80% vs. lag_llama's 90%), and its
AR(3) fit (vs. AR(5)) produces a spread-growth formula that turns out not
to actually track empirical coverage well by horizon step 4-5 on this
real data. Recorded as a genuine, honest finding about the fallback
proxy's calibration at longer horizons — not something redesigned here,
since improving the proxy's own math is out of scope for this
backtest-wiring pass (same boundary respected for lag_llama and GARCH's
own known, un-fixed issue).

## Related files

- `01-implementation.md` — how this was built and tested.
- `../12-lag_llama/02-real-scenario.md` — the directly comparable real result on identical data.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist this satisfies.
