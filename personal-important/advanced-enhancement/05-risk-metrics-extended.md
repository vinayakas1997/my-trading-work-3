# Enhancement 5: Extended Risk Metrics

## Current State Score: 6/10

The `compute_performance_metrics()` function in `vinu-simulator/engine/metrics.py` computes 10 metrics: total_return, CAGR, annual_volatility, sharpe_ratio, sortino_ratio, max_drawdown, calmar_ratio, win_rate, skewness, kurtosis. These cover the basics but miss several critical metrics that professional quants use to evaluate strategies.

## Target State: 10/10

A comprehensive metrics suite with 20+ metrics covering:
1. **Risk-adjusted returns**: Information Ratio, Treynor Ratio, Jensen's Alpha
2. **Tail risk**: VaR (95%, 99%), CVaR, Tail Ratio
3. **Drawdown characteristics**: Max DD Duration, Average DD, DD Recovery Time
4. **Trading behavior**: Turnover Rate, Hit Rate, Profit Factor, Avg Win/Loss
5. **Market-relative**: Beta, Correlation to Benchmark, Tracking Error
6. **Statistical significance**: p-value of Sharpe > 0, Bootstrap confidence intervals

## Why This Matters (The Problem)

- **Sharpe alone is misleading**: A Sharpe 1.5 strategy with -40% MaxDD is worse than Sharpe 0.8 with -8% MaxDD. The current system checks both, but doesn't weight them.
- **No tail risk awareness**: A strategy that blows up 5% of the time looks fine in Sharpe but has unacceptable tail risk. VaR and CVaR catch this.
- **No recovery time**: A strategy with 20% drawdown that takes 2 years to recover is very different from one that recovers in 2 weeks. Both show the same MaxDD.
- **No turnover awareness**: A daily-trading strategy with 500% annual turnover incurs massive costs that the slippage model may underestimate. Turnover is the Canary in the coal mine.
- **No statistical confidence**: The Sharpe of 1.22 on 252 data points might be statistically insignificant. A p-value or confidence interval tells you if you should trust it.
- **No benchmark context**: The metrics don't say whether the strategy is better than just buying SPY.

## What to Build

### 1. Extended Metrics Function — Modify `metrics.py`

```python
def compute_extended_metrics(
    portfolio_values: pd.Series,
    daily_returns: pd.Series,
    benchmark_returns: pd.Series | None = None,
    risk_free_rate: float = 0.0,
) -> dict[str, float]:

    basic = compute_performance_metrics(portfolio_values, daily_returns, risk_free_rate)

    extended = {}

    # === TAIL RISK ===
    sorted_rets = daily_returns.sort_values()
    var_95 = sorted_rets.quantile(0.05)  # Value at Risk 95%
    var_99 = sorted_rets.quantile(0.01)  # Value at Risk 99%
    cvar_95 = sorted_rets[sorted_rets <= var_95].mean()  # Conditional VaR
    tail_ratio = sorted_rets.quantile(0.95) / abs(sorted_rets.quantile(0.05))

    extended["var_95"] = var_95
    extended["var_99"] = var_99
    extended["cvar_95"] = cvar_95
    extended["tail_ratio"] = tail_ratio

    # === DRAWDOWN CHARACTERISTICS ===
    cumulative = portfolio_values / portfolio_values.iloc[0]
    running_max = cumulative.expanding().max()
    drawdown_series = (cumulative - running_max) / running_max

    # Max DD duration (longest time to recover)
    in_drawdown = drawdown_series < 0
    dd_streaks = (in_drawdown != in_drawdown.shift()).cumsum()
    dd_durations = in_drawdown.groupby(dd_streaks).sum()
    max_dd_duration = dd_durations.max() if len(dd_durations) > 0 else 0

    # Average drawdown
    avg_dd = drawdown_series[drawdown_series < 0].mean()
    # Recovery time (trading days to recover from max DD)
    max_dd_idx = drawdown_series.idxmin()
    recovery_idx = drawdown_series[max_dd_idx:].idxmax() if max_dd_idx is not None else None
    recovery_days = (recovery_idx - max_dd_idx).days if recovery_idx is not None else len(daily_returns)

    extended["max_dd_duration_days"] = max_dd_duration
    extended["avg_drawdown"] = avg_dd
    extended["recovery_time_days"] = recovery_days

    # === TRADING BEHAVIOR ===
    wins = daily_returns[daily_returns > 0]
    losses = daily_returns[daily_returns < 0]

    profit_factor = wins.sum() / abs(losses.sum()) if abs(losses.sum()) > 0 else float('inf')
    avg_win_pct = wins.mean() if len(wins) > 0 else 0.0
    avg_loss_pct = losses.mean() if len(losses) > 0 else 0.0
    win_loss_ratio = abs(avg_win_pct / avg_loss_pct) if avg_loss_pct != 0 else float('inf')
    hit_rate = len(wins) / len(daily_returns) if len(daily_returns) > 0 else 0.0

    extended["profit_factor"] = profit_factor
    extended["avg_win_pct"] = avg_win_pct
    extended["avg_loss_pct"] = avg_loss_pct
    extended["win_loss_ratio"] = win_loss_ratio
    extended["hit_rate"] = hit_rate  # rename of win_rate, kept for compatibility

    # === MARKET-RELATIVE (if benchmark provided) ===
    if benchmark_returns is not None:
        aligned = pd.concat([daily_returns, benchmark_returns], axis=1).dropna()
        strat_rets = aligned.iloc[:, 0]
        bench_rets = aligned.iloc[:, 1]

        beta = strat_rets.cov(bench_rets) / bench_rets.var() if bench_rets.var() > 0 else 0.0
        alpha = (strat_rets.mean() - beta * bench_rets.mean()) * 252  # Annualized Jensen's Alpha
        tracking_error = (strat_rets - bench_rets).std() * np.sqrt(252)
        info_ratio = (strat_rets.mean() - bench_rets.mean()) / (strat_rets - bench_rets).std() * np.sqrt(252) if tracking_error > 0 else 0.0
        correlation = strat_rets.corr(bench_rets)

        extended["beta"] = beta
        extended["alpha"] = alpha
        extended["tracking_error"] = tracking_error
        extended["information_ratio"] = info_ratio
        extended["market_correlation"] = correlation

    # === STATISTICAL SIGNIFICANCE ===
    n = len(daily_returns)
    sharpe_se = np.sqrt((1 + 0.5 * basic["sharpe_ratio"]**2) / n) if n > 1 else 1.0
    sharpe_p_value = 2 * (1 - stats.norm.cdf(abs(basic["sharpe_ratio"] / sharpe_se)))
    sharpe_ci_low = basic["sharpe_ratio"] - 1.96 * sharpe_se
    sharpe_ci_high = basic["sharpe_ratio"] + 1.96 * sharpe_se

    extended["sharpe_standard_error"] = sharpe_se
    extended["sharpe_p_value"] = sharpe_p_value
    extended["sharpe_ci_95_low"] = sharpe_ci_low
    extended["sharpe_ci_95_high"] = sharpe_ci_high

    # === TURNOVER ===
    # (Requires trade data from SimulationResult)
    # Computed separately: total_traded_value / avg_portfolio_value

    extended.update(basic)
    return extended
```

### 2. Turnover Computation — Modify `simulator.py`

Add to `WeightSimulator.run()`:
```python
# After simulation loop:
total_traded_value = sum(t.shares * t.price for t in trades)
avg_portfolio_value = np.mean(equity_curve)
annual_turnover = (total_traded_value / avg_portfolio_value) * (252 / len(daily_ret)) if len(daily_ret) > 0 else 0.0

metrics_with_turnover = {**metrics, "annual_turnover": annual_turnover}
```

### 3. Risk Critic Extended Rules — Modify `loop.py`

Add these rules:

```python
# Rule 12: Tail risk
if extended_metrics.get("cvar_95", -0.02) < -0.03:
    suggestions.append(
        f"CVaR 95% is {extended_metrics['cvar_95']:.1%} — "
        f"extreme tail risk. Consider stop-loss or position limits"
    )

# Rule 13: Recovery time
if extended_metrics.get("recovery_time_days", 0) > 120:
    suggestions.append(
        f"Recovery from max drawdown took {extended_metrics['recovery_time_days']} days. "
        f"Consider adding drawdown-recovery filters"
    )

# Rule 14: Turnover too high
if extended_metrics.get("annual_turnover", 0) > 2000:
    suggestions.append(
        f"Annual turnover {extended_metrics['annual_turnover']:.0f}% — "
        f"costs will erode edge. Add holding period filter"
    )

# Rule 15: Sharpe not statistically significant
if extended_metrics.get("sharpe_p_value", 1.0) > 0.05:
    suggestions.append(
        f"Sharpe {extended_metrics['sharpe_ratio']:.2f} is not statistically significant "
        f"(p={extended_metrics['sharpe_p_value']:.3f}). Need more data"
    )

# Rule 16: Negative profit factor
if extended_metrics.get("profit_factor", 1.0) < 1.0:
    suggestions.append(
        f"Profit factor {extended_metrics['profit_factor']:.2f} < 1 — "
        f"strategy loses more on losers than it gains on winners"
    )
```

### 4. Report Enhancement — Modify `report.py`

Add sections for extended metrics:

```markdown
### Risk Metrics
| Metric | Value |
|--------|-------|
| VaR (95%) | -2.1% |
| CVaR (95%) | -3.4% |
| Tail Ratio | 1.8 |
| Profit Factor | 2.1 |
| Avg Win / Avg Loss | 1.5x |
| Max DD Duration | 45 days |
| Recovery Time | 12 days |

### Market-Relative (vs SPY)
| Metric | Strategy | Benchmark |
|--------|----------|-----------|
| Sharpe | 1.22 | 0.89 |
| Max DD | -7.5% | -12.3% |
| Beta | 0.72 | — |
| Alpha (annual) | +4.2% | — |
| Information Ratio | 0.84 | — |

### Statistical Significance
Sharpe 95% Confidence Interval: [0.82, 1.62]
p-value (Sharpe > 0): 0.003 — strong evidence
```

## Code Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `vinu_simulator/engine/metrics.py` | MODIFY | Add VaR, CVaR, tail ratio, drawdown duration, recovery, profit factor, turnover |
| `vinu_simulator/engine/simulator.py` | MODIFY | Add turnover computation to simulation result |
| `vinu_simulator/models/metrics.py` | MODIFY | Add extended metric fields |
| `vinu_research/loop.py` | MODIFY | Add 6 new risk critic rules for extended metrics |
| `vinu_research/report.py` | MODIFY | Add extended metrics tables |
| `vinu_research/tools.py` | MODIFY | Add benchmark data fetching |
| `tests/test_metrics_extended.py` | **NEW** | Unit tests for new metrics |

## Complexity & Verdict

- **Difficulty**: Low (most formulas are well-known, no architectural changes needed)
- **Lines of code**: ~300-400 total
- **Priority**: **MEDIUM** — important for thorough evaluation, but not blocking other improvements
- **Dependencies**: `scipy.stats` for p-value computation (already in dependencies via vinu-correlation)
- **Risk**: Very Low — additive, doesn't change existing behavior
- **Time estimate**: 1-2 days

## Implementation Order

1. Add all non-benchmark metrics to `metrics.py` (tail risk, drawdown, behavior)
2. Add turnover computation to simulator
3. Add benchmark-dependent metrics (requires benchmark data — see #07)
4. Update MetricBundle model
5. Add risk critic rules
6. Update report format
7. Write tests

## Key Implementation Details

- **Turnover** = `total_value_traded / avg_aum` expressed as annualized percentage
- **CVaR** = average of all returns below VaR threshold
- **Recovery Time** = trading days between max drawdown trough and subsequent peak
- **Information Ratio** = excess return over benchmark / tracking error
- **Profit Factor** = gross profit / gross loss (ratio > 2 is good)
- **Sharpe p-value**: tests the null hypothesis that true Sharpe = 0. Low p-value (< 0.05) means we can reject the null.
