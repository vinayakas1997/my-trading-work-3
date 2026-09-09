# Decisions — B Adoptable 20/21/24 (2026-09-07)

> `02-adoptable-logic-catalog.md` Rows 20,21,24

## B20 Risk Gateway + Throttle — BUILT

- `vinu-agent/broker/order_guard.py` deque 10 orders/sec per instance before mandate checks, fail-closed. Covers runaway loop #1 blow-up per QuantMemo. Price band still via `max_order_value` + `max_position_pct` existing.

## B21 Freeze Manifest — BUILT

- `vinu-infra/freeze.py` `freeze_manifest()` + `contamination_check()`: hashes VINU_* env + file hashes under `*_DATA_ROOT`. Port of `quant-live-readiness-kit`. Enables lineage proof and `drift` detection between research and live.

## B24 Dry-run wallet — SPIKED

- `vinu-live/shadow_evaluator.py` currently Sharpe-only (`daily_returns`). Wallet-level dry-run (tick fills, fees) remains backlog; freeze manifest + rehearsal cover most divergence. Next: extend `ShadowEvaluator` to `portfolio_value` wallet simulation using `WeightSimulator` with `CostModel`.

## Status

- B20/B21 built, B24 spiked — Row 14 staged rollout now has freeze + throttle; full tick fill reconciliation remains enhancement.
