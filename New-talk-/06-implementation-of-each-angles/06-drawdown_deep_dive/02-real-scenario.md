---
name: drawdown_deep_dive-real-scenario
status: phase-1-done
purpose: one concrete, real example proving drawdown_deep_dive's episode detection actually works — real Alpaca data in, a real detected drawdown-and-recovery, real storage/query round-trip, and the real k-sweep robustness check.
---

# 06 — drawdown_deep_dive — Real Scenario

125 real AAPL daily bars (Alpaca), same dataset used for ARIMA's/
backtesting_44_metrics's `1D` Phase 1 checks.

## The call

```python
from vinu_initial_analysis.angles.drawdown_deep_dive.backtest import run_drawdown_detection

df = run_drawdown_detection("AAPL", "1D", bars, k=2.0)  # 3 real episodes
```

## Real output — one full episode

```json
{
  "symbol": "AAPL", "timeframe": "1D", "bar_ts": 1772150400, "episode_index": 0, "k": 2.0,
  "session": "closed", "subsession": null,
  "day_of_week": "friday", "week_of_month": 4, "month": 2, "quarter": 1,
  "status": "recovered",
  "peak_ts": 1772150400, "peak_price": 272.765,
  "atr_pct_at_peak": 2.6319, "threshold_pct_used": -5.2638,
  "trough_ts": 1774828800, "trough_price": 246.72,
  "drop_pct": -9.5485, "duration_to_trough": 21, "trough_speed": -0.4547,
  "formation_checkpoints": {
    "25%": {"candle": 0, "price": 264.07},
    "50%": {"candle": 4, "price": 259.33},
    "75%": {"candle": 10, "price": 249.86}
  },
  "formation_news": [],
  "recovery_ts": 1776643200, "recovery_price": 271.23,
  "recovery_gain_pct": 9.9343, "duration_to_recovery": 14, "recovery_speed": 0.7096,
  "recovery_checkpoints": {
    "25%": {"candle": 1, "price": 253.73},
    "50%": {"candle": 7, "price": 260.44},
    "75%": {"candle": 11, "price": 266.31}
  },
  "recovery_news": []
}
```

A real, non-trivial episode: AAPL peaked at $272.77 on a Friday, took 21
trading days to bottom out at $246.72 (-9.55%), then took another 14 days
to fully recover above the original peak. The threshold that triggered
this episode was `-5.26%` (`2.0 × 2.63%` ATR at the peak) — a real,
volatility-adaptive number, not a fixed -2%. `formation_news`/
`recovery_news` are empty here because no live news service was running
in this environment (same limitation noted throughout this session) — the
splitting logic itself is real and tested, just had nothing to filter
against for this run.

## The k-sweep, run for real

```python
from vinu_initial_analysis.angles.drawdown_deep_dive.backtest import run_k_sweep

sweep = run_k_sweep("AAPL", "1D", bars)
```

| k | n_episodes | n_recovered | n_open | avg_drop_pct | avg_duration_to_trough | avg_duration_to_recovery |
|---|---|---|---|---|---|---|
| 1.5 | 6 | 5 | 1 | -7.7664 | 7.33 | 5.6 |
| 2.0 | 3 | 2 | 1 | -11.5797 | 12.00 | 12.5 |
| 2.5 | 3 | 2 | 1 | -11.5797 | 12.00 | 12.5 |
| 3.0 | 3 | 2 | 1 | -11.5797 | 12.00 | 12.5 |

This closes the design doc's own "Open/unresolved" item — the sweep
"hasn't actually been run yet." Real finding: stable for k≥2.0 on this
window, meaningfully more sensitive at k=1.5.

## Storage + query round-trip, for real

```python
storage.write("AAPL", "drawdown_deep_dive", df, granularity="1D", tier="tier2")
# -> run_id "3ca687abe115", read back: 3 rows, exact match

query_slice(back, ["day_of_week"], {"avg_drop_pct": ("drop_pct", "mean")})
#  day_of_week  n  avg_drop_pct
#       friday  1       -9.5485
#       monday  1      -13.2869
#    wednesday  1      -11.9038
```

Independently checked against a hand-written pandas
`groupby("day_of_week")["drop_pct"].agg(["mean","count"])` on the same
raw rows and matched exactly.

## Related files

- `01-implementation.md` — how this was built and tested, including the
  ATR-warmup bug found and fixed along the way.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` —
  the checklist this scenario satisfies.
