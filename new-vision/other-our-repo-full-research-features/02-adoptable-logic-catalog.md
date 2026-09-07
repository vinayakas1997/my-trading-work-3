# 02 — Adoptable Logic Catalog (Beyond-16 Worth-Implementing 17-26)

> Features not in `04:` nor pending `01-16` but mature in outer repos and worth adding for whole-app live survival. Sep 2026.

| # | Outer source | Feature not in 04 nor pending | What it is | Dest vinu file (where to wire) | Effort | Depends on |
|---|---|---|---|---|---|
| 17 | **Qlib** `qlib/data/handler` | **Purged Walk-Forward + Embargo + Triple-Barrier labeling** | Purged/embargoed CV per Lopez de Prado ch.7 + triple-barrier (take-profit/stop-loss/max-hold) label | `vinu-research/pbo.py` + `vinu-research/sweep.py:159` + `vinu-quant-core` simulator | Low-med | After Row 1 |
| 18 | **Qlib** model zoo | **Model Ensemble + Attribution** | Stacking/ensemble over candidates + PnL attribution per factor/angle | `vinu-research/comparison.py:33` + `vinu-portfolio/service.py:build_portfolio` + `vinu-simulator/engine/attribution.py` | Med | Row 1 green |
| 19 | **Freqtrade** `optimize/` | **Hyperopt Bayesian + Pairlist filtering** | Bayes search over sweep space + pairlist prunes illiquid before Gate (vol/volume filter) | `vinu-research/sweep.py` + `vinu-agent/scheduler_workers.py` Gate `04:23` | Low | — |
| 20 | **Nautilus + QuantConnect** | **Pre-trade Risk Gateway + Message Throttles** | Every `OrderGuard` order checks size/position/price band + rate cap (e.g. 10/sec) | `vinu-live/broker/order_guard.py` + `broker/kill_switch.py` | Low-med | Row 13 env |
| 21 | **Nautilus catalog** | **Data Versioning + Lineage + Freeze Manifest** | `freeze.py` hash of `data/news:stock-price:features` inputs + contamination check | `vinu-infra/` + `vinu-initial-analysis/RunLog` `04:20` | Med | — |
| 22 | **Lean Research + VectorBT** | **Signal Ranking + Distribution view** | Ranked signal + distribution/mapping view in notebook | `vinu-research/sweep_grid.py:86` + new `notebooks/` | Low | Row 7 |
| 23 | **FinRL turbulence + Hummingbot inventory** | **Turbulence Index + Vol-adjusted sizing** | VIX/turbulence scales down sizing in stress; inventory skew | `vinu-tools/` indicators + `vinu-portfolio/service.py:compute_daily_allocation` | Med | Row 5 |
| 24 | **Freqtrade dry-run** | **Dry-Run Wallet with Simulated Fills (not Sharpe-only)** | Wallet-level dry-run tracks fills tick-by-tick vs `ShadowEvaluator:120` daily-return Sharpe-only | `vinu-live/shadow_evaluator.py:23` + `vinu-simulator/service.py` | Med | Row 14 |
| 25 | **TradeMaster PRIDE-Star** | **8-Metric PRIDE Star + Monte Carlo / Stress** | Star plot (TR, SR, maxDD…) + Monte Carlo equity resampling | `vinu-simulator/engine/metrics.py` + `vinu-research/service.py` | Low | — |
| 26 | **Qlib Arctic + Orderbook** | **LOB Feature + Market-Impact beyond Almgren-Chriss** | Spread/depth features; extend `costs.py:73` `missing_volume_impact_pct=0.005` with spread | `vinu-tools/` + `vinu-simulator/engine/costs.py:73` | Med-high | Only if intraday |

## Priority as Slice

- **Immediate (next after 16 green):** 20 (Risk Gateway + Throttle), 21 (Freeze Manifest), 24 (Dry-run wallet) — highest live-safety per effort.
- **Next:** 17 (Purged CV), 18 (Ensemble), 19 (Hyperopt), 23 (Turbulence), 25 (Monte Carlo).
- **Later / conditional:** 22 (Signal ranking — notebooks), 26 (LOB — only if intraday).

## How to spike each

For each row: clone outer repo, open source file noted, copy logic/test pattern (not whole service), wire into dest vinu file, add test in `vinu-* /tests/test_*.py` mimicking outer repo's test.
