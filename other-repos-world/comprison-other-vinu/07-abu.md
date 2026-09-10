# abu (abupy / 阿布量化)

https://github.com/bbfamily/abu · 16.6K stars · First released 2016-09-19 · Last updated 2026-01-24

## Advanced Features

- **"Ump" (裁判/umpire) ML veto layer** (`abupy/UmpBu/ABuUmpMainBase.py`) — trains a Gaussian Mixture Model on historical trade feature vectors (`abupy/TradeBu/ABuMLFeature.py`) to cluster trades by outcome, then identifies clusters with a failure rate above a `threshold` (default 0.65) and treats membership in those clusters as a **veto signal that blocks a live trade before execution** (`_do_gmm_cluster`). A family of judges (`ABuUmpMainDeg/Full/Jump/Mul/Price/Wave` main judges, `ABuUmpEdge*` edge/auxiliary judges) is orchestrated by `abupy/UmpBu/ABuUmpManager.py`. Essentially a learned, statistically-grounded pre-trade gate layered on top of the strategy's own buy signal.
- **Correlation-aware cross-validation** (`abupy/MetricsBu/ABuCrossVal.py`) — `AbuCrossVal.fit`, `_do_cross_corr`, `_find_or_cache_similar` build CV folds not from random symbol splits but from **similarity/correlation clustering**, so a strategy isn't validated on folds full of highly correlated symbols (which would leak signal). Directly targets the same overfitting risk that deflated-Sharpe/holdout testing is meant to catch.
- **Grid search over factor-parameter combinations with scoring** (`abupy/MetricsBu/ABuGridSearch.py`) — `GridSearch.grid_search()` cartesian-products buy/sell factor parameter sets, backtests each, and ranks with a pluggable `WrsmScorer`.
- **Composable buy/sell factor + position-sizing separation** — `abupy/FactorBuyBu` (breakout, trend, demark, wave-detection buy factors), `abupy/FactorSellBu` (three flavors of N×ATR stop-loss, keyed off entry price / pre-bar close / current close respectively), and `abupy/BetaBu` position sizing (`ABuKellyPosition.py` — classic Kelly fraction capped by `pos_max`; `ABuAtrPosition.py` — position size inversely scaled by ATR with a floor to avoid oversizing on abnormally low-volatility names).
- **Intraday slippage fill models with a decorator-based limit-up/limit-down guard** (`abupy/SlippageBu/ABuSlippageBuyMean.py`) — fills at the mean of the day's high/low, but the `@slippage_limit_up` decorator rejects the fill entirely if the stock opened down more than `g_open_down_rate` (7%) from prior close — a domain-specific "don't chase a gap-down" guard.
- **Similarity-based stock picking / trade caching** (`abupy/SimilarBu/ABuSimilar.py`, `ABuCorrcoef.py`) — finds symbols with historically similar price-path behavior via correlation coefficient, used both for stock-picking and to build the correlation-aware validation folds above.

## Why It's Trusted / Mature

abu is the most architecturally serious of the Chinese-origin quant repos audited: it explicitly separates "does the strategy want to trade" (buy/sell factors) from "should we actually let it trade" (the Ump veto layer, trained on realized outcomes) — a genuine two-stage gate most other frameworks don't have. Its grid search and correlation-aware cross-validation give it a defensible answer to "how do we know this isn't overfit," which is close in spirit to what deflated Sharpe + holdout testing does. The Ump layer in particular is notable because it's a learned gate that improves as more realized trade outcomes accumulate, rather than a fixed rule set that never adapts.

## vs Vinu — Gap & Adoptable Logic

**Gap:** Vina's promotion pipeline (`vinu-research`) gates strategy *artifacts* statistically before going live, but has no learned, per-trade veto gate that runs at execution time using clustering over realized trade outcomes — abu's Ump layer is a distinct additional safety mechanism operating at a different point in the pipeline (just before order placement, not just before promotion). Vina also has no correlation-aware CV-fold construction for its holdout testing — folds could currently be full of highly correlated symbols without any explicit guard against it.

**Adopt:**
- Ump-style GMM outcome-cluster veto — featurize each candidate trade (entry conditions, factor triggers), cluster historical trades with GMM, flag clusters with historical failure-rate above a threshold, veto new trades landing in a "bad" cluster. A natural complement to `vinu-agent`'s TradingMandate risk checks — an outcome-informed statistical gate rather than a fixed limit — and could also plug into `vinu-live`'s signal-conflict detection as an additional statistical veto.
- Correlation-clustered CV folds (`_do_cross_corr`) — directly portable idea for `vinu-research`'s holdout testing: build holdout splits so correlated symbols don't span train/test, tightening the deflated-Sharpe gate against cross-symbol leakage.
- The three ATR-stop variants (entry-price / pre-bar-close / current-close keyed) — distinct, nameable stop-rule mechanisms worth enumerating explicitly as options in `vinu-live`'s contingency/invalidation rule engine, rather than one implicit stop convention.
- Kelly-fraction and ATR-inverse position sizing with a hard cap — both cap at `self.pos_max` regardless of formula output, a pattern worth mirroring in `vinu-agent`'s `max position pct` mandate check: let a sizing formula run freely, but always clamp to the hard mandate ceiling as a final step.
- The gap-down fill rejection guard (`@slippage_limit_up`) — a small, concrete execution-realism rule (reject fills after large opening gaps) worth adding to `vinu-simulator`'s fill model.

## Where Vinu Excels

- **A live broker execution path.** abu is a backtest/research framework — it has no live order-submission, no kill switch, no reduce_only exemption, no book↔broker reconciliation. Its Ump veto layer is a genuinely good idea, but it operates purely on historical/backtest trade data, not on Vina's actual live-trading pipeline.
- **Actively maintained, production service architecture.** abu is a single-process research library last meaningfully touched years into its life relative to Vina's actively-developed, per-service (isolated venv/tests per concern) production system — Vina's engineering discipline (test suites, CI-style verification, documented bug fixes) is a different tier of software maturity than a personal quant-research codebase.
- **LLM-assisted research + human-gated promotion**, versus abu's fully automated GMM-cluster veto. abu's Ump layer decides algorithmically with no human review step; Vina's pipeline is designed so a human/statistical gate reviews an LLM-generated artifact before it can trade — a deliberately more conservative posture for real capital.
