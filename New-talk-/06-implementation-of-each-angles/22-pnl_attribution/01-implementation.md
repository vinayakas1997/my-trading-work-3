---
name: pnl_attribution-implementation
status: phase-1-done
purpose: the real record of implementing pnl_attribution's per-artifact_id breakdown — the one angle in this project with no real production data to validate against yet.
---

# 22 — pnl_attribution — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/pnl_attribution/compute.py` | Edited | Extracted `_aggregate_group()` (win_rate/avg_win_pct/avg_loss_pct/n_trades/total_realized_pnl for one group of closed positions) out of `aggregate_pnl_attribution`'s inline logic. `aggregate_pnl_attribution` now also groups `closed_positions` by `artifact_id` and computes the same block per group as a new `by_artifact` nested dict — the actual "attribution" breakdown the design doc proposed. Symbol-level output unchanged (same keys, same values). |
| `vinu-initial-analysis/vinu_initial_analysis/angles/pnl_attribution/spec.yaml` | Edited | `time_formats` widened from `[1D]` to the decided 6 (still doesn't mean much for push-fed data, per the design doc's own note — done for schema consistency). |
| `vinu-initial-analysis/tests/test_pnl_attribution.py` | Edited | Added `artifact_id` parameter to the `_closed_position` fixture helper (default unchanged, so all 11 pre-existing tests pass unmodified) + 3 new tests for the `by_artifact` breakdown. |

## How it was implemented

Group B, and unlike every other angle built this session: **not
bars-driven at all**, and — per the design doc's own explicit statement —
**has no real data to validate against yet**, since it's push-fed from
Phase 6 live trading positions that don't exist in this project's current
state (no live trading has run). This is not a corner cut; it's the
project's own already-documented reality (`22-pnl_attribution.md` SS7:
"this angle has no real data to validate any of this against until Phase
6 live trading actually produces closed positions... everything in SS4
is illustrative shape, not a measured result").

The actual work was narrow and precisely scoped by the design doc: add
a per-`artifact_id` breakdown alongside the existing (unchanged, already
correct) symbol-level aggregate. `artifact_id` was already present on
every closed position's real schema (`vinu-live/book/schema.py`'s
`Position.artifact_id`) and already flows through `closed_positions_json`
unmodified — no new data collection, no new ingest path, purely an
aggregation-logic addition to `aggregate_pnl_attribution` itself
(not a separate `backtest.py`, since the design doc explicitly says
"Backtest method: not applicable" for this angle — there's no historical
bars to walk forward over).

`_aggregate_group()` is the same win_rate/avg_win/avg_loss/CI block that
used to be computed inline once (symbol level) — extracted so
`by_artifact`'s per-group computation reuses the identical, already-
correct logic rather than a second copy that could silently drift from
the symbol-level one.

## Testing

11 pre-existing tests (all pass unchanged — the `by_artifact` addition is
purely additive to the output dict, no existing key changed shape or
value) + 3 new tests: correct grouping by `artifact_id` (2 artifacts,
correct per-group `n_trades`/`total_realized_pnl`, thin group correctly
flagged `insufficient_sample`), the single-artifact case matches the
symbol-level totals exactly (a real consistency check — if every trade
shares one artifact, `by_artifact`'s one entry should equal the whole-
symbol aggregate), and positions with no `artifact_id` are excluded from
`by_artifact` but still counted at the symbol level (matches real
production data where `artifact_id` defaults to `""` for any position
not linked to a Phase 4 TradePlan).

**"Real-data validation" — the one legitimate exception in this
session**: no real Phase 6 closed positions exist in this project yet
(confirmed: this is the design doc's own stated fact, not something I
independently discovered). Ran a schema-accurate scenario instead — 3
closed positions built with exactly the real `Position` dataclass's
field names/types (`position_id`, `symbol`, `side`, `qty`, `avg_entry`,
`realized_pnl`, `closed_at`, `artifact_id`), 2 sharing one `artifact_id`
("does this specific trade plan's own performance separate cleanly from
the rest") — confirmed the grouping, win-rate math, and thin-sample
flagging all work correctly on schema-faithful data. Verified the full
real ingest path too: `pnl_attribution_ingest.ingest_closed_positions()`
→ `AngleStorage.write()` → `storage.read_latest()` round-trip, confirming
the nested `by_artifact` dict survives the real parquet write/read cycle
(same nested-dict storage pattern as lag_llama/moirai/moment's
`predictions`) with exact content match.

**Full `vinu-initial-analysis` suite**: run after this angle; see
`../plan.md`'s status table entry for the pass count.

## Related files

- `02-real-scenario.md` — the schema-accurate example.
- `../plan.md` — overall status table.
- `../../04-enhancement-of-each-angle/22-pnl_attribution.md` — the decided design.
