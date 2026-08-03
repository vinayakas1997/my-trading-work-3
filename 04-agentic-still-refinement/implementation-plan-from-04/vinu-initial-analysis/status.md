# vinu-initial-analysis — Status

**Status: signal-usage contract implemented.** Freshness recompute job not started. Full detail in [`plan.md`](plan.md).

## Files touched

**Signal-usage contract:**
- `vinu_initial_analysis/angles/signal_contract.py` (new) — `SIGNAL_USAGE_CONTRACT` dict (currently: `significance_score`, `regime_feature`) + `tag_row(row, field)` helper that attaches `{field}_proven_for` / `{field}_not_proven_for` / `{field}_evidence_ref`.
- `vinu_initial_analysis/angles/news_price_causality/compute.py` — tags each row that gets a `significance_score` with the contract.
- `vinu_initial_analysis/angles/regime_analysis/compute.py` — tags each `regime_stats` row with the contract.
- `tests/test_signal_contract.py` (new, 4 tests) — tag attachment for a known field, no-op for an unknown field, values match the registry, and the full round trip through `regime_analysis.compute()`'s actual output rows.

**Freshness recompute job (daily regime/correlation recompute): not started** — pending the either/or decision with `vinu-research/plan.md`.

## Bugs / Fix Log

None found while building the signal-usage contract.

## Test run

`uv run pytest tests/test_signal_contract.py` from `vinu-initial-analysis/`: **4 passed**.
