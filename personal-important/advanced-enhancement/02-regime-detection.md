# Enhancement 2: Market Regime Detection

## Current State Score: 3/10

The system has **zero awareness of market regimes**. The risk critic checks `ADX < 20` as a single hardcoded threshold, but this is a poor proxy for regime classification. A strategy is generated once and refined without context of whether it's being used in a trending, mean-reverting, or high-volatility market. If a crossover strategy is tested on a trending period and shows Sharpe 1.5, the system declares PASS — then the strategy gets deployed into a choppy market and loses money.

## Target State: 10/10

A regime detection module that:
1. Classifies each market session into one of 4 regimes (trending, mean-reverting, high-volatility, quiet)
2. Tags every backtest period and every trade with the active regime
3. The risk critic reports: "Strategy performed well in trending regimes (Sharpe 1.8) but failed in mean-reverting regimes (Sharpe -0.3)"
4. The generator selects template based on detected regime
5. Strategies include regime-contingent rules: "only trade when regime == trending"

## Why This Matters (The Problem)

- **Strategy-regime mismatch**: A momentum strategy in a mean-reverting market loses money. The system currently can't detect this.
- **Wrong conclusions from backtests**: A backtest over 2023-2024 might be 80% trending, 20% choppy. The Sharpe of 1.2 is achievable only in trending. When the market switches to choppy, the strategy fails.
- **No adaptive logic**: Human quants switch strategies when regime changes. The system has no mechanism for this.
- **Regime-dependent risk**: Drawdown sizes differ by regime. MaxDD in a volatile regime should be evaluated differently than MaxDD in a quiet regime.

## What to Build

### 1. Regime Classifier Module — New `vinu_features/compute/regime/`

**Option A: HMM-Based (Recommended)**

```python
from hmmlearn import hmm
import numpy as np

class HMMRegimeClassifier:
    def __init__(self, n_regimes=4):
        self.model = hmm.GaussianHMM(
            n_components=n_regimes,
            covariance_type="full",
            n_iter=100,
        )

    def fit(self, features_df):
        """Features: [returns_5d, vol_20d, correlation_20d, skew_20d]"""
        self.model.fit(features_df.values)

    def classify(self, features_df):
        """Returns regime labels [0, 1, 2, 3] for each row"""
        return self.model.predict(features_df.values)

    def label_regimes(self, feature_means):
        """
        Auto-label regimes based on feature characteristics:
        - High return + low vol → "trending"
        - Low return + high vol → "mean_reverting"
        - High vol + negative skew → "volatile"
        - Low vol + low return → "quiet"
        """
```

**Option B: Simple Volatility-Based (Faster, less accurate)**

```python
class SimpleRegimeClassifier:
    def classify(self, returns, window=20):
        """
        - vol < 15th percentile → "quiet"
        - vol > 85th percentile → "high_vol"
        - autocorr(returns) > 0.3 → "trending"
        - autocorr(returns) < -0.2 → "mean_reverting"
        - else → "neutral"
        """
```

### 2. Feature Engineering for Regime Detection

Required features to feed the classifier:

```
returns_5d    = close.pct_change(5)
returns_21d   = close.pct_change(21)
vol_20d       = returns_5d.rolling(20).std() * sqrt(252)
skew_20d      = returns_5d.rolling(20).skew()
kurt_20d      = returns_5d.rolling(20).kurt()
autocorr_5d   = returns_5d.rolling(20).apply(lambda x: x.autocorr())
range_20d     = (high.rolling(20).max() - low.rolling(20).min()) / close
volume_ratio  = volume / volume.rolling(20).mean()
```

### 3. Risk Critic Integration — Modify `loop.py`

```python
def _rule_based_check(self, result, story, drawdowns, iteration):
    regime_distribution = self._regime_classifier.get_distribution(
        result.daily_returns
    )

    # Check regime-specific performance
    regime_metrics = result.compute_regime_metrics(self._regime_classifier)

    for regime, metrics in regime_metrics.items():
        if metrics.sharpe < 0.3 and regime_distribution[regime] > 0.2:
            suggestions.append(
                f"Strategy fails in {regime} regime (Sharpe {metrics.sharpe:.2f}), "
                f"which accounts for {regime_distribution[regime]*100:.0f}% of the period. "
                f"Add {regime}-contingent filter"
            )

    # Rule 8: Regime concentration risk
    dominant_regime = max(regime_distribution, key=regime_distribution.get)
    if regime_distribution[dominant_regime] > 0.6:
        suggestions.append(
            f"Strategy tested on {regime_distribution[dominant_regime]*100:.0f}% "
            f"{dominant_regime} regime — performance may not generalize"
        )
```

### 4. Generator Integration — Modify `generator.py`

```python
def select_template_for_regime(regime: str, user_idea: str) -> str:
    """
    trending → crossover or momentum (prefer trend-following)
    mean_reverting → RSI or Bollinger (prefer mean-reversion)
    high_vol → Add ATR filter to whatever chosen
    quiet → preference for low-beta strategies
    """
    if regime == "trending":
        return CROSSOVER_TEMPLATE
    elif regime == "mean_reverting":
        return RSI_TEMPLATE
    elif regime == "high_vol":
        return (CROSSOVER_TEMPLATE + ATR_FILTER_TEMPLATE)
    else:
        return MOMENTUM_TEMPLATE
```

### 5. Strategy Code — Regime-Contingent Logic

Extend the generated strategy to include regime-based conditional execution:

```python
def generate_weights(self, data: pd.DataFrame) -> pd.Series:
    regime = data.get('regime', 'neutral')

    base_signal = fast_ma > slow_ma  # original crossover logic

    # Regime-contingent override
    signal = pd.Series(0.0, index=data.index)
    if regime == 'trending':
        signal = base_signal.astype(float)
    elif regime == 'neutral':
        signal = base_signal.astype(float) * 0.5
    # regime == 'mean_reverting': stay out (signal stays 0)

    return signal * self.allocation
```

### 6. New Config Fields

```python
class ResearchConfig:
    regime_enabled: bool = True
    regime_classifier: str = "hmm"        # "hmm" or "simple"
    regime_n_states: int = 4
    regime_min_regime_pct: float = 0.05   # Ignore regimes < 5% of data
```

## Code Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `vinu_features/compute/regime/hmm.py` | **NEW** | HMM regime classifier |
| `vinu_features/compute/regime/simple.py` | **NEW** | Simple threshold-based classifier |
| `vinu_features/compute/regime/__init__.py` | **NEW** | Regime classifier factory |
| `vinu_research/loop.py` | MODIFY | Regime-aware risk critic rules |
| `vinu_research/generator.py` | MODIFY | Regime-aware template selection |
| `vinu_research/config.py` | MODIFY | Regime-related config fields |
| `vinu_simulator/models/metrics.py` | MODIFY | Add regime_performance field |
| `vinu_research/report.py` | MODIFY | Add regime distribution section |
| `tests/test_regime.py` | **NEW** | Unit tests for classifiers |

## Complexity & Verdict

- **Difficulty**: High (HMM requires statistical knowledge, careful feature selection)
- **Lines of code**: ~600-800 total
- **Priority**: **HIGH** — without regime awareness, strategies are blind to market context
- **Dependencies**: `hmmlearn` (scikit-learn ecosystem), or build simple threshold-based without deps
- **Risk**: Medium — regime classifier could misclassify; must allow manual override
- **Time estimate**: 5-8 days

## Implementation Order

1. Build HMM-based classifier first (the simpler version)
2. Integrate feature computation into vinu-features pipeline
3. Wire into vinu-research loop (add regime distribution to backtest result)
4. Add risk critic rules for regime-specific failures
5. Add regime-contingent code generation
6. Write comprehensive tests with synthetic regime data
