---
name: trend_session_structure-real-scenario
status: phase-1-done
purpose: one concrete, real example proving the per-session confidence-calibration breakdown actually works end to end with trend_lifecycle's real output — the final angle of this implementation pass.
---

# 31 — trend_session_structure — Real Scenario

Real trend_lifecycle signal-outcome data (the same real AAPL 1D backtest
validated in `30-trend_lifecycle/02-real-scenario.md`).

## The call

```python
from vinu_initial_analysis.angles.trend_lifecycle.backtest import run_signal_outcome_backtest
from vinu_initial_analysis.angles.trend_session_structure.backtest import aggregate_signal_outcomes_by_session

signal_outcomes = run_signal_outcome_backtest("AAPL", bars, time_format="1D")
result = aggregate_signal_outcomes_by_session(signal_outcomes)
```

## Real output

```json
[
  {
    "session": "afterhours", "n_signals": 6, "n_mature_signals": 6,
    "meets_floor": true, "avg_stated_confidence": 0.4917,
    "measured_success_rate": 0.5
  }
]
```

All 6 real `book_profits` signals land in a single session bucket — on
1D data, every peak's timestamp shares the same session classification,
exactly the structural collapse this angle's own design doc predicts (and
`05-dlinear`'s real-data validation already confirmed independently: "all
1D rows show session=closed"). This is why `trend_session_structure`
itself correctly returns `not_applicable` for 1D+ timeframes — a real
per-session breakdown needs intraday data (Phase 2, deferred, same as
every other angle's finer timeframes this session) to actually say
anything about premarket vs. regular vs. afterhours behavior.

The number itself (0.4917 confidence, 50% success) is identical to
`trend_lifecycle`'s own unsliced aggregate — expected and correct when
every row shares one session; this confirms the join/grouping logic
works, not that a real cross-session difference exists on this dataset.

## Storage round-trip, for real

```python
storage.write("AAPL", "trend_session_structure_signal_calibration", result, granularity="1H", tier="tier2")
back = storage.read("AAPL", "trend_session_structure_signal_calibration", granularity="1H", tier="tier2")
# round-trip rows match: True
```

## What a real intraday check would show (Phase 2, deferred)

This angle's actual real value — "does session matter" — can only be
answered against 15min/1H/4H data, where real trading sessions actually
vary across peaks. That's explicitly out of Phase 1's scope (this
session's real-data checklist validates the coarsest declared timeframe
first), tracked the same way every other angle's finer timeframes are:
deferred, not silently skipped.

## Related files

- `01-implementation.md` — how this was built and tested, including the
  confirmation that no correctness work was needed in the underlying code.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist this satisfies.
