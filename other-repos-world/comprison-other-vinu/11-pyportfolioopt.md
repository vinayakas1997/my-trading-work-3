# PyPortfolioOpt

https://github.com/robertmartin8/PyPortfolioOpt · ~3.4K stars · First released 2018-05-29 · Last updated 2026-07-07

## Advanced Features

- **Covariance-matrix regularization / PSD repair** — `fix_nonpositive_semidefinite` offers `spectral` (eigen-decompose, zero out negative eigenvalues, rebuild) and `diag` (ridge-style diagonal loading) methods, applied automatically when a raw sample covariance isn't positive semidefinite. `pypfopt/risk_models.py:57-113`.
- **Multiple shrinkage estimators for covariance** — Ledoit-Wolf single-factor, constant-correlation, and constant-variance shrinkage, plus Oracle Approximating Shrinkage (`CovarianceShrinkage` class, `risk_models.py:412-657`) — all much less noisy than sample covariance/correlation for a matrix built from limited history, which is directly relevant to correlation-cap risk checks.
- **Semicovariance** (downside-only covariance, only counts co-movement below a benchmark) — `risk_models.py:206-256`.
- **Hierarchical Risk Parity (HRP)** — `HRPOpt` in `pypfopt/hierarchical_portfolio.py`, using `scipy.cluster.hierarchy` to build a dendrogram from the correlation matrix and allocate weights via recursive bisection down the cluster tree, explicitly "code reproduced with permission from Marcos López de Prado (2016)" — avoids inverting the covariance matrix entirely, more robust than mean-variance under estimation error.
- **Black-Litterman model** — `BlackLittermanModel` combines a market-implied prior (`market_implied_prior_returns`, `market_implied_risk_aversion`) with investor views, supporting the Idzorek method to convert view-confidence percentages into the `Omega` uncertainty matrix. `pypfopt/black_litterman.py:19-380`.
- **Convex transaction-cost and tracking-error penalty terms** usable as additive objectives in the optimizer — `transaction_cost(w, w_prev, k)` (linear cost vs. previous weights) and `ex_ante_tracking_error`/`ex_post_tracking_error` vs. a benchmark. `pypfopt/objective_functions.py:198-269`.
- **Discrete allocation** — converts continuous target weights into actual integer share counts via either a greedy iterative algorithm (`greedy_portfolio`, buys the asset with largest weight deficit each iteration, tracks leftover cash) or a mixed-integer LP solve (`lp_portfolio`), including explicit long/short sub-portfolio splitting logic. `pypfopt/discrete_allocation.py:158-341`.

## Why It's Trusted / Mature

PyPortfolioOpt is trusted because each piece — risk model, expected-returns estimator, optimizer objective, discrete allocation — is a swappable, independently testable module with a consistent `BaseOptimizer`/`BaseConvexOptimizer` interface, and because it implements well-known, citation-backed academic techniques (Ledoit-Wolf, HRP/López de Prado, Black-Litterman, Idzorek) rather than ad hoc heuristics. A serious user can point to the exact paper behind each numeric choice, which matters a great deal for anything touching risk allocation, where "why does the optimizer do this" needs a defensible answer, not just "that's what the code happened to compute."

## vs Vinu — Gap & Adoptable Logic

**Gap:** `vinu-portfolio` computes a "correlation matrix" and "target weights/rebalancing," but there's no indication it uses shrinkage estimators (Ledoit-Wolf) or a PSD-repair step — a raw sample correlation matrix from limited history is noisy and can be non-positive-semidefinite, which matters directly for Vina's correlation/concentration risk caps and the runtime correlation monitor in `vinu-live` (a noisy correlation matrix means false-positive/false-negative "reduce_only trim" triggers, which is exactly the class of bug already found and fixed once this session in the same monitor). Vina also has no discrete-share-allocation algorithm documented — turning target weights into whole-share orders with leftover-cash tracking is exactly what `vinu-portfolio` → `vinu-agent`'s order sizing needs, and PyPortfolioOpt has two concrete, tested implementations of it.

**Adopt:**
- `fix_nonpositive_semidefinite` (spectral method) — a directly portable, few-line function to harden `vinu-portfolio`'s correlation-matrix computation before it feeds correlation-cap checks or the runtime correlation monitor.
- Ledoit-Wolf shrinkage covariance — a concrete, well-tested estimator to replace/augment a raw sample correlation matrix in `vinu-portfolio`, reducing noise-driven false triggers in correlation/concentration risk checks and `vinu-live`'s runtime correlation monitor.
- The greedy discrete allocation algorithm — a specific, small, dependency-light algorithm (no LP solver needed) for converting `vinu-portfolio`'s target weights into integer share orders with deterministic leftover-cash handling; directly reusable for `vinu-agent`'s order-sizing step, including its long/short-splitting logic if Vina ever needs it.
- The transaction-cost-aware objective term (a simple `k * sum(|w - w_prev|)` penalty) — worth adding to `vinu-portfolio`'s rebalancing objective so it naturally trades off turnover against target-weight tracking, rather than rebalancing to exact target weights and separately worrying about execution cost after the fact.
- HRP — worth evaluating as an alternative/backstop to `vinu-portfolio`'s mean-variance-style target-weight computation when the correlation matrix is ill-conditioned (small universe/short history), since HRP sidesteps covariance-matrix inversion entirely.

## Where Vinu Excels

- **A live execution path the optimizer's output actually feeds.** PyPortfolioOpt is a pure math library — it computes weights and stops there. Vina's `vinu-portfolio` → `vinu-agent` connects target weights to real order submission, with a full risk-guard stack (kill switch, reduce_only, mandate limits) PyPortfolioOpt has no concept of, since it never places an order.
- **Runtime-tunable operational limits.** PyPortfolioOpt's constraints are set per-optimization-call in code; Vina's mandate limits (capital utilization, position caps) are now live-editable on a running process via the runtime-settings admin API.
- **LLM-driven strategy generation upstream of the optimizer.** PyPortfolioOpt answers "given these expected returns and this covariance matrix, what are the optimal weights" — it has no opinion on where the expected-returns input comes from. Vina's research pipeline supplies that upstream signal through an LLM-assisted, human-gated process.
