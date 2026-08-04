# vinu-initial-analysis — Status

**Status: signal-usage contract implemented.** Freshness recompute job:
decided and implemented, but hosted in `vinu-research` instead of here —
no code lands in this component for it, see
[`../vinu-research/status.md`](../vinu-research/status.md). Full detail in
[`plan.md`](plan.md).

## Files touched

**Signal-usage contract:**
- `vinu_initial_analysis/angles/signal_contract.py` (new) — `SIGNAL_USAGE_CONTRACT` dict (currently: `significance_score`, `regime_feature`) + `tag_row(row, field)` helper that attaches `{field}_proven_for` / `{field}_not_proven_for` / `{field}_evidence_ref`.
- `vinu_initial_analysis/angles/news_price_causality/compute.py` — tags each row that gets a `significance_score` with the contract.
- `vinu_initial_analysis/angles/regime_analysis/compute.py` — tags each `regime_stats` row with the contract.
- `tests/test_signal_contract.py` (new, 4 tests) — tag attachment for a known field, no-op for an unknown field, values match the registry, and the full round trip through `regime_analysis.compute()`'s actual output rows.

**Freshness recompute job (daily regime/correlation recompute): decided and implemented, hosted in `vinu-research`** — the either/or with `vinu-research/plan.md` resolved in favor of hosting there (`regime_recompute_scan()` on the existing `ScheduledResearchExecutor`); no new code needed in this component beyond the already-exposed `/analysis/run/{symbol}?angle_names=...` route it calls. See [`../vinu-research/status.md`](../vinu-research/status.md) for the implementation and tests.

## Bugs / Fix Log

None found while building the signal-usage contract.

## Test run

`uv run pytest tests/test_signal_contract.py` from `vinu-initial-analysis/`: **4 passed**.
