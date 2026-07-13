# Enhancement 8: Slippage & Market Impact Modeling

## Current State Score: 7/10

The simulator supports two cost models — `FlatCostModel` (fixed percentage) and `AlmgrenChrissCostModel` (market impact). The Almgren-Chriss model is a respectable academic standard. However, the models are used with **fixed, non-tuned parameters** and don't account for several real-world factors:

- **Volume-based slippage**: Can't trade more than X% of daily volume without incurring extra impact
- **Time-of-day effects**: Slippage is higher at market open/close
- **Spread modeling**: Bid-ask spread varies by liquidity and market conditions
- **Order book simulation**: Market vs limit order decisions depend on urgency
- **Adaptive parameters**: Impact parameters should be calibrated per symbol based on historical data

## Target State: 10/10

A sophisticated cost/slippage model that:
1. Uses historical volume profiles to estimate real-world fill rates
2. Models spread costs based on market cap / liquidity tiers
3. Applies time-of-day adjustments (higher cost at open/close)
4. Auto-calibrates Almgren-Chriss parameters per symbol from historical data
5. Reports slippage as a separate metric line item (not buried in transaction costs)
6. The risk critic can detect when slippage is eroding strategy edge

## Why This Matters (The Problem)

- **Flat slippage underestimates costs for illiquid stocks**: A 0.05% slippage on TSLA is fine. The same 0.05% on a micro-cap stock is unrealistic — the real slippage is 10x higher.
- **Volume constraints make strategies infeasible**: A strategy that trades 50% of a stock's daily volume is impossible to execute. The current model doesn't check this.
- **No slippage breakdown**: Currently all costs are "transaction_cost". You can't see how much is commissions vs spread vs impact.
- **Parameter sensitivity**: Small changes in slippage assumptions can dramatically change backtest results. Without calibration, users can't trust the outputs.

## What to Build

### 1. Volume-Based Slippage Model — New `vinu_simulator/engine/costs_advanced.py`

```python
@dataclass
class AdvancedCostConfig:
    # Spread model
    spread_model: str = "liquidity_tier"     # "fixed", "liquidity_tier", "historical"
    spread_pct: float = 0.001                # Default 10bps spread

    # Market impact (Almgren-Chriss parameters)
    impact_permanent: float = 0.0001         # Permanent impact coefficient
    impact_temporary: float = 0.001          # Temporary impact coefficient
    impact_decay: float = 0.1                # Impact decay factor per rebalance

    # Volume constraints
    max_volume_pct: float = 0.05             # Max 5% of daily volume per trade
    volume_lookback_days: int = 20           # Days for avg volume computation

    # Time-of-day adjustments
    time_of_day_adjustment: bool = True      # Higher slippage at open/close
    open_adj_mult: float = 1.5               # 50% higher at market open
    close_adj_mult: float = 1.3              # 30% higher at market close

    # Liquidity tiers (market cap based)
    liquidity_tiers = {
        "large": {"spread_pct": 0.0005, "impact_temp": 0.0005},    # AAPL, MSFT
        "mid":   {"spread_pct": 0.0010, "impact_temp": 0.0010},    # Mid-cap
        "small": {"spread_pct": 0.0020, "impact_temp": 0.0025},    # Small-cap
        "micro": {"spread_pct": 0.0050, "impact_temp": 0.0050},    # Micro-cap
    }

class AdvancedCostModel:
    def __init__(self, config: AdvancedCostConfig):
        self.config = config

    def compute_slippage(
        self,
        symbol: str,
        side: str,
        shares: float,
        price: float,
        volume: float | None,
        timestamp: pd.Timestamp | None = None,
        liquidity_tier: str | None = None,
    ) -> float:
        """
        Returns total slippage cost as a decimal (e.g., 0.0015 = 0.15%)
        Components:
        1. Spread cost (half-spread assumption)
        2. Market impact (Almgren-Chriss)
        3. Volume constraint penalty
        4. Time-of-day adjustment
        """
        # 1. Spread cost
        tier = liquidity_tier or "large"
        tier_config = self.config.liquidity_tiers.get(tier, self.config.liquidity_tiers["mid"])
        spread = tier_config["spread_pct"] / 2  # Half-spread for one trade

        # 2. Market impact
        participation_rate = (shares * price) / max(volume * price, 1) if volume else 0.01
        impact_temp = tier_config["impact_temp"] * (participation_rate ** 0.5)
        impact_perm = self.config.impact_permanent * participation_rate

        # 3. Volume constraint penalty
        volume_penalty = 0.0
        if volume and (shares / volume) > self.config.max_volume_pct:
            excess = (shares / volume) / self.config.max_volume_pct
            volume_penalty = 0.001 * ((excess - 1) ** 2)

        # 4. Time-of-day adjustment
        tod_mult = 1.0
        if self.config.time_of_day_adjustment and timestamp is not None:
            hour = timestamp.hour
            minute = timestamp.minute
            # Market open (9:30-10:00 ET)
            if hour == 9 or (hour == 10 and minute < 30):
                tod_mult = self.config.open_adj_mult
            # Market close (15:30-16:00 ET)
            elif hour == 15 and minute >= 30:
                tod_mult = self.config.close_adj_mult

        total = (spread + impact_temp + impact_perm + volume_penalty) * tod_mult
        return total
```

### 2. Auto-Calibration Module — New File

```python
class CostModelCalibrator:
    """
    Calibrates cost model parameters per symbol using historical data.

    Data sources:
    - vinu-stock-price: OHLCV with spread data
    - Market cap from vinu-news or config

    Calibration:
    - Spread = average (ask - bid) / mid
    - Impact coefficient from linear regression of returns on signed volume
    - Liquidity tier from market cap or average volume decile
    """

    async def calibrate(self, symbol: str) -> dict:
        ...
```

### 3. Slippage Reporting — Modify `simulator.py`

Add slippage breakdown to `SimulationResult`:

```python
@dataclass
class SlippageReport:
    total_costs: float           # Total cost (dollars)
    spread_cost: float           # Cost from bid-ask spread
    impact_cost: float           # Cost from market impact
    volume_penalty: float        # Cost from exceeding volume limits
    missed_trades: int           # Number of trades skipped due to volume constraints
    avg_slippage_bps: float      # Average slippage in basis points
```

### 4. Risk Critic Slippage Rules — Modify `loop.py`

```python
# Rule 21: Slippage exceeds threshold
avg_slippage = result.slippage_report.avg_slippage_bps
if avg_slippage > 20:  # 20 bps average slippage
    suggestions.append(
        f"Average slippage {avg_slippage:.0f} bps is high. "
        f"Consider reducing trade frequency or focusing on liquid symbols"
    )

# Rule 22: Volume constraint violations
if result.slippage_report.missed_trades > 0:
    pct_missed = result.slippage_report.missed_trades / len(result.trades)
    if pct_missed > 0.1:
        suggestions.append(
            f"{result.slippage_report.missed_trades} trades blocked by volume constraints "
            f"({pct_missed:.0%} of all trades) — strategy may be infeasible at scale"
        )

# Rule 23: Impact cost > spread cost
if result.slippage_report.impact_cost > result.slippage_report.spread_cost:
    suggestions.append(
        "Market impact dominates trading costs — "
        "consider reducing position sizes to minimize footprint"
    )
```

### 5. Integration with vinu-strategy — Modify `vinu_strategy/engine/pipeline.py`

```python
class WeightPipeline:
    def __init__(self, cost_model: AdvancedCostModel | None = None):
        self._cost_model = cost_model or FlatCostModel()

    def compute_execution_cost(self, current_weights, target_weights, prices, volumes):
        """Pre-trade cost estimate for rebalance decisions"""
        cost_estimate = 0.0
        for symbol, target in target_weights.items():
            deviation = abs(target - current_weights.get(symbol, 0))
            if deviation > 0:
                notional = deviation * self._portfolio_value
                cost_estimate += self._cost_model.compute_slippage(
                    symbol, "SELL" if target < 0 else "BUY",
                    notional / prices[symbol],
                    prices[symbol],
                    volumes.get(symbol),
                )
        return cost_estimate
```

## Code Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `vinu_simulator/engine/costs_advanced.py` | **NEW** | Volume-based, time-of-day-aware cost model |
| `vinu_simulator/engine/costs.py` | MODIFY | Add cost model calibrator |
| `vinu_simulator/models/simulation.py` | MODIFY | Add SlippageReport dataclass |
| `vinu_simulator/engine/simulator.py` | MODIFY | Integrate advanced cost model, report slippage breakdown |
| `vinu_research/loop.py` | MODIFY | Add slippage-related risk critic rules |
| `vinu_strategy/engine/pipeline.py` | MODIFY | Integrate cost-aware rebalancing |
| `tests/test_costs_advanced.py` | **NEW** | Tests for advanced cost models |

## Complexity & Verdict

- **Difficulty**: Medium (advanced cost modeling requires care, but math is well-understood)
- **Lines of code**: ~400-600 total
- **Priority**: **MEDIUM** — important for realistic simulation, but current flat model is acceptable for initial research
- **Dependencies**: None outside codebase
- **Risk**: Low — advanced model is optional; existing FlatCostModel + AlmgrenChriss remain default
- **Time estimate**: 3-5 days

## Implementation Order

1. Build AdvancedCostModel with volume, spread, time-of-day components
2. Integrate into WeightSimulator (advanced mode)
3. Build slippage reporting
4. Add volume constraint enforcement (reject trades exceeding X% of volume)
5. Add risk critic rules
6. Write calibration script for symbol-specific parameters
7. Validate: compare flat costs vs advanced costs for liquid vs illiquid stocks
