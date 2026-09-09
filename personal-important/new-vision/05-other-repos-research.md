# 05 — Other Repos Research: Open-Source Quant Packages by Stars & Extractable Features

> Purpose: collect live Sep 2026 data on good, high-star open-source quant packages so we can extract features not yet in `vinu-components`. Companion to `04-new-full-explanation.md` vision and `pending-items-to-be-implemented.md` (16 shortcomings). Stars are live GitHub API reads Sep 7 2026; use as signal, not truth (see `TitanFlow-Systems/best-of-algorithmic-trading` quality score note).

## Methodology

- Primary index: `TitanFlow-Systems/best-of-algorithmic-trading` — 109 projects across 7 categories, ~310K combined stars, ranked by automated quality score (GitHub activity + contributors + package stats) not just stars.
- Cross-checked via `wilsonfreitas/awesome-quant` (29.4K stars, 136 contributors, 25 categories) and `grokipedia.com Popular open-source quantitative trading projects 2025-2026` (Qlib 39K+, Qbot 16K+).
- Direct GitHub reads for star counts below (Sep 2026). For quick local audit: `git clone https://github.com/TitanFlow-Systems/best-of-algorithmic-trading && grep -n "Freqtrade\|Hummingbot\|Lean" projects.yaml`.

## Ranked Table — Stars + What to Steal

| # | Package | Stars (Sep 2026) | Primary stack / license | One-line what it does | Key feature to consider extracting | Maps to `pending-items-to-be-implemented.md` row |
|---|---|---|---|---|---:|---|
| 1 | **Freqtrade** `freqtrade/freqtrade` | **54.1K** (TitanFlow reports 48K, leaderboard 46.9K) | Python, GPL-3.0, Docker, 390 contributors, 32K commits | Free crypto bot; backtest → hyperopt (ML) → dry-run → live on 20+ exchanges via CCXT, Telegram/WebUI/REST control, `freqUI`, `FreqAI` (RL) | **Hyperopt + `lookahead analysis` & `recursive analysis` guards** — auto-detects future-leak in strategy before live. Also download/hyperopt plumbing. | Row 1 (rehearsal leak check), Row 7 (untuned caps) |
| 2 | **microsoft/Qlib** | **48.4K** live (Grokipedia 39.3K Mar 2026, TrendingBots 45.1K Apr 2026) | Python, MIT, Microsoft, 7.6K forks | AI-oriented end-to-end: data → factor mining → model zoo (LGBM/Transformer) → portfolio opt → execution; Point-in-Time DB, Arctic/Orderbook, `RD-Agent` LLM autonomous R&D | **Point-in-Time DB + factor store + Qlib notebook tutorial** and **RD-Agent** (LLM factor/model evolution). Solves survivorship/universe gap. | Row 15 (universe/survivorship), Row 11 (Thesis Intake risk-rules) |
| 3 | **NautilusTrader** `nautechsystems/nautilus_trader` | **28.6K**, 3.7K forks, 21K commits | Rust core + Python, LGPL-3.0 | Production-grade deterministic event-driven, nanosecond, Parquet catalog, configurable fill/fee/latency/book models, single-node backtest→live parity | **Deterministic core + fill/latency/book models** and **Parquet data catalog** — hardens `vinu-simulator/engine/simulator.py:189` Almgren-Chriss + `shadow_evaluator.py:23` tick reconciliation | Row 14 (staged rollout + fill reconciliation) |
| 4 | **awesome-quant** `wilsonfreitas/awesome-quant` | **29.4K**, 3.9K forks (meta-list) | Curated Markdown/YAML, no runtime | 25-language index: numerical libs, pricing, indicators, trading & backtesting, reproducible books | **Use as audit checklist**, not runtime — cross-check coverage | — |
| 5 | **daily_stock_analysis** `ZhuLinsen/daily_stock_analysis` | **25K** | Python, LLM-driven | LLM daily dashboard for A/H/US: multi-source行情+news+quotes+sentiment, auto decision dashboard, multi-channel notify | **Multi-source ingest + LLM summary → notify** pattern | Row 9 (Significance Triage delivery), enriches `vinu-news` |
| 6 | **QuantConnect/Lean** | **21.5K** (GitStarClub 21.3K Aug 2026) | C# 94% + Python, Apache-2.0, 230 contributors | Event-driven multi-asset (eq/opt/fut/crypto/forex), broker adapters (IBKR/Coinbase/Binance/OANDA), `lean backtest/optimize/live` CLI, cloud hybrid | **Broker adapter registry + `lean live` parity** and **Optimizer** for K/N tuning | Row 7, Row 13 (broker factory), Row 15 |
| 7 | **Zipline** `quantopian/zipline` | **20.1K**, 5K forks | Python, Apache-2.0 | Pythonic algo library that powered Quantopian; Pipeline API | **Pipeline `Filter/Classifier` factor API** — inspiration for `angle_synthesizer` cross-angle `agree/diverge` but superseded by Lean | Row 8 (Calibration Tracker) |
| 8 | **Hummingbot** `hummingbot/hummingbot` | **18K** (TitanFlow 18K, 310 contributors) | Python, Apache-2.0 | Market-making & arbitrage, connector architecture | **Connector + inventory skew** — if adding market-making angle | Future angle |
| 9 | **Qbot** `UFund-Me/Qbot` | **16.7K** | Python, local-deploy | AI quant robot, full local deployment, Chinese broker APIs (Haitong/Huatai), RL/DL, WeChat community | **Local deployment pattern** — validates `host.docker.internal:8009` local `qwen36-35B` | — (validates current) |
| 10 | **Abu / 阿布量化** `bbfamily/abu` | **16.6K** | Python | A-share/HK + futures/options/BTC, ML + position management | China factor library | Only if targeting A-shares |
| 11 | **FinRL** `AI4Finance-Foundation/FinRL` | **16.2K**, 3.5K forks (FinRL-X successor) | Python, MIT, NeurIPS 2020 | First financial RL: `StockTrading 2026` tutorial trains 5 agents (A2C, DDPG, PPO, TD3, SAC) vs MVO/DJIA, Gym envs; successor `FinRL-Trading` decoupled modular | **RL env + 5-agent bake-off + FinRL-Meta benchmarks** — plugs into `simulator.py:300` `SimulatorEnv` | Row 5 (sizing bake-off), Row 6 (verdict) |
| 12 | **VectorBT** `polakowo/vectorbt` | **9.0K**, 1.1K forks | Python + Numba/Rust, Fair-Code | Vectorized: thousands of param combos via NumPy/Numba/Rust in seconds, pandas-native, TA-Lib, QuantStats, signal ranking | **Vectorized sweep** — accelerate `run_parameter_sweep`/`comparison.py` grid matrix; indicator ecosystem for 31 angles | Row 1, Row 7 |
| 13 | **StockSharp** | **9.4K**, 2K forks | C#, Apache-2.0 | Algo platform | Less relevant (C#) unless `quant-core-api:8084` ported | — |
| 14 | **PyPortfolioOpt** `robertmartin8/PyPortfolioOpt` | **~3.4K** (pepy ~64K DL/mo) | Python, MIT | Efficient frontier, Black-Litterman, shrinkage, HRP, `L2_reg`, `objective_functions` | **HRP / Black-Litterman + L2_reg** → replace provisional `config.py:106` `fractional_kelly` | Row 5 |
| 15 | **pysystemtrade** `robcarver17/pysystemtrade` | **~2K** (via awesome-quant) | Python | Rob Carver `Systematic Trading` framework | **Forecast → position → portfolio rules** — alternative to Qlib pipeline | Row 5 |
| 16 | **vn.py / VeighNa** `vnpy/vnpy` | **~13K** original; `paperswithbacktest` fork 95 | Python, event-driven | Multi-gateway China futures/stocks/crypto | Gateway pattern | Only if CN market |
| 17 | **TradeMaster** `TradeMaster-NTU/TradeMaster` | **3.1K** | Python, Apache-2.0, HKUST | RL platform with configs `algorithmic_trading/high_frequency/order_execution/portfolio_management` + `PRIDE-Star` 8-metric | **RL pipeline template** | Row 6 |
| 18 | **best-of-algorithmic-trading** `TitanFlow-Systems` | **253** | Generator | Weekly ranked `projects.yaml` → quality score | **Use `grep` trick to audit activity** | Meta |

> Note: star history is point-in-time; trending weekly velocity (e.g. Qlib +360/wk, Lean +766 Jul 2026) matters more than absolute. TitanFlow warns abandoned repos collect stars long after last release — check `⏱️ last update` + `quality score` not just `⭐`.

## Per-Package Extractable Detail (what exists vs what Vinu already has)

### Freqtrade — hyperopt & leak guards
- **Repo:** `https://github.com/freqtrade/freqtrade` (`user_data/strategies/`, `freqtrade/optimize/`).
- **Extract:** `lookahead analysis` (`freqtrade lookahead-analysis`) flags use of `close` of same bar to enter; `recursive analysis`; `hyperopt` with `skopt`/`hyperopt` loss functions. Your `WeightSimulator` has `T+1 shift(1):103` already (no lookahead), but no automated post-hoc leak scan — add one test analogous to `tests/test_custom_sim.py:98 TestPerfectForesightCannotProfit`.
- **Effort:** low (borrow test pattern, not engine).

### Qlib — PIT & RD-Agent
- **Repo:** `https://github.com/microsoft/qlib` (`qlib/data/`, `qlib/contrib/`, `examples/tutorial`).
- **Extract:** `Point-in-Time database` (`pull/343 Mar 2022`) guarantees no future release used past; `notebook tutorial` end-to-end (data → factor → model → backtest → attribution). `RD-Agent` (`https://github.com/microsoft/RD-Agent`) LLM loops over factor/model search.
- **Effort:** medium; integrate PIT as data contract in `vinu-initial-analysis` quarters.

### NautilusTrader — deterministic fills
- **Repo:** `https://github.com/nautechsystems/nautilus_trader` (`crates/model/`, `nautilus_trader/model/`).
- **Extract:** `fill model` (slippage + market impact + queue), `latency model`, `Parquet catalog` (`nautilus catalog`). Your `costs.py:73 AlmgrenChrissCostModel` is close; add its queue-position logic and catalog versioning (`Data Versioning and Lineage` in QuantMemo).
- **Effort:** medium (model port).

### Lean — adapter & optimizer
- **Repo:** `https://github.com/QuantConnect/Lean` (`Brokerages/`, `Optimizer/`, `Launcher/`).
- **Extract:** Broker adapter interface (IBKR/OANDA/Coinbase) → factor `broker/factory.py _PROVIDERS`; Optimizer `lean optimize` for K/N/completeness grid.
- **Effort:** low-medium.

### FinRL / TradeMaster / FinRL-X — RL bake-off
- **Repos:** `AI4Finance-Foundation/FinRL` (`examples/FinRL_StockTrading_2026_*.py`), `TradeMaster-NTU/TradeMaster` (`configs/`), successor `FinRL-Trading`.
- **Extract:** Train 5 agents on same `DOW 30 2014-2025 → trade 2026-03-20`, compare vs MVO/DJIA; Gym env wrapping your `SimulatorEnv:300`. Use as Row 6 adversarial verdict alternative.
- **Effort:** low (clone tutorial, point at `vinu-stock-price` data).

### VectorBT — vectorized sweep
- **Repo:** `https://github.com/polakowo/vectorbt` (`vectorbt/generic/`, `vectorbt/portfolio/`).
- **Extract:** `vbt.MA.run(price, window).ma_crossed_above` broadcasting over `fast_window × slow_window × symbol` matrix; 1000 configs in seconds vs your per-candidate `run_sweep_candidate` loop `sweep.py:159`.
- **Effort:** low-medium (NumPy/Numba port of one sweep path).

### PyPortfolioOpt — HRP/BL/L2
- **Repo:** `https://github.com/robertmartin8/PyPortfolioOpt` (`pypfopt/efficient_frontier.py`, `hrp.py`, `black_litterman.py`).
- **Extract:** `HRP` (hierarchical risk parity), `BlackLitterman`, `L2_reg(gamma=0.1)` to de-concentrate weights; cookbook notebooks.
- **Effort:** low (swap in `compute_daily_allocation`).

## Prioritized Extraction Plan for Vinu

1. **Immediate (next build slice A1-A2):** Freqtrade leak guard → Row 1 rehearsal validation; Qlib PIT contract → Row 15 window determinism; FinRL 5-agent tutorial clone → Row 6 comparison baseline.
2. **Next (A3-A4):** PyPortfolioOpt HRP/L2 → Row 5 sizing decision; VectorBT vectorized sweep spike → speed Row 7 tuning; Nautilus fill model diff → Row 14 shadow reconciliation (tick-level vs Sharpe-only `shadow_evaluator.py:23-129`).
3. **Later / conditional:** daily_stock_analysis multi-notify → Row 9 delivery proof; Hummingbot/Qbot/Abu only if targeting crypto market-making or A-shares.

## How to use

```bash
# Audit any of the above locally via the best-of generator index
git clone https://github.com/TitanFlow-Systems/best-of-algorithmic-trading
cd best-of-algorithmic-trading
grep -n "Freqtrade\|Qlib\|Lean\|FinRL\|VectorBT" projects.yaml
# Then visit upstream repo, verify license, test its own install path before depending.
```

## Sources

- TitanFlow-Systems/best-of-algorithmic-trading `README.md` + `projects.yaml` (109 projects, 310K stars, quality score) — `https://github.com/TitanFlow-Systems/best-of-algorithmic-trading`
- wilsonfreitas/awesome-quant `README.md` (29.4K stars) — `https://github.com/wilsonfreitas/awesome-quant`
- Grokipedia `Popular open-source quantitative trading projects (2025–2026)` (Qlib 39K+, Qbot 16K+, Abu 16K+, daily_stock_analysis 25K) — `https://grokipedia.com/page/Popular_open-source_quantitative_trading_projects_20252026`
- Direct GitHub reads Sep 7 2026: `QuantConnect/Lean` (21.5K), `freqtrade/freqtrade` (54.1K), `microsoft/qlib` (48.3K), `AI4Finance-Foundation/FinRL` (16.2K), `polakowo/vectorbt` (9.0K), `nautechsystems/nautilus_trader` (28.5K), `quantopian/zipline` (20.0K)
- Intraday trend via `gitstarclub.com/QuantConnect/Lean` (+766 Jul 2026), `trendingbots.ai/agents/qlib` (+360/wk)

---
*Next: pick 2-3 packages from the Immediate list to actually spike in `vinu-research`/`vinu-simulator` and update `pending-items-to-be-implemented.md` row status from `pending` to `spiked`.*
