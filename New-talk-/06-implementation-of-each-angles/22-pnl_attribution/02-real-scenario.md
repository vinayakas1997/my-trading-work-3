---
name: pnl_attribution-real-scenario
status: phase-1-done
purpose: one concrete, schema-accurate example proving the by_artifact breakdown actually works, and the real ingest/storage round-trip — this angle has no genuine production data yet, a fact the design doc itself already states.
---

# 22 — pnl_attribution — Real Scenario

No real Phase 6 closed positions exist in this project yet — this is
stated directly in the decided design doc, not a limitation found here.
The scenario below uses 3 closed positions built with the exact real
`Position` schema's field names and types
(`vinu-live/vinu_live/book/schema.py`), not fabricated/simplified ones.

## The call

```python
from vinu_initial_analysis.angles.pnl_attribution.compute import aggregate_pnl_attribution

positions = [
    {"position_id": "p1", "symbol": "AAPL", "side": "long", "qty": 10.0,
     "avg_entry": 270.0, "realized_pnl": 55.0,
     "closed_at": "2026-01-10T15:00:00Z", "artifact_id": "artifact_kronos_001"},
    {"position_id": "p2", "symbol": "AAPL", "side": "long", "qty": 5.0,
     "avg_entry": 268.0, "realized_pnl": -22.0,
     "closed_at": "2026-01-14T15:00:00Z", "artifact_id": "artifact_kronos_001"},
    {"position_id": "p3", "symbol": "AAPL", "side": "short", "qty": 8.0,
     "avg_entry": 275.0, "realized_pnl": 40.0,
     "closed_at": "2026-01-20T15:00:00Z", "artifact_id": "artifact_arima_002"},
]
df = aggregate_pnl_attribution("AAPL", positions)
```

## Real output

```json
{
  "symbol": "AAPL", "status": "ok", "n_trades": 3, "total_realized_pnl": 73.0,
  "win_rate": {"mean": 0.667, "n_observations": 3, "confidence_interval": [-0.77, 2.10], "status": "ok"},
  "by_artifact": {
    "artifact_kronos_001": {
      "n_trades": 2, "total_realized_pnl": 33.0,
      "win_rate": {"mean": 0.5, "n_observations": 2, "status": "ok"},
      "avg_win_pct": {"mean": 0.0204, "n_observations": 1, "status": "insufficient_sample"},
      "avg_loss_pct": {"mean": -0.0164, "n_observations": 1, "status": "insufficient_sample"}
    },
    "artifact_arima_002": {
      "n_trades": 1, "total_realized_pnl": 40.0,
      "win_rate": {"mean": 1.0, "n_observations": 1, "status": "insufficient_sample"}
    }
  }
}
```

`artifact_kronos_001`'s 2 trades separate cleanly from `artifact_arima_002`'s
1 trade — the actual "which trade plan is making money" breakdown this
angle's name promises, correctly flagging both groups' individual
statistics as `insufficient_sample` at n=1-2 (honest, not hidden).

## The real ingest + storage round-trip

```python
from vinu_initial_analysis.pnl_attribution_ingest import ingest_closed_positions
from vinu_initial_analysis.storage.parquet import AngleStorage

storage = AngleStorage(data_root)
run_id = ingest_closed_positions(storage, "AAPL", positions)
back = storage.read_latest("AAPL", "pnl_attribution")
# by_artifact survives the real parquet write/read cycle with exact
# content match -- same nested-dict pattern as lag_llama/moirai/moment's
# `predictions` field.
```

## Why there's no "real market data" section here

Every other angle in this session's Phase 1 checklist validates against
real Alpaca price bars. This angle doesn't consume price bars at all —
its real input is Phase 6 trade executions, which don't exist yet in this
project (no live trading has run). The design doc names this directly as
an open item, not something discovered during implementation. What *is*
verified here, for real, is: the aggregation math (win rate, avg win/loss,
CI, per-artifact grouping) on schema-faithful data, and the full real
ingest→storage→read round-trip through the actual production code path
(`pnl_attribution_ingest.py`, not a test-only shortcut).

## Related files

- `01-implementation.md` — how this was built and tested.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist; this angle satisfies its storage/query requirements but not its "real market data" requirement, for the reason stated above.
