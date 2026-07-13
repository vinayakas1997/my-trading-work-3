# Enhancement 7: Benchmark Comparison

## Current State Score: 3/10

The system reports absolute metrics (Sharpe, MaxDD, etc.) **without any benchmark comparison**. A Sharpe of 1.22 sounds good, but if the S&P 500 returned Sharpe 2.0 in the same period with buy-and-hold, the strategy is actually destroying value. There's no concept of alpha, tracking error, or market-relative performance.

## Target State: 10/10

Every backtest report automatically includes:
1. **Strategy vs Benchmark comparison table** (Sharpe, MaxDD, CAGR, WinRate)
2. **Alpha** (annualized excess return vs benchmark)
3. **Beta** (market exposure)
4. **Information Ratio** (alpha per unit of tracking error)
5. **Tracking Error** (standard deviation of excess returns)
6. **Up/Down Capture Ratio** (how the strategy performs in bull/bear markets)
7. **Relative Drawdown** (strategy drawdown vs benchmark drawdown)

## Why This Matters (The Problem)

- **Sharpe without context is meaningless**: A strategy Sharpe of 1.22 vs market Sharpe of 2.0 = the strategy is destroying alpha. A Sharpe of 0.8 vs market Sharpe of 0.2 = the strategy is creating alpha.
- **No way to know if the strategy is "good"**: The risk critic says "PASS" at Sharpe ≥ 1.5. But in a low-volatility year with strong market returns, a bond ETF could hit Sharpe 1.5. The system has no market-relative context.
- **Alpha is what matters**: The goal of active management is to generate alpha. Without benchmark comparison, the system doesn't know if it's achieving this.
- **Drawdown attribution**: Is a -10% drawdown a market-wide crash or a strategy-specific problem? A benchmark comparison tells you.

## What to Build

### 1. Benchmark Data Fetching — Modify `tools.py`

```python
class ResearchTools:
    def __init__(self, config):
        self.default_benchmark = config.benchmark_symbol or "SPY"

    async def get_benchmark_data(
        self,
        from_date: str,
        to_date: str,
        benchmark: str | None = None,
    ) -> pd.Series | None:
        """Fetch benchmark price data from stock-price service"""
        benchmark = benchmark or self.default_benchmark
        try:
            # Use existing vinu-stock-price API
            prices = await self._http_get(
                f"http://stock-price:8081/query/{benchmark}",
                params={"from": from_date, "to": to_date, "interval": "1d"},
            )
            return pd.Series(prices["close"], index=pd.to_datetime(prices["timestamp"]))
        except Exception:
            LOG.warning("Could not fetch benchmark data for %s", benchmark)
            return None
```

### 2. Benchmark Metrics Computation — New Function

```python
def compute_benchmark_metrics(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free_rate: float = 0.0,
) -> dict[str, float]:

    # Align on common dates
    combined = pd.concat([strategy_returns, benchmark_returns], axis=1).dropna()
    if len(combined) < 20:
        return {}

    strat = combined.iloc[:, 0]
    bench = combined.iloc[:, 1]

    result = {}

    # Alpha and Beta (CAPM)
    cov_matrix = np.cov(strat, bench)
    beta = cov_matrix[0, 1] / cov_matrix[1, 1] if cov_matrix[1, 1] > 0 else 0.0
    rf_daily = (1 + risk_free_rate) ** (1 / 252) - 1
    excess_strat = strat.mean() - rf_daily
    excess_bench = bench.mean() - rf_daily
    alpha_daily = excess_strat - beta * excess_bench
    result["alpha"] = alpha_daily * 252  # Annualize
    result["beta"] = beta

    # Tracking Error
    excess_returns = strat - bench
    tracking_error = excess_returns.std() * np.sqrt(252)
    result["tracking_error"] = tracking_error

    # Information Ratio
    result["information_ratio"] = (
        (excess_returns.mean() / excess_returns.std() * np.sqrt(252))
        if tracking_error > 0 else 0.0
    )

    # Up/Down Capture
    bench_up = bench > 0
    bench_down = bench <= 0
    up_capture = strat[bench_up].mean() / bench[bench_up].mean() if bench_up.any() and bench[bench_up].mean() != 0 else 0.0
    down_capture = strat[bench_down].mean() / bench[bench_down].mean() if bench_down.any() and bench[bench_down].mean() != 0 else 0.0
    result["up_capture"] = up_capture
    result["down_capture"] = down_capture

    # Correlation
    result["market_correlation"] = strat.corr(bench)

    # Relative drawdown
    strat_cum = (1 + strat).cumprod()
    bench_cum = (1 + bench).cumprod()
    relative_cum = strat_cum / bench_cum
    running_max = relative_cum.expanding().max()
    relative_dd = (relative_cum - running_max) / running_max
    result["relative_max_drawdown"] = relative_dd.min()

    return result
```

### 3. Report Integration — Modify `report.py`

```markdown
### Benchmark Comparison (vs {benchmark_symbol})
| Metric | Strategy | Benchmark | Difference |
|--------|----------|-----------|------------|
| CAGR | +12.4% | +8.2% | +4.2% |
| Sharpe | 1.22 | 0.89 | +0.33 |
| Max Drawdown | -7.5% | -12.3% | +4.8% |
| Volatility | 15.2% | 18.1% | -2.9% |
| Win Rate | 59% | 54% | +5% |

### Alpha & Beta
| Metric | Value | Interpretation |
|--------|-------|----------------|
| Alpha (annual) | +4.2% | Positive alpha vs SPY |
| Beta | 0.72 | Less volatile than market |
| Correlation | 0.65 | Moderate market exposure |
| Information Ratio | 0.84 | Good active returns per unit of risk |
| Tracking Error | 8.1% | Deviation from benchmark |
| Rel. Max DD | -4.2% | Strategy lost ground vs benchmark in peak drawdown |

### Market Capture
| Metric | Value |
|--------|-------|
| Up Capture | 85% (captures 85% of market upside) |
| Down Capture | 60% (only 60% of market downside) |
| Capture Ratio | 1.42 (good: captures more upside than downside) |
```

### 4. Risk Critic Benchmark Rules — Modify `loop.py`

```python
# Rule 17: Negative alpha
if benchmark_metrics and benchmark_metrics.get("alpha", 0) < 0:
    suggestions.append(
        f"Strategy alpha is {benchmark_metrics['alpha']:.1%} — "
        f"the strategy is destroying value vs benchmark. Consider simpler approach"
    )

# Rule 18: Low information ratio
if benchmark_metrics and benchmark_metrics.get("information_ratio", 0) < 0.5:
    suggestions.append(
        f"Information ratio {benchmark_metrics['information_ratio']:.2f} < 0.5 — "
        f"active returns don't justify tracking error"
    )

# Rule 19: High down capture
if benchmark_metrics and benchmark_metrics.get("down_capture", 1) > 1.2:
    suggestions.append(
        f"Down capture {benchmark_metrics['down_capture']:.0%} > 100% — "
        f"strategy falls MORE than market in downturns. Add tail protection"
    )

# Rule 20: Strategy not beating benchmark on CAGR
if benchmark_metrics and benchmark_metrics.get("excess_cagr", 0) < 0:
    suggestions.append(
        f"Strategy CAGR below benchmark CAGR — "
        f"consider if active management is justified"
    )
```

### 5. CLI Integration

```python
@click.option("--benchmark", default="SPY", help="Benchmark symbol for comparison")
@click.option("--no-benchmark", is_flag=True, help="Skip benchmark comparison")
```

## Code Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `vinu_research/tools.py` | MODIFY | Add get_benchmark_data() method |
| `vinu_research/report.py` | MODIFY | Add benchmark comparison section |
| `vinu_research/models.py` | MODIFY | Add BenchmarkMetrics dataclass |
| `vinu_research/loop.py` | MODIFY | Add benchmark data fetching to loop, 4 new risk critic rules |
| `vinu_research/config.py` | MODIFY | Add benchmark_symbol config |
| `tests/test_benchmark.py` | **NEW** | Tests for benchmark metrics computation |

## Complexity & Verdict

- **Difficulty**: Low (straightforward math, no architectural changes)
- **Lines of code**: ~250-350 total
- **Priority**: **MEDIUM** — important but not as critical as walk-forward or generator upgrade
- **Dependencies**: vinu-stock-price (for benchmark data) or Yahoo Finance fallback
- **Risk**: Very Low — additive, benchmark failure (None) doesn't affect existing flow
- **Time estimate**: 1-2 days

## Implementation Order

1. Add benchmark data fetching to ResearchTools
2. Build benchmark metrics computation
3. Integrate into research loop (fetches benchmark in parallel with strategy backtest)
4. Update report format
5. Add risk critic rules
6. Write tests

## Edge Cases to Handle

- **Benchmark data not available**: Gracefully skip benchmark comparison, show "N/A"
- **Different date ranges**: Align strategy and benchmark dates before comparison
- **Non-US markets**: Allow configurable benchmark symbol per market (SPY for US, IEV for Europe, EEM for EM)
- **No benchmark**: If `--no-benchmark`, skip all benchmark-related computation
