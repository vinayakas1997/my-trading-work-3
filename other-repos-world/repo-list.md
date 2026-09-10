# Reference Repos — Ranked List

Source: `personal-important/new-vision/05-other-repos-research.md` (18 repos originally ranked by stars, Sep 2026 snapshot) + `ref-fincept-terminal` found separately. All 19 were cloned and fully audited by 5 parallel research agents reading actual source (see `repo-research-findings.md` for the full per-repo writeup: advanced features, why people trust it, adoptable logic vs Vina).

Star counts are the Sep 2026 snapshot from the source doc (not re-verified). "First Released" and "Last Updated" were pulled fresh from the GitHub API.

## Filtering pass (after the full audit)

Of the 19, **6 turned out redundant or low-value once compared against what the other 13 already cover** — their cloned folders have been **deleted from `other-repos-world/repos/`** to keep the working set lean (freed ~1.86G):

| Repo | Why cut |
|---|---|
| awesome-quant | Pure index/catalog, no runtime code — the few useful pointers (`pit-release-gate`, `lookahead-free`) were already extracted into the findings doc. |
| best-of-algorithmic-trading | Same — a catalog/generator, and what it lists is almost entirely crypto/multi-exchange bots, out of scope for Vina. |
| Qbot | Audit's own verdict: "nothing structural... little else rises above boilerplate" — a thin wrapper around backtrader/easytrader tutorials. Its one real idea (index-drawdown kill-switch) is done better by FinRL and TradeMaster. |
| Zipline | Unmaintained since Feb 2024. Its one standout idea (Pipeline factor/filter graph) is better covered by Qlib's expression engine (actively maintained) + Lean's coarse→fine universe selection. |
| vn.py / VeighNa | Its main strength (multi-broker gateway abstraction) isn't needed — Vina is single-broker (Alpaca) by design. Its factor pipeline overlaps Qlib's more mature expression engine. |
| TradeMaster | Academic RL benchmark, no live/broker code at all. Its one useful idea (data-derived regime labeling) is a fancier version of what FinRL's turbulence index already gives cheaply. |

**13 kept** — each contributed at least one pattern nothing else did. Table below is renumbered with the 13 keepers first, the 6 cut repos listed last for the record.

## Kept (13) — cloned in `other-repos-world/repos/`

| # | Repo | GitHub Link | Stars (Sep 2026) | First Released | Last Updated | Description |
|---|---|---|---|---|---|---|
| 1 | Freqtrade | https://github.com/freqtrade/freqtrade | 54.1K | 2017-05-17 | 2026-09-08 | Free crypto bot: backtest → hyperopt (ML) → dry-run → live on 20+ exchanges via CCXT, Telegram/WebUI/REST control, FreqUI, FreqAI (RL). |
| 2 | Qlib | https://github.com/microsoft/qlib | 48.4K | 2020-08-14 | 2026-09-02 | Microsoft AI-oriented end-to-end quant platform: data → factor mining → model zoo (LGBM/Transformer) → portfolio opt → execution; Point-in-Time DB; RD-Agent LLM autonomous R&D. |
| 3 | NautilusTrader | https://github.com/nautechsystems/nautilus_trader | 28.6K | 2018-06-25 | 2026-09-10 | Production-grade deterministic event-driven engine (Rust core + Python), nanosecond precision, Parquet catalog, configurable fill/fee/latency/book models, backtest→live parity. |
| 4 | daily_stock_analysis | https://github.com/ZhuLinsen/daily_stock_analysis | 25K | 2026-01-10 | 2026-09-06 | LLM-driven daily dashboard for A/H/US markets: multi-source quotes + news + sentiment, auto decision dashboard, multi-channel notify. **Ships a production rule-based full-market scanner — highest-value repo for vinu-screener.** |
| 5 | Lean | https://github.com/QuantConnect/Lean | 21.5K | 2014-11-28 | 2026-09-09 | Event-driven multi-asset engine (equities/options/futures/crypto/forex), broker adapters (IBKR/Coinbase/Binance/OANDA), CLI (backtest/optimize/live), cloud hybrid. |
| 6 | Hummingbot | https://github.com/hummingbot/hummingbot | 18K | 2019-04-02 | 2026-09-09 | Market-making & arbitrage bot, connector architecture for exchanges. |
| 7 | Abu (阿布量化) | https://github.com/bbfamily/abu | 16.6K | 2016-09-19 | 2026-01-24 | A-share/HK + futures/options/BTC quant framework, ML + position management. China-market factor library. |
| 8 | FinRL | https://github.com/AI4Finance-Foundation/FinRL | 16.2K | 2020-07-26 | 2026-07-13 | First financial RL library: 5-agent bake-off (A2C/DDPG/PPO/TD3/SAC) vs MVO/DJIA baselines, Gym envs; successor line FinRL-Trading/FinRL-Meta. |
| 9 | VectorBT | https://github.com/polakowo/vectorbt | 9.0K | 2017-11-14 | 2026-08-02 | Vectorized backtesting: thousands of parameter combos via NumPy/Numba/Rust in seconds, pandas-native, TA-Lib, QuantStats, signal ranking. |
| 10 | StockSharp | https://github.com/StockSharp/StockSharp | 9.4K | 2014-12-08 | 2026-09-07 | Algo trading platform in C#. Less relevant unless porting to a C# component. |
| 11 | PyPortfolioOpt | https://github.com/robertmartin8/PyPortfolioOpt | ~3.4K | 2018-05-29 | 2026-07-07 | Efficient frontier, Black-Litterman, shrinkage, HRP, L2 regularization, objective functions for portfolio construction. |
| 12 | pysystemtrade | https://github.com/robcarver17/pysystemtrade | ~2K | 2015-11-27 | 2026-07-18 | Rob Carver's "Systematic Trading" framework: forecast → position → portfolio rules pipeline. |
| 13 | FinceptTerminal | https://github.com/Fincept-Corporation/FinceptTerminal | 31.3K | 2024-08-29 | 2026-09-08 | Full C++/Qt financial terminal. Has a mature scan engine under `fincept-qt/src/algo_engine/` (`ConditionEvaluator`, `ScanMonitor`, `RealtimeScanRunner`, `AlgoScanner`) — the closest match found to "set a rule, set a frequency, get notified" for `vinu-screener`. Note: June 2026 maintenance notice (moving to monthly public updates, team refocused on a paid private edition) — still actively pushed as of Sep 2026. |

## Cut (6) — deleted from `other-repos-world/repos/`, kept here for the record only

| # | Repo | GitHub Link | Stars (Sep 2026) | First Released | Last Updated | Description |
|---|---|---|---|---|---|---|
| 14 | awesome-quant | https://github.com/wilsonfreitas/awesome-quant | 29.4K | 2015-09-30 | 2026-09-09 | Curated 25-language index of numerical libs, pricing, indicators, trading & backtesting tools, reproducible books. Meta-list, not runtime. |
| 15 | best-of-algorithmic-trading | https://github.com/merovinh/best-of-algorithmic-trading | 253 | 2023-01-07 | 2026-09-04 | Generator that produces a weekly ranked `projects.yaml` of quant/trading repos by quality score. Meta tool, not a trading system itself. **Correction: actual owner is `merovinh`, not `TitanFlow-Systems` as the source doc had it — verified via GitHub API.** |
| 16 | Qbot | https://github.com/UFund-Me/Qbot | 16.7K | 2022-11-23 | 2026-03-11 | AI quant robot, full local deployment, Chinese broker APIs (Haitong/Huatai), RL/DL, WeChat community. |
| 17 | Zipline | https://github.com/quantopian/zipline | 20.1K | 2012-10-19 | 2024-02-13 | Pythonic algo library that powered Quantopian; Pipeline API for cross-sectional factor screening of a full universe. **Unmaintained — last push Feb 2024.** |
| 18 | vn.py / VeighNa | https://github.com/vnpy/vnpy | ~13K | 2015-03-02 | 2026-09-01 | Multi-gateway event-driven platform for China futures/stocks/crypto. Gateway pattern. |
| 19 | TradeMaster | https://github.com/TradeMaster-NTU/TradeMaster | 3.1K | 2022-08-23 | 2025-06-04 | RL platform (HKUST) with configs for algorithmic_trading/high_frequency/order_execution/portfolio_management + PRIDE-Star 8-metric eval. |

## Not on this ranked list (found separately, already cloned in `personal-important/other-reference-repos/`)

| Repo | GitHub Link | Notes |
|---|---|---|
| **Vibe-Trading** | **https://github.com/HKUDS/Vibe-Trading** | **Fully audited 2026-09-10** — full writeup at `comprison-other-vinu/14-vibe-trading.md`. 33.1K stars, created 2026-04-01, pushed 2026-09-10 — actively maintained by HKUDS. Has real scanner/screener code (`market_screener_tool.py`, `shadow_account/scanner.py`) — already reviewed for the screener design. Also the source repo for **the LLM-agent concept adopted into Vina's own agent design** (per user, 2026-09-10) — turned out to have a near-exact structural analog to Vina's own OrderGuard/TradingMandate (`live/mandate/`, `live/order_guard.py`, `live/halt.py`), independently arrived at. Now re-cloned into `other-repos-world/repos/` and treated as a 14th audited repo (6 new adoptable items added to `adoption-tracker.md`). |
| ref-FinRobot | (link unknown — cloned already, no URL captured) | LLM-agent finance robot framework. Not part of the 13/19 audit above. |

## Referenced but not actually available (empty placeholders, no content)

| Name | Status |
|---|---|
| jarvis-trading-bot | Empty folder in `personal-important/other-reference-repos/` — no `.git`, no files. Real GitHub URL unknown; needs the user to supply it before cloning. |
| Jarvis | Same — empty placeholder, not the tracked "Jarvis-like watcher-agent" concept mentioned in `new-vision/04-new-full-explanation.md` (that's a deferred idea, not a repo). |
