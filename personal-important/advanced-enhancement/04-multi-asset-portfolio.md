# Enhancement 4: Multi-Asset Portfolio Support

## Current State Score: 3/10

The research loop processes **one symbol at a time**. The `vinu-simulator` already supports multi-ticker simulation, and `vinu-strategy` can build multi-asset portfolios via YAML definitions. But the core research agent — the thing that actually creates and refines strategies — is single-stock only. This means:

- No cross-asset correlation analysis in strategy design
- No portfolio-level drawdown constraints
- No sector/industry exposure limits
- No diversification benefits captured
- Real portfolios are multi-asset; single-stock strategies are toy systems

## Target State: 10/10

The research loop accepts a **universe of symbols**, generates strategies that consider cross-asset relationships, enforces portfolio-level risk constraints, and reports portfolio-level metrics alongside per-symbol breakdowns.

## Why This Matters (The Problem)

- **Real trading is multi-asset**: No serious fund trades one stock. The system must handle universes of 10-500 symbols.
- **Diversification is the only free lunch**: A 100% AAPL portfolio has worse risk-adjusted returns than a 20% AAPL + 20% MSFT + 20% GOOG + 20% AMZN + 20% META portfolio.
- **Correlation matters**: Adding a position when it's highly correlated to existing positions adds risk without diversification.
- **Portfolio-level drawdown**: The system checks MaxDD per strategy, but real portfolios have constraints like "portfolio MaxDD cannot exceed 15%".
- **Sector limits**: A quant wouldn't put 50% in tech. The system has no sector awareness.
- **Capital allocation**: Given 10 good strategies, which ones get capital? The system has no mechanism to rank and allocate.

## What to Build

### 1. Universe Selection — New `vinu_research/universe.py`

```python
@dataclass
class UniverseConfig:
    symbols: list[str] = field(default_factory=list)
    max_symbols: int = 20
    selection_method: str = "explicit"  # "explicit", "top_market_cap", "sector_balanced"
    sector_weights: dict[str, float] | None = None  # e.g. {"TECH": 0.3, "FINANCE": 0.2}

class UniverseSelector:
    def select(self, config: UniverseConfig) -> list[str]:
        if config.selection_method == "explicit":
            return config.symbols
        elif config.selection_method == "top_market_cap":
            # Fetch top N by market cap from vinu-stock-price
            pass
        elif config.selection_method == "sector_balanced":
            # Fetch sector ETFs or stocks, select N per sector
            pass
```

### 2. Cross-Asset Correlation Module — Modify `vinu-research/tools.py`

```python
class ResearchTools:
    async def get_correlation_matrix(self, symbols: list[str],
                                     from_date: str, to_date: str) -> pd.DataFrame:
        """Fetch returns and compute pairwise correlation matrix"""
        prices = await asyncio.gather(
            *[self._get_prices(s, from_date, to_date) for s in symbols]
        )
        returns = pd.DataFrame({s: p['close'].pct_change() for s, p in zip(symbols, prices)})
        return returns.corr()

    async def get_sector_exposures(self, symbols: list[str]) -> dict[str, str]:
        """Fetch sector classification for each symbol"""
        ...
```

### 3. Research Loop Enhancement — Modify `loop.py`

```python
async def run_multi(
    self,
    user_idea: str,
    symbols: list[str],
    from_date: str,
    to_date: str,
) -> ResearchResult:

    # Step 1: Compute cross-asset correlation
    corr_matrix = await self._tools.get_correlation_matrix(symbols, from_date, to_date)

    # Step 2: Generate portfolio-level strategy
    strategy_code = await self._generate_portfolio_strategy(
        user_idea, symbols, corr_matrix
    )

    # Step 3: Multi-symbol backtest
    result = await self._tools.run_backtest(
        strategy_code=strategy_code,
        symbols=symbols,  # ← multiple symbols
        ...
    )

    # Step 4: Portfolio-level risk critic
    portfolio_metrics = result.portfolio_metrics
    per_symbol_metrics = result.per_symbol_metrics

    critic_feedback = await self._risk_critic(
        result=result,
        portfolio_metrics=portfolio_metrics,
        per_symbol_metrics=per_symbol_metrics,
        correlation_matrix=corr_matrix,
        iteration=iteration,
    )

    # Step 5: Refine with portfolio-aware filters
    ...
```

### 4. Portfolio-Level Risk Critic Rules

Add to `_rule_based_check()`:

```python
# Rule 9: Portfolio concentration
max_weight = max(portfolio_metrics.current_weights)
if max_weight > 0.40:
    suggestions.append(
        f"Portfolio too concentrated: {max_weight:.0%} in single asset. "
        f"Add max_position_weight constraint or sector limit"
    )

# Rule 10: Correlation concentration
if corr_matrix is not None:
    avg_corr = corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)].mean()
    if avg_corr > 0.6:
        suggestions.append(
            f"Average pairwise correlation {avg_corr:.2f} is high — "
            f"portfolio lacks diversification. Consider adding uncorrelated assets"
        )

# Rule 11: Sector concentration if sector data available
if sector_exposures:
    top_sector = max(sector_exposures, key=sector_exposures.get)
    if sector_exposures[top_sector] > 0.50:
        suggestions.append(
            f"Portfolio is {sector_exposures[top_sector]:.0%} in {top_sector}. "
            f"Consider sector-balancing"
        )
```

### 5. Portfolio-Level Strategy Code Generation

```python
def generate_portfolio_strategy(user_idea, symbols, corr_matrix):
    """
    Generate a strategy that considers:
    - Per-symbol signals (momentum, mean reversion, etc.)
    - Cross-asset hedging (if X goes up, reduce Y)
    - Portfolio-level risk parity (volatility-based allocation)
    - Sector constraints
    """
    signal_lines = []
    for sym in symbols:
        signal_lines.append(f"{sym}_signal = compute_momentum(data['{sym}'])")

    code = f"""
    signals = pd.DataFrame({{
        {', '.join(f"'{s}': compute_momentum(data['{s}'])" for s in symbols)}
    }})

    # Cross-asset hedging via correlation
    for col in signals.columns:
        correlated = signals.corrwith(signals[col]).abs() > 0.7
        signals[col] *= (1 - correlated.astype(float).mean() * 0.3)

    # Risk parity: scale by inverse volatility
    vols = {{s: data['{s}']['close'].pct_change().std() for s in symbols}}
    for s in symbols:
        if vols[s] > 0:
            signals[s] /= vols[s]

    # Apply max weight constraint
    signals = signals.clip(-{max_weight}, {max_weight})

    # Renormalize
    total_abs = signals.abs().sum(axis=1)
    signals = signals.div(total_abs, axis=0).fillna(0)
    """
    return code
```

### 6. CLI Integration

```python
@click.option("--universe", "-u", help="Comma-separated symbols, or path to universe file")
@click.option("--universe-method", default="explicit",
              type=click.Choice(["explicit", "sector_balanced", "top_market_cap"]))
@click.option("--max-symbols", default=20, type=int)
@click.option("--max-position-weight", default=0.25, type=float)
```

## Code Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `vinu_research/universe.py` | **NEW** | Universe selection and sector classification |
| `vinu_research/loop.py` | MODIFY | Add `run_multi()` for multi-asset research |
| `vinu_research/tools.py` | MODIFY | Add correlation_matrix, sector_exposures methods |
| `vinu_research/generator.py` | MODIFY | Add portfolio strategy code generator |
| `vinu_research/models.py` | MODIFY | Add PortfolioMetrics dataclass |
| `vinu_research/report.py` | MODIFY | Add portfolio breakdown section |
| `vinu_simulator/models/simulation.py` | MODIFY | Support multi-symbol portfolio metrics |
| `tests/test_portfolio.py` | **NEW** | Integration tests for multi-asset flow |

## Complexity & Verdict

- **Difficulty**: High (requires changes across multiple services, correlation logic is subtle)
- **Lines of code**: ~700-1000 total
- **Priority**: **HIGH** — single-stock is a toy; multi-asset is a real quant system
- **Dependencies**: vinu-stock-price (for prices), vinu-strategy (for portfolio engine)
- **Risk**: Medium-High — existing single-stock flow must remain unchanged; multi-asset is additive
- **Time estimate**: 8-12 days

## Implementation Order

1. Build multi-symbol backtest support in `vinu-simulator` (verify it works today)
2. Build universe selection module
3. Add correlation computation to ResearchTools
4. Build portfolio-level risk critic rules
5. Build portfolio strategy code generator
6. Wire up CLI
7. End-to-end test with 3-5 symbols
8. Validate: compare single-stock vs portfolio results
