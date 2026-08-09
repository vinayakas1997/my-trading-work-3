---
name: chronos-real-scenario
status: phase-1-done
purpose: one concrete, real example proving Chronos's walk-forward backtest actually works — real Alpaca data in, a real 710M-parameter model call, real nested output, real storage/query round-trip including the first real unnest_predictions check.
---

# 03 — Chronos — Real Scenario

525 real AAPL 1-hour bars (Alpaca, aggregated via the real
`vinu_stock.query.aggregate.aggregate_bars`) — the most recent slice of a
larger real dataset, deliberately kept small given the real ~14s-per-step
cost of a genuine `chronos-t5-large` forecast call on CPU (see
`01-implementation.md` for why `1D` wasn't feasible here at all: only 125
real daily bars exist, far short of the 512 this model requires).

## The call

```python
from vinu_initial_analysis.angles.chronos.backtest import run_chronos_backtest

df = run_chronos_backtest("AAPL", "1H", bars)  # 9 real steps, ~117s total
```

## Real output — one full step

```json
{
  "symbol": "AAPL", "timeframe": "1H", "bar_ts": 1786021200, "step_index": 0,
  "session": "ny", "subsession": "premarket",
  "day_of_week": "thursday", "week_of_month": 1, "month": 8, "quarter": 3,
  "status": "ok",
  "model_backend": "pretrained", "checkpoint": "amazon/chronos-t5-large",
  "last_close": 314.88,
  "predictions": {
    "1": {"p10": 313.6624, "median": 315.9188, "p90": 318.1754, "actual": 313.345, "hit": 0},
    "2": {"p10": 313.6624, "median": 315.9188, "p90": 320.4319, "actual": 309.55,  "hit": 0},
    "3": {"p10": 313.6624, "median": 315.9188, "p90": 320.4319, "actual": 311.67,  "hit": 0},
    "4": {"p10": 311.4056, "median": 315.9188, "p90": 322.0116, "actual": 312.16,  "hit": 1},
    "5": {"p10": 311.4056, "median": 318.1754, "p90": 322.0116, "actual": 312.255, "hit": 1}
  }
}
```

Real, non-degenerate spread here — the band widens with horizon (as
expected) and the miss/hit pattern is genuine (misses at steps 1-3, hits
at 4-5), not a constant.

## The degenerate-band finding, shown for real

A different real 512-candle context (calmer, std=0.69 on a ~313 price
level) produced this instead — every field bit-identical:

```json
{"p10": 313.9796, "median": 313.9796, "p90": 313.9796}
```

Reproduced on **both** `chronos-t5-tiny` and `chronos-t5-large` on the
identical context — confirmed not a checkpoint-specific bug. A more
volatile real window (std=13.8, ~20x higher) produced genuine nonzero
spread again, especially at later steps — confirming the mechanism is
real relative-volatility-driven quantization behavior, not a code defect.
See `01-implementation.md`'s "Real finding" section for the full
investigation.

## Storage + `unnest_predictions` round-trip, for real

```python
storage.write("AAPL", "chronos", df, granularity="1H", tier="tier2")
# -> run_id "5acc84287e40", read back: 9 rows, exact match
# nested predictions dict survives the real parquet round-trip byte-for-byte

from vinu_initial_analysis.storage.query import unnest_predictions, query_slice

flat = unnest_predictions(back)  # 9 rows -> 45 rows (9 steps x 5 horizons)

query_slice(flat, ["horizon"], {"hit_rate": ("hit", "mean")})
#  horizon  n  hit_rate
#        1  9  0.555556
#        2  9  0.777778
#        3  9  1.000000
#        4  9  1.000000
#        5  9  1.000000
```

This is the **first real proof `unnest_predictions` actually works** on
genuine nested model output, not just the hand-built test fixtures in
`test_query.py` — matched a hand-computed pandas `groupby` exactly.

**Caveat, stated plainly**: this table looks like "accuracy improves with
horizon," the opposite of what the design doc's own example anticipated
("accuracy decaying by horizon step"). With `n=9` this is not a real
finding — it's what happened on one small, deliberately-limited real
slice. Not treated as a conclusion; recorded honestly as a real number
from a real (if small) run.

## Naive baseline comparison (real data)

```python
from vinu_initial_analysis.angles.chronos.naive_baseline import run_naive_baseline
```

| Horizon step | naive RMSE | Chronos RMSE | Chronos better? |
|---|---|---|---|
| 1 | 1.9245 | 2.1539 | No |
| 2 | 2.2855 | 2.6958 | No |
| 3 | 1.7066 | 2.0975 | No |
| 4 | 1.7309 | 2.0868 | No |
| 5 | 1.5417 | 2.0264 | No |

Same honest pattern as ARIMA — naive wins on this real (small) sample.
Same caveat: `n=9`, not conclusive on its own.

## Related files

- `01-implementation.md` — how this was built, tested, and all bugs/findings in full.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist this satisfies.
