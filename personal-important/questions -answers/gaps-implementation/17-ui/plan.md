# Plan - 17 UI Status

Goal: Single view read-only v1, no live buttons.

Files touched:
- Read: `vinu-components/vinu-agent/server/routes_system.py:15` health, `routes_ticker_ledger.py` ledger, `routes_broker.py:114` perf, `storage/ticker_summaries.py:88` summary, research artifacts, sim parquet + live books.
- New: `full_progress.db` view (see 04), pipeline 0-7 page, drill-down curves, halt banner, export CSV.
- Repos views: freqUI tables, Lean/Nautilus admin, Qlib/VectorBT plots.

Steps:
1. Checkbox view + pipeline page. Highest value.
2. Drill-down + freqUI tables.
3. Halt banner + reconcile diff + plots + export alerts.
4. Test: counts match DB, equity loads, banner on HALT, CSV downloads, 10s refresh no 429.

Knobs: `UI_ENABLED`, `UI_PORT=8092`, `UI_REFRESH_SEC=10`, `UI_READ_ONLY=true` (see 10).
Acceptance: 1 SELECT shows AAPL 1D 27/27, click run_id shows curve.
