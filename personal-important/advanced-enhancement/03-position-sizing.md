# Enhancement 3: Position Sizing & Allocation Upgrade

## Current State Score: 4/10

All generated strategies use a **fixed allocation** (`signal * 0.98`). The vinu-strategy engine has `max_weight` and `normalize` risk controls, but the research loop never optimizes position sizing. The result is:
- No Kelly-optimal bet sizing — leaving edge on the table
- No volatility targeting — portfolio risk varies wildly with market conditions
- No risk parity — all positions treated equally regardless of volatility
- No dynamic sizing — all positions get the same weight regardless of signal strength

## Target State: 10/10

A full position-sizing framework integrated into the research loop:
1. **Kelly Criterion**: Optimal bet size given win rate and payoff distribution
2. **Volatility Targeting**: Scale positions to target a specific portfolio volatility
3. **Risk Parity**: Allocate based on inverse volatility of each asset
4. **Signal-Adaptive Sizing**: Stronger signals get proportionally larger weights
5. Each sizing method is a configurable option in the strategy generator
6. Risk critic evaluates sizing efficiency (is the position size too small/large given the edge?)

## Why This Matters (The Problem)

- **Betting too small = leaving money on the table**: A strategy with 60% win rate and 2:1 reward:risk deserves bigger bets than one with 51% win rate.
- **Betting too big = blowing up**: Overbetting leads to ruin even with positive edge (the gambler's fallacy).
- **No volatility awareness**: A strategy trading AAPL (lower vol) gets the same position size as one trading TSLA (2x vol). The risk contribution is wildly different.
- **No signal strength scaling**: Current logic: signal > 0 → 0.98, signal ≤ 0 → 0. A strong +2 sigma signal should get higher weight than a weak +0.1 sigma signal.
- **No drawdown-dependent sizing**: When the strategy is down 15%, it should reduce position size. Currently it keeps betting the same amount.

## What to Build

### 1. Sizing Strategies — New Module `vinu_research/sizing.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
import numpy as np


@dataclass
class SizingConfig:
    method: str = "fixed"              # "fixed", "kelly", "vol_target", "risk_parity"
    max_allocation: float = 0.98       # Never exceed this
    min_allocation: float = 0.0        # Never go below this
    target_vol: float = 0.15           # Target annualized volatility (for vol_target)
    kelly_fraction: float = 0.25       # Fractional Kelly (0.25 = quarter Kelly)
    vol_lookback: int = 63             # Days for realized vol estimate
    max_conviction_mult: float = 3.0   # Max signal-strength multiplier


class SizingStrategy(ABC):
    @abstractmethod
    def compute_allocation(self, metrics: dict, daily_returns: pd.Series,
                           signal: pd.Series) -> float:
        ...


class KellySizing(SizingStrategy):
    def compute_allocation(self, metrics, daily_returns, signal):
        # Kelly formula: f* = (p * b - q) / b
        # where p = win rate, q = loss rate, b = average win / average loss
        win_rate = metrics.get("win_rate", 0.5)
        avg_win = metrics.get("avg_win_pct", 0.02)
        avg_loss = metrics.get("avg_loss_pct", -0.01)
        b = abs(avg_win / avg_loss) if avg_loss != 0 else 1

        kelly = (win_rate * b - (1 - win_rate)) / b
        kelly = np.clip(kelly, 0, self.config.max_allocation)
        return kelly * self.config.kelly_fraction


class VolTargetSizing(SizingStrategy):
    def compute_allocation(self, metrics, daily_returns, signal):
        realized_vol = daily_returns.std() * np.sqrt(252)
        if realized_vol <= 0:
            return self.config.max_allocation * 0.5
        # Scale: if vol is 20% but target is 15%, use 75% allocation
        vol_ratio = self.config.target_vol / realized_vol
        allocation = self.config.max_allocation * min(vol_ratio, 1.0)
        return np.clip(allocation, self.config.min_allocation,
                       self.config.max_allocation)


class SignalStrengthSizing(SizingStrategy):
    def compute_allocation(self, metrics, daily_returns, signal):
        # Scale based on signal z-score
        signal_mean = signal.mean()
        signal_std = signal.std()
        if signal_std <= 0:
            return self.config.max_allocation * 0.5
        z_scores = (signal - signal_mean) / signal_std
        # Average conviction for active positions
        active_signal = signal[signal.abs() > 0.01]
        if len(active_signal) == 0:
            return self.config.max_allocation * 0.5
        avg_z = active_signal.abs().mean()
        # Map z-score to allocation multiplier
        mult = min(avg_z / 1.0, self.config.max_conviction_mult)
        return np.clip(
            self.config.max_allocation * mult / self.config.max_conviction_mult,
            self.config.min_allocation,
            self.config.max_allocation,
        )
```

### 2. Integration with Strategy Generator — Modify `generator.py`

Current code generation:
```python
return signal * {allocation}
```

New code generation with sizing:
```python
# If sizing_method == "kelly":
allocation = self._compute_kelly_allocation(data)
return signal * allocation

# If sizing_method == "vol_target":
allocation = self._compute_vol_target(data)
return signal * allocation

# If sizing_method == "signal_strength":
return signal * self.max_allocation * (signal.abs() / signal.abs().max())
```

### 3. Strategy Template Expansion — Modify `generator.py`

Add sizing method selection based on user idea:
```python
def _detect_sizing_method(idea: str) -> str:
    idea_lower = idea.lower()
    if "kelly" in idea_lower:           return "kelly"
    if "vol target" in idea_lower:      return "vol_target"
    if "risk parity" in idea_lower:     return "risk_parity"
    if "signal strength" in idea_lower: return "signal_strength"
    return "fixed"  # default
```

### 4. Risk Critic Sizing Rules — Modify `loop.py`

Add to `_rule_based_check()`:

```python
# Assess sizing efficiency
if result.metrics.win_rate > 0.55 and result.metrics.avg_win_pct > 0.02:
    # High edge strategy should use Kelly or vol-target sizing
    if "signal * " in strategy_code and "* 0.98" in strategy_code:
        suggestions.append(
            "Strategy has strong edge (WR > 55%, avg win > 2%) but uses fixed allocation. "
            "Consider Kelly Criterion sizing to optimize bet size"
        )

# Check if sizing is too aggressive
if hasattr(result, 'max_position_risk') and result.max_position_risk > 0.05:
    suggestions.append(
        "Single position risk exceeds 5% of portfolio. "
        "Consider reducing max allocation or adding volatility targeting"
    )
```

### 5. CLI Integration

```python
@click.option("--sizing", default="fixed",
              type=click.Choice(["fixed", "kelly", "vol_target", "signal_strength"]))
@click.option("--target-vol", default=0.15, type=float)
@click.option("--kelly-fraction", default=0.25, type=float)
```

## Code Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `vinu_research/sizing.py` | **NEW** | Sizing strategies (Kelly, VolTarget, SignalStrength) |
| `vinu_research/generator.py` | MODIFY | Add sizing_method selection and code generation |
| `vinu_research/loop.py` | MODIFY | Add sizing-related risk critic rules |
| `vinu_research/config.py` | MODIFY | Add sizing config fields |
| `vinu_simulator/models/metrics.py` | MODIFY | Add avg_win_pct, avg_loss_pct, position_risk |
| `vinu_simulator/engine/metrics.py` | MODIFY | Compute avg_win_pct, avg_loss_pct |
| `tests/test_sizing.py` | **NEW** | Unit tests for all sizing strategies |

## Complexity & Verdict

- **Difficulty**: Low-Medium (Kelly formula is straightforward, integration is the main work)
- **Lines of code**: ~300-400 total
- **Priority**: **HIGH** — without proper sizing, good strategies underperform and risky strategies blow up
- **Dependencies**: None outside codebase
- **Risk**: Low — sizing is additive, existing fixed allocation remains default
- **Time estimate**: 2-4 days

## Implementation Order

1. Build sizing strategy classes (standalone, fully testable)
2. Add Kelly/vol metrics to backtest result computation
3. Integrate sizing into strategy generator templates
4. Add risk critic rules for sizing
5. Add CLI integration
6. Validate on known strategies (verify Kelly sizing increases Sharpe)
