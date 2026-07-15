# Additional Research Angles (Sonnet Contribution)

These 13 angles (25–37) extend the original 19-angle taxonomy (`mimi-agent-analysis/02-different-angles-on-asset.md`) and Gemini's 5 advanced angles (`gemini-agent-analysis/gemini-differnt-angles-on-asset.md`, angles 20–24). Numbering continues from 25 to avoid collision.

Unlike Gemini's set — which is entirely new external-data buildout — about half of these are **already buildable from code and data that exist in the repo today**, just never framed as their own research angle. Each angle is marked with its real status, verified against the current codebase (not assumed), with exact file paths.

**Status legend:** `Present` (fully wired, callable today) · `Partially present` (building blocks exist, needs an assembly/harness layer) · `Yet to be implemented` (no code, and/or no data source, exists)

---

## ANGLE 25: ML / Quantitative Prediction Engine
**Question:** Which machine-learning model best predicts this asset's forward returns, and which features actually drive it?

| Dimension | What You Learn | Status |
|-----------|---------------|--------|
| Model comparison | Linear / Ridge / Lasso / ElasticNet / Logistic / Random Forest / LightGBM / XGBoost / CatBoost scored against the same label | Present |
| Out-of-sample Information Coefficient | Spearman rank correlation between `ml_score` and true forward return, held-out slice only | Present (recently fixed) |
| Best-model selection | Automated ranking across models by OOS IC | Present |
| Feature importance / SHAP | Which of the 619 alpha factors + 22 named indicators actually drove the prediction | Yet to be implemented |
| Label engineering | Forward-return horizon, classification vs regression targets | Present |

**Current Implementation Details & Architecture Gaps:**
* **Status**: *Present*, and this is the most surprising omission from the original 19-angle doc — 9 real ML models already live in [vinu_features/compute/ml_models/](file:///c:/Users/vinay/Desktop/my-trading-work-3/vinu-components/vinu-features/vinu_features/compute/ml_models/) (`linear_regression/`, `ridge/`, `lasso/`, `elastic_net/`, `logistic_regression/`, `random_forest/`, `lightgbm/`, `xgboost/`, `catboost/`), dispatched by `registry.py` and orchestrated by `runner.py`.
* **The known blocker**: as of the last deep-dive session (`personal-important/advanced-vision-plan/advanced-part-2-plan.md`, bug #7), `runner.py` historically fit and predicted on the identical array (no train/test split), producing fabricated in-sample scores (0.878 "correlation" that was pure memorization). Phase 1 of that plan calls for a time-ordered holdout split — check whether it has since landed before trusting any `ml_score` output.
* **What's missing to complete this angle**: a `select_best(models, X, y)` ranking helper (scoped in the same plan doc, §1.3) and a feature-importance/SHAP export — neither exists yet.

**Example:** "AAPL: XGBoost beats Random Forest and Ridge on OOS IC (0.09 vs 0.04 vs 0.02, held-out slice only). Top 3 features: BETA_30, ROC_20, SUMP_10."

---

## ANGLE 26: Multi-Factor Style / Risk Decomposition
**Question:** Is this asset's (or strategy's) return genuinely alpha, or just a disguised bet on well-known style factors?

| Dimension | What You Learn | Status |
|-----------|---------------|--------|
| Single-factor CAPM beta/alpha | Market sensitivity and excess return vs one benchmark | Present |
| Multi-factor regression (Fama-French 5 + Momentum) | How much of the return is explained by SMB/HML/RMW/CMA/MKT_RF/momentum simultaneously | Yet to be implemented |
| Factor exposure drift | Does the asset's style-factor loading change over time (value → growth rotation, etc.) | Yet to be implemented |
| Residual alpha significance | t-stat on the regression intercept after controlling for all style factors | Yet to be implemented |

**Current Implementation Details & Architecture Gaps:**
* **Status**: *Partially present*. `vinu_simulator/engine/attribution.py::beta_regression()` already computes single-factor beta/alpha/tracking-error/information-ratio against one benchmark series (used by Angle 12's benchmark comparison). Separately, the raw factor time series already exist as computable columns: [alpha_factors/academic/smb.py, hml.py, rmw.py, cma.py, mkt_rf.py, carhart_mom.py](file:///c:/Users/vinay/Desktop/my-trading-work-3/vinu-components/vinu-features/vinu_features/compute/alpha_factors/academic/).
* **What's missing**: nothing currently regresses an asset/strategy against *all* of those factors simultaneously (a multi-variate OLS instead of `beta_regression`'s single covariate). This is a genuinely small lift — `beta_regression`'s structure generalizes directly to `statsmodels.OLS` with 6 regressors instead of 1.

**Example:** "TSLA: after controlling for MKT_RF, SMB, HML, RMW, CMA, and momentum simultaneously, residual alpha is 2.1%/yr (t=0.8, not significant) — the apparent outperformance is almost entirely a momentum + small-cap-growth loading, not stock-specific skill."

---

## ANGLE 27: Seasonality & Calendar Effects
**Question:** Does this asset have a systematic edge tied to the calendar rather than to any signal?

| Dimension | What You Learn | Status |
|-----------|---------------|--------|
| Day-of-week effect | Average/median return by weekday | Yet to be implemented |
| Month-of-year effect | "Sell in May," January effect, Santa Claus rally | Yet to be implemented |
| Turn-of-month drift | Return concentration in the last/first N trading days of the month | Yet to be implemented |
| Pre-holiday drift | Return in the session(s) before market holidays | Yet to be implemented |
| Day-before/-after FOMC drift | Overlaps with Gemini's Angle 21 but at the single-session level rather than a full macro-beta regression | Yet to be implemented |

**Current Implementation Details & Architecture Gaps:**
* **Status**: *Yet to be implemented as its own angle*, but the only missing piece is a grouping/aggregation layer — every OHLCV bar already carries a timestamp via [vinu-stock-price](file:///c:/Users/vinay/Desktop/my-trading-work-3/vinu-components/vinu-stock-price/), and `vinu_features/compute/indicators/session/session.py` already demonstrates the exact pattern needed (pure function of bar timestamp → category). Seasonality is presently buried as one throwaway "theme" tag under Angle 4's factor-zoo taxonomy and never actually computed.
* **What's missing**: a `calendar_effects` indicator/report that groups existing daily returns by weekday/month/turn-of-month and reports mean, t-stat, and sample size per bucket. This requires zero new data ingestion — it's a pure aggregation over data the system already stores.

**Example:** "MSFT: Monday returns average -0.04% (n=520, t=-0.9, not significant) vs. Turn-of-month (last 2 + first 3 trading days) average +0.11% (n=260, t=2.3, significant at 5%) — a real, small, exploitable calendar effect."

---

## ANGLE 28: Cross-Timeframe Signal Decay
**Question:** At what horizon does this factor/signal actually work, and when does its edge disappear?

| Dimension | What You Learn | Status |
|-----------|---------------|--------|
| Per-factor decay horizon | Each alpha factor already declares how many periods until its signal fades | Present (metadata only) |
| Multi-interval IC comparison | Does the same factor's OOS IC hold up at 15m vs 1h vs 1d vs 1w | Yet to be implemented |
| Signal half-life measurement | Empirically fit decay curve vs the factor's declared `decay_horizon` | Yet to be implemented |
| Interval-aware annualization | Metrics correctly annualized regardless of bar granularity | Present |

**Current Implementation Details & Architecture Gaps:**
* **Status**: *Partially present*. Every factor in the zoo already carries a `decay_horizon` attribute (declared, per Angle 4 of the original doc) and `vinu_simulator/engine/metrics.py::periods_per_year_for_interval()` already makes Sharpe/CAGR/Sortino correctly interval-aware (1m/5m/15m/30m/1h/4h/1d) — this was a hard-won fix (see `advanced-part-2-plan.md` bug #6, previously hardcoded to `√252` and silently invalid at all intraday granularities).
* **What's missing**: nothing actually *exercises* the `decay_horizon` field. There's no harness that runs the same factor's backtest at multiple intervals and plots OOS IC against horizon to confirm (or falsify) the declared decay assumption.

**Example:** "alpha101_012 declares decay_horizon=60 (bars). Empirically: OOS IC=0.06 at 1d (60 bars ≈ 3 months, matches), IC=0.01 at 15m (60 bars ≈ 1 trading day — signal has already decayed by then), confirming the factor is a daily-frequency signal, not intraday."

---

## ANGLE 29: Data Quality & Provider Reconciliation
**Question:** Can the underlying price/volume data itself be trusted?

| Dimension | What You Learn | Status |
|-----------|---------------|--------|
| Cross-provider OHLCV diff | Do Alpaca, Polygon, Yahoo, yfinance, and Tushare agree on this asset's bars | Yet to be implemented |
| Corporate-action adjustment consistency | Are splits/dividends applied consistently across providers | Yet to be implemented |
| Gap/staleness detection | Missing bars, stale ticks, backfill completeness | Partially present |
| Survivorship-bias check | Is the historical universe free of delisted-name removal bias | Yet to be implemented |

**Current Implementation Details & Architecture Gaps:**
* **Status**: *Partially present*. [vinu-stock-price](file:///c:/Users/vinay/Desktop/my-trading-work-3/vinu-components/vinu-stock-price/vinu_stock/providers/) already ships 5 independent OHLCV providers (`alpaca.py`, `polygon.py`, `yahoo.py`, `yfinance.py`, `tushare.py`) with a priority/role-based `registry.py` and per-provider `retry.py` — but they're used as *fallbacks* (use provider B if provider A fails), never *reconciled* against each other. The `catalog/store.py` SQLite catalog tracks what's been backfilled, which is the natural place to add a diff report.
* **Why this matters concretely**: the project's own bug list already found one silent data-integrity failure this way — `advanced-part-2-plan.md` bug #3, where `vinu-features`'s row-normalizer only recognized `ts`/`timestamp`/`sort_ts` as the bar-timestamp key but `vinu-stock-price`'s candles API returns `bar_ts`, silently dropping every row (`row_count: 0`, reported as a "successful" run). A reconciliation angle is exactly the kind of check that would have caught this class of bug automatically instead of via hours of manual investigation.
* **What's missing**: a scheduled or on-demand job that pulls the same symbol/date range from 2+ providers and reports bar-level divergence (price, volume, missing bars).

**Example:** "AAPL 2024-03-15: Alpaca and Polygon agree within 0.01% on close price for 98.7% of bars; the 1.3% divergence cluster is entirely on days with after-hours corporate actions, flagged for manual review before backtesting through that window."

---

## ANGLE 30: Meta-Portfolio / Strategy-of-Strategies Allocation
**Question:** If I have several independently-validated strategies, how should capital be split across them?

| Dimension | What You Learn | Status |
|-----------|---------------|--------|
| Single-strategy ranking | Rank candidate strategies for one asset by risk-adjusted return | Present |
| Cross-strategy correlation | Are two PASSing strategies actually diversifying, or redundant | Partially present |
| Multi-strategy capital allocation | Equal-weight / risk-parity / Sharpe-weighted split across accepted strategies | Yet to be implemented |
| Combined equity curve | What does the portfolio of strategies look like, not just the portfolio of assets | Yet to be implemented |

**Current Implementation Details & Architecture Gaps:**
* **Status**: *Partially present*. [vinu_research/comparison.py](file:///c:/Users/vinay/Desktop/my-trading-work-3/vinu-components/vinu-research/vinu_research/comparison.py)'s `rank_candidates()`/`best_candidate()` already rank multiple strategy *candidates* for the same research run — but that's single-strategy selection, not portfolio construction. Separately, [vinu_research/portfolio.py](file:///c:/Users/vinay/Desktop/my-trading-work-3/vinu-components/vinu-research/vinu_research/portfolio.py) already has `compute_correlation_matrix()`, `compute_rolling_beta()`, and `analyze_portfolio()` — but built for a portfolio of *assets*, not a portfolio of *strategies' equity curves*.
* **What's missing**: the same correlation-matrix/allocation machinery in `portfolio.py`, fed with strategy-level return series instead of asset-level ones — architecturally this is the same math applied one layer up, not a new subsystem.

**Example:** "3 PASSing strategies on AAPL (MA-crossover, RSI mean-reversion, news-aware momentum) have pairwise correlation 0.15–0.31 — genuinely diversifying. Risk-parity blend: combined Sharpe 1.4 vs the best single strategy's 1.1."

---

## ANGLE 31: Execution Quality Audit (Realized vs. Modeled Cost)
**Question:** Once a strategy trades for real, does the backtest's cost model still hold up?

| Dimension | What You Learn | Status |
|-----------|---------------|--------|
| Modeled vs. realized slippage | Almgren-Chriss prediction vs actual fill price divergence | Yet to be implemented |
| Modeled vs. realized fees | Assumed 0.1% fee / 0.05% slippage vs. actual broker statement | Yet to be implemented |
| Cost-model recalibration | Feed realized data back into the cost model's parameters | Yet to be implemented |
| Trade-journal pattern extraction | What entry/exit patterns actually occurred, clustered | Present |

**Current Implementation Details & Architecture Gaps:**
* **Status**: *Partially present*. The shadow-trading pipeline already exists end-to-end — [vinu_research/shadow/](file:///c:/Users/vinay/Desktop/my-trading-work-3/vinu-components/vinu-research/vinu_research/shadow/) has `extractor.py` (FIFO round-trip pairing from a trade journal), `backtester.py`, `attribution.py`, and `reporter.py`. The cost models themselves (`FlatCostModel`, `AlmgrenChrissCostModel` in `vinu_simulator/engine/costs.py`) are fully built and already parameterized (`transaction_cost_pct`, `slippage_pct`).
* **What's missing**: nothing currently closes the loop between "what the cost model predicted" and "what a real (or shadow/paper) trade actually cost." This requires realized fill data as an input, which the shadow module is positioned to ingest but doesn't yet compare against the simulator's cost-model prediction for the same trade.
* **Why this matters**: the project's own bug list already surfaced a related failure mode — `advanced-part-2-plan.md` bug #5, where a 100%-notional target weight always failed to buy because `cost = notional × (1 + fees + slippage + impact)` exceeded available cash with no buffer, silently skipping every trade rather than erroring. An execution-quality audit is the kind of check that catches cost-model assumptions breaking down in practice, not just in theory.

**Example:** "Shadow AAPL trades over 30 days: modeled slippage assumed 0.05%, realized average slippage was 0.14% — 2.8x higher, concentrated in trades executed in the first 15 minutes of the session. Cost-model recalibration recommended before scaling position size."

---

## ANGLE 32: Institutional Ownership & 13F Flow
**Question:** Are large institutional holders accumulating or distributing this asset?

| Dimension | What You Learn | Status |
|-----------|---------------|--------|
| 13F quarterly holdings changes | Net institutional buying/selling by fund, aggregated | Yet to be implemented |
| Ownership concentration | % of float held by top-N institutions | Yet to be implemented |
| New/exited positions | Which funds initiated or fully exited this quarter | Yet to be implemented |
| Ownership vs. price divergence | Does price move ahead of or behind disclosed institutional flow (13F is lagged, quarterly) | Yet to be implemented |

**Current Implementation Details & Architecture Gaps:**
* **Status**: *Yet to be implemented* — zero code presence (confirmed via repo-wide search for `insider|13f|short.interest`, no real hits outside unrelated third-party packages). This is distinct from Gemini's Angle 24 (SEC Section 1A risk-factor NLP + Form 4 insider transaction *velocity*) — 13F is institutional *fund-level* holdings, a different filing type (13F-HR) and a different signal (slow-moving, quarterly, large-holder positioning rather than executive-level buy/sell).
* **What's needed**: a new SEC EDGAR 13F ingestion pipeline (quarterly, ~45-day reporting lag by design) — no existing provider in `vinu-stock-price` or elsewhere touches SEC filings at all.

**Example:** "NVDA: 13F filings show net institutional accumulation of 2.1M shares last quarter, led by 3 new fund initiations >$50M — but this data is inherently 45+ days stale by disclosure rules, so it's a positioning-confirmation signal, not a timing signal."

---

## ANGLE 33: Analyst Estimates & Revisions Momentum
**Question:** Is Wall Street getting more or less optimistic about this asset, and does that predict returns?

| Dimension | What You Learn | Status |
|-----------|---------------|--------|
| EPS estimate revisions | Direction/magnitude of analyst EPS estimate changes over time | Yet to be implemented |
| Price-target revisions | Analyst price-target changes, dispersion across analysts | Yet to be implemented |
| Rating changes | Upgrade/downgrade frequency and magnitude | Yet to be implemented |
| Earnings surprise history | Beat/miss streak, whisper number vs. consensus | Yet to be implemented |

**Current Implementation Details & Architecture Gaps:**
* **Status**: *Yet to be implemented*. This is distinct from Angle 17 (Fundamentals) in the original taxonomy — Angle 17's `fundamentals_tool.py` (in [vinu-agent/vinu_agent/tools/](file:///c:/Users/vinay/Desktop/my-trading-work-3/vinu-components/vinu-agent/vinu_agent/tools/fundamentals_tool.py)) pulls *static* ratios (PE, ROE, debt/equity) live from `yfinance` on each call — it does not track revisions or estimate momentum over time, which is one of the more robustly documented factors in the academic literature (estimate-revision momentum).
* **Worth flagging separately**: Angle 17 as currently implemented lives inside `vinu-agent`'s tool layer, not as its own deterministic microservice the way `vinu-features`/`vinu-correlation` are — so today it's technically reachable without an LLM (the `yfinance` call itself is deterministic), but it's coupled to the agent's tool wrapper rather than architected as a standalone service like the other 18 original angles.
* **What's needed**: a time-series estimates provider (yfinance's estimate history is thin; a dedicated provider like a broker-consensus feed would be needed for real revision-momentum tracking) plus storage for historical snapshots (a single live `yfinance` call can't show revision *direction* without a stored prior value to diff against).

**Example:** "AAPL: consensus FY2026 EPS estimate revised up 3 times in the last 60 days (+4.2% cumulative), with price target dispersion narrowing from $210–$260 to $225–$245 — estimate convergence typically precedes reduced post-earnings volatility."

---

## ANGLE 34: Credit & Capital Structure Signals
**Question:** Is the bond/credit market signaling stress before the equity market notices?

| Dimension | What You Learn | Status |
|-----------|---------------|--------|
| Credit spread trend | Corporate bond spread vs. Treasury, widening/narrowing | Yet to be implemented |
| CDS pricing | Credit default swap spread as a real-time distress gauge | Yet to be implemented |
| Credit-rating change history | Moody's/S&P/Fitch upgrade/downgrade timeline | Yet to be implemented |
| Credit-equity lead-lag | Does spread widening precede equity drawdowns for this name | Yet to be implemented |

**Current Implementation Details & Architecture Gaps:**
* **Status**: *Yet to be implemented* — zero code presence, and no adjacent building block exists (unlike Angles 26/27/28/30/31 above). This requires an entirely new data provider (bond pricing / CDS data is a different asset class from the equity-only OHLCV that all 5 existing `vinu-stock-price` providers serve).
* **Why it's worth the build**: credit stress historically leads equity stress by days to weeks for the same issuer — this is one of the more distinct, non-redundant signal sources relative to everything else in the 24-angle set so far (all of which are either price-derived, news-derived, or equity-fundamentals-derived).

**Example:** "AAPL 5Y CDS spread widened 8bps over 2 weeks while equity price was flat — a divergence that historically precedes a 3–5% equity drawdown within 20 trading days for large-cap tech names."

---

## ANGLE 35: Alt-Data & Social Sentiment
**Question:** What is retail/public attention doing, separate from professional news coverage?

| Dimension | What You Learn | Status |
|-----------|---------------|--------|
| Reddit/Twitter/StockTwits sentiment | Retail sentiment velocity and volume, distinct from Angle 1's professional-news sentiment | Yet to be implemented |
| Google Trends search volume | Public attention as a leading/coincident indicator | Yet to be implemented |
| App download / web-traffic alt-data | Company-specific consumer-engagement proxies | Yet to be implemented |
| Retail vs. professional sentiment divergence | Does retail chatter diverge from what `vinu-news`'s enrichment pipeline scores | Yet to be implemented |

**Current Implementation Details & Architecture Gaps:**
* **Status**: *Yet to be implemented*. [vinu-news](file:///c:/Users/vinay/Desktop/my-trading-work-3/vinu-components/vinu-news/) is the only "soft data" source in the entire platform, and it's exclusively RSS/news-wire — no social-media or search-trend ingestion exists. The rule-based enrichment pipeline (`analysis/enrichment/{sentiment,impact,category,priority,threat,source_credibility,ticker_extractor,ticker_dominance}.py`) is a strong, reusable template for *how* to build this (keyword/rule-based scoring, fully deterministic, no LLM needed) — it just currently only ever sees professional news-wire text, never social posts.
* **What's needed**: new RSS-equivalent collectors for Reddit/Twitter/StockTwits APIs and Google Trends, feeding into the same enrichment pattern already proven out in `vinu-news`.

**Example:** "GME: Reddit mention velocity spiked 8x baseline z-score over 48h while professional news volume (Angle 1) stayed flat — a retail-led move with no corresponding institutional news catalyst, historically higher-volatility and lower-persistence than news-driven moves."

---

## ANGLE 36: Historical Scenario / Crisis Replay
**Question:** How would this strategy have performed during a specific past crisis, not just across its own randomized history?

| Dimension | What You Learn | Status |
|-----------|---------------|--------|
| Named-crisis replay | Run current strategy logic against 2008 GFC, 2020 COVID crash, 2022 rate-shock price data | Yet to be implemented |
| Regime-conditional stress | Isolate performance specifically during historically-labeled bear/crash windows | Partially present |
| Cross-asset contagion scenario | What happens to this asset if a correlated asset/sector crashes | Yet to be implemented |

**Current Implementation Details & Architecture Gaps:**
* **Status**: *Partially present*, and worth distinguishing carefully from what already exists. Angle 11's Monte Carlo permutation (`vinu_simulator/engine/validation.py::monte_carlo_permutation`) reshuffles *this asset's own* trade P&Ls — it tests whether the *ordering* of realized trades mattered, not whether the strategy survives a *specific, different, worse* historical regime. Angle 9's regime classification (`engine/regime.py::classify_regime`) labels bull/bear/high-vol/sideways *within* the backtest period already run — it doesn't let you inject an external crisis period the strategy never saw.
* **What's missing**: a scenario-replay harness that takes the strategy's `generate_weights()` logic and runs it against a *different*, specifically-chosen historical price window (e.g. splice in March 2020's SPY path) — this is a data/harness problem, not a hard math problem, since all the metrics/backtest machinery (`WeightSimulator`, `compute_full_metrics`) already accepts arbitrary price series as input.

**Example:** "MA-crossover strategy on AAPL, replayed against the March 2020 crash price path: -22% max drawdown in 15 trading days vs. the strategy's own historical worst-case of -19% over 354 days — the strategy has never actually been tested against a move this fast, even though its own backtest 'passed.'"

---

## ANGLE 37: Regulatory & Market-Structure Events
**Question:** Are there structural trading constraints on this asset that price/volume data alone won't reveal?

| Dimension | What You Learn | Status |
|-----------|---------------|--------|
| Trading halts | LULD halts, volatility circuit breakers, news-pending halts | Yet to be implemented |
| Short-sale restriction (SSR) | Uptick-rule trigger days | Yet to be implemented |
| Delisting / compliance risk | Exchange notices, minimum-price/market-cap compliance deadlines | Yet to be implemented |
| Index inclusion/exclusion | S&P 500 addition/removal-driven forced flows | Yet to be implemented |

**Current Implementation Details & Architecture Gaps:**
* **Status**: *Yet to be implemented* — zero code presence. Lowest priority of the 13 angles here for liquid large-cap names (the primary use case implied by the existing news/technicals/factor stack), but material for small-caps, meme-stocks, or any name near compliance thresholds.
* **What's needed**: an exchange-notice/halt-feed provider — none of the existing 5 OHLCV providers in `vinu-stock-price` surface halt or SSR status as a first-class field (halts typically show up only indirectly, as a gap or a suspiciously flat/thin bar).

**Example:** "Small-cap XYZ: 3 LULD volatility halts in the trailing 30 days, each followed by a mean-reversion of ~40% of the pre-halt move within 2 hours — halts here are a distinct, tradeable microstructure signal that pure OHLCV analysis would miss entirely."

---

## Summary Table

| Angle | Name | Status | New Data Source Needed? |
|-------|------|--------|--------------------------|
| 25 | ML / Quantitative Prediction | Present (blocked by known bug) | No |
| 26 | Multi-Factor Style Decomposition | Partially present | No |
| 27 | Seasonality & Calendar Effects | Yet to be implemented | No |
| 28 | Cross-Timeframe Signal Decay | Partially present | No |
| 29 | Data Quality & Provider Reconciliation | Partially present | No |
| 30 | Meta-Portfolio / Strategy-of-Strategies | Partially present | No |
| 31 | Execution Quality Audit | Partially present | No (needs realized fill data) |
| 32 | Institutional Ownership & 13F Flow | Yet to be implemented | Yes (SEC EDGAR 13F) |
| 33 | Analyst Estimates & Revisions | Yet to be implemented | Yes (estimates provider) |
| 34 | Credit & Capital Structure | Yet to be implemented | Yes (bond/CDS data) |
| 35 | Alt-Data & Social Sentiment | Yet to be implemented | Yes (social/trends APIs) |
| 36 | Historical Scenario / Crisis Replay | Partially present | No |
| 37 | Regulatory & Market-Structure Events | Yet to be implemented | Yes (halt/exchange feed) |

**7 of 13 angles need zero new data source** — they're assembly/harness work on top of code that already exists (ML models, factor time series, OHLCV timestamps, decay metadata, multi-provider ingestion, strategy ranking, shadow trade extraction, cost models, Monte Carlo/regime machinery). The remaining 6 (institutional ownership, analyst estimates, credit, alt-data, and regulatory events) genuinely require onboarding a new external data provider each — the same category of work as Gemini's Angles 20–24.
