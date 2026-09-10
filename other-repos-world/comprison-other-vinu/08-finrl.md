# FinRL

https://github.com/AI4Finance-Foundation/FinRL · 16.2K stars · First released 2020-07-26 · Last updated 2026-07-13

## Advanced Features

- **Turbulence-index kill switch** — a Mahalanobis-distance-style market stress indicator computed from a rolling 252-day covariance of returns; positions are forcibly liquidated when it exceeds a threshold. `calculate_turbulence` (`finrl/meta/preprocessor/preprocessors.py:282-334`); consumed in the trading envs at `finrl/meta/env_stock_trading/env_stocktrading_stoploss.py:332-336` and live in `env_stock_papertrading.py:304-330` (`turbulence_bool`, with a `sigmoid_sign` compression of the turbulence signal into observation space for the RL agent).
- **Reward-shaped stop-loss / cash-reserve / profit-taking environment** — `StockTradingEnvStopLoss` computes reward as `total_assets - (cash_penalty + stop_loss_penalty + low_profit_penalty) + additional_reward`: it penalizes running low on cash, penalizes not cutting losers below `stoploss_penalty * avg_buy_price`, and penalizes selling winners below a `profit_loss_ratio`-derived threshold. An incremental average-cost-basis tracker per asset (`avg_buy_price`, `n_buys`) is maintained purely in vectorized numpy. `env_stocktrading_stoploss.py:260-433`.
- **Ensemble-of-RL-agents strategy selection** — trains A2C/PPO/DDPG/SAC/TD3 on a rolling window, validates each on a holdout window, and picks the model with the best validation Sharpe ratio to trade the next window. `get_validation_sharpe` + `run_ensemble_strategy` in `finrl/agents/stablebaselines3/models.py:220-710` (class `DRLEnsembleAgent`).
- **Live paper-trading loop against Alpaca** — with market-open/close awaiting threads, a `turbulence_bool` short-circuit that liquidates all positions via `alpaca.list_positions()`, and quantity clipping to available cash. `env_stock_papertrading.py:155-338`. Notably uses the same broker (Alpaca) as Vina.
- **Cash-penalty reward with a "patient" no-fill-on-shortfall mode** vs. a hard-terminate-episode mode — `env_stocktrading_cashpenalty.py:250-357` (`patient` flag).

## Why It's Trusted / Mature

FinRL's appeal is that it standardizes "define a gym-style trading Env + swap in any Stable-Baselines3/ElegantRL/RLlib RL algorithm," and it packages turbulence-based crash protection and ensemble model-selection out of the box, so a user gets a runnable RL pipeline without hand-rolling reward shaping from scratch. It's worth being clear-eyed, though: it's trusted for research/teaching value, not production engineering rigor — the codebase has real rough edges (matplotlib backend hacks, bare `except:` clauses, global state, episode-based backtesting rather than event-driven simulation). It's a good source of well-known techniques implemented cleanly, not a template for production infrastructure.

## vs Vinu — Gap & Adoptable Logic

**Gap:** Vina has no RL-agent component at all (it's LLM-agent + rule-based instead, a deliberate design choice, not a gap in the negative sense) — so most of FinRL's RL-specific machinery (ensemble training, gym envs, SB3 integration) isn't directly relevant. What is relevant: Vina has no analog of FinRL's turbulence index — a single scalar computed from a rolling covariance/Mahalanobis distance across a basket, used as a portfolio-wide "stop everything" signal. `vinu-live`'s OOD detector is conceptually similar but the turbulence-index formula (regime-shift detection via Mahalanobis distance over a return covariance window) is a concrete, cheap, well-known technique worth confirming Vina's OOD detector actually implements, rather than assuming equivalence.

**Adopt:**
- The turbulence index (`calculate_turbulence`) as a cheap regime/stress feature for `vinu-live`'s OOD/emergency-flatten detector, or for `vinu-screener` to suppress candidates during market-wide turbulence — a trivial port (pandas + `np.linalg.pinv`, no RL needed) that could gate the whole screener/halt-policy the same way it gates FinRL's env.
- The incremental average-buy-price tracker (`avg_buy_price`, `n_buys`, vectorized incremental mean update) — a useful pattern for any component in Vina needing a per-symbol running cost-basis without replaying full trade history.
- Model-selection-by-validation-Sharpe on rolling windows (`_train_window` + `get_validation_sharpe`) — a concrete rolling-window holdout-then-promote pattern conceptually parallel to `vinu-research`'s promotion gate, worth comparing against for how holdout-window size and rebalance-window interact.

## Where Vinu Excels

- **Production engineering discipline.** The audit itself notes FinRL's real rough edges — bare `except:` clauses, global state, matplotlib backend hacks. Vina's per-service architecture with isolated tests per concern, and the documented, verified bug fixes already made this session, reflect a materially higher engineering bar than a research/teaching codebase needs to clear.
- **A promotion gate independent of any one model's own self-assessment.** FinRL's ensemble picks whichever RL model scored best on its own validation Sharpe — there's no external, independent statistical gate (deflated Sharpe correcting for how many models were tried) the way `vinu-research` applies one uniformly to every candidate strategy, LLM-generated or otherwise.
- **No RL-specific fragility.** RL policies are famously prone to reward-hacking their own environment's implementation details; Vina's rule-based + LLM-research approach sidesteps that entire failure mode by construction, at the cost of not getting RL's adaptive optimization — a deliberate, defensible trade-off for real capital.
