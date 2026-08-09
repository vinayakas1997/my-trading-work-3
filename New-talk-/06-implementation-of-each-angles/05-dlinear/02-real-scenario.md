---
name: dlinear-real-scenario
status: done
purpose: one concrete, real example proving DLinear's walk-forward backtest actually works — real market data in, the real function call, real output back.
---

# 05 — DLinear — Real Scenario

Real AAPL daily bars, fetched via `yfinance` (the local `vinu-stock-price`
service wasn't running when this was captured — see
`05-storage-enhancement-levels/angle-validation-checklist.md` rule 1).

## The input: real data

186 real daily bars, 2025-11-10 through 2026-08-07. First and last three
rows, exactly as fetched (no fabricated numbers):

```
    bar_ts       open       high        low      close   volume
1762732800 268.959991 273.730011 267.459991 269.429993 41312400   # 2025-11-10
1762819200 269.809998 275.910004 269.799988 275.250000 46208300   # 2025-11-11
1762905600 275.000000 275.730011 271.700012 273.470001 48398000   # 2025-11-12
...
1785888000 309.359985 311.709991 305.670013 311.000000 49438800   # 2026-08-05
1785974400 314.339996 316.290009 309.230011 312.410004 46139900   # 2026-08-06
1786060800 311.450012 314.809998 310.739990 313.329987 34407100   # 2026-08-07
```

## The call

```python
from vinu_initial_analysis.angles.dlinear.backtest import run_dlinear_backtest

df = run_dlinear_backtest("AAPL", "1D", bars, data_root)
```

`min_observations=100` (DLinear's decided value) means the first 100 bars
are consumed before the first step, leaving `186 - 100 = 86` output rows —
exactly what came back.

## The output: real results

First row (the earliest step, forecasting from 2026-04-13's close):

```json
{
  "symbol": "AAPL",
  "timeframe": "1D",
  "bar_ts": 1775433600,
  "step_index": 0,
  "session": "closed",
  "subsession": null,
  "day_of_week": "monday",
  "week_of_month": 1,
  "month": 4,
  "quarter": 2,
  "status": "ok",
  "n_observations": 100,
  "n_train_windows": 70,
  "lookback": 30,
  "last_close": 258.8599853515625,
  "forecast_price": 261.315244971046,
  "forecast_return": 0.009484894376969774,
  "direction": "up",
  "train_loss": 0.15197058022022247,
  "actual_price": 253.5,
  "actual_return": -0.02070611780450735,
  "hit": 0,
  "weights_ref": "AAPL/dlinear/1D/2026/202604/1775433600.pt"
}
```

This step predicted "up" (+0.95%) but the real next close came in down
2.07% — recorded honestly as `"hit": 0`. A backtest that only ever showed
successful predictions would be worth distrusting; this one shows both.

Last row (the most recent step, using an expanding window of 185 bars by
this point):

```json
{
  "symbol": "AAPL",
  "timeframe": "1D",
  "bar_ts": 1785974400,
  "step_index": 85,
  "session": "closed",
  "subsession": null,
  "day_of_week": "thursday",
  "week_of_month": 1,
  "month": 8,
  "quarter": 3,
  "status": "ok",
  "n_observations": 185,
  "n_train_windows": 155,
  "lookback": 30,
  "last_close": 312.4100036621094,
  "forecast_price": 316.3025205127135,
  "forecast_return": 0.012459642152861791,
  "direction": "up",
  "train_loss": 0.072734035551548,
  "actual_price": 313.3299865722656,
  "actual_return": 0.002944793378483706,
  "hit": 1,
  "weights_ref": "AAPL/dlinear/1D/2026/202608/1785974400.pt"
}
```

Note `n_observations` growing from 100 to 185 between the first and last
row — the expanding window (DLinear's decided `window="expanding"`)
actually growing step by step, not a fixed-size slice.

## Proving the weights are real, not just "some file exists"

```python
from vinu_initial_analysis.storage.weights import WeightsStore
from vinu_initial_analysis.angles.dlinear.compute import _build_model, LOOKBACK, KERNEL_SIZE
import torch

store = WeightsStore(data_root)
state_dict = store.load("AAPL/dlinear/1D/2026/202604/1775433600.pt")

model = _build_model(LOOKBACK, KERNEL_SIZE)
model.load_state_dict(state_dict)
model.eval()
# ... reconstruct the same 30-bar input window this step used ...
# reloaded model's forecast_price: 261.315244971046
# recorded forecast_price:         261.315244971046  <- exact match
```

The reloaded model reproduces the exact `forecast_price` that step
recorded, to full float precision — proof the weights file saved for a
given `bar_ts` really is the model that made that step's forecast, not a
different step's, and not a placeholder.

## Session tagging: honest, not broken

Every one of the 86 rows shows `"session": "closed"` — because a 1D bar's
timestamp sits at midnight UTC, outside every real trading session
window. This is correct (see
`angle-validation-checklist.md` finding #1), and it's why a
session-grouped query isn't a meaningful example for this angle — grouping
by `day_of_week` is:

```python
from vinu_initial_analysis.storage.query import query_slice

query_slice(df, ["session"], {"avg_hit_rate": ("hit", "mean")})
#   session   n  avg_hit_rate
# 0  closed  86      0.511628
```

That single-row, 51.2%-over-86-observations result is real but not useful
as a demonstration — it's included here specifically to document *why*
it's the wrong grouping to showcase for a 1D angle, not as the angle's
real headline result.

## Related files

- `01-implementation.md` — how this was built and what was tested.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` —
  the checklist this scenario satisfies, and where findings #1 and #2
  (session tagging, intraday prepost data) are explained in full.
