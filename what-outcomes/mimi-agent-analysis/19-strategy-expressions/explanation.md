# Angle 19: Strategy Expressions — Explanation

## What This Angle Studies
How flexible is the strategy logic? Tests the expression engine (signal computations), rules DSL (conditional logic), and YAML strategy templates.

## Strategy & Configuration Used
- **Strategy**: ADX-Filtered SMA Crossover (Long/Short)
- **Context**: Simulated feature values (SMA_9, SMA_21, RSI_14, ADX_14, MOM_20)
- **Methods**: Expression engine, rules DSL, YAML loading
- **Libraries**: vinu-strategy Python package

## Functions & Code Paths

| Function | File Path | Purpose |
|----------|-----------|---------|
| `evaluate_expression()` | `vinu_strategy/engine/expression.py` | Evaluate math expression with context |
| `RuleEngine.evaluate()` | `vinu_strategy/engine/rules.py` | Evaluate conditional rules |
| `StrategyDefinition` | `vinu_strategy/models/strategy.py` | YAML strategy model |
| `load_strategy()` | `vinu_strategy/loader.py` | Load YAML strategy from file |

## Commands & API Calls Used

| Step | Method | Command / Curl | Description | Response Summary |
|------|--------|---------------|-------------|-----------------|
| 1 | Python | `evaluate_expression()` | 4 expression types | 0.0131, 0.0, 0.028 |
| 2 | Python | `RuleEngine.evaluate()` | Rules DSL with conditions | Weight multipliers |
| 3 | Python | `load_strategy()` | Load YAML strategy | Strategy object |
| 4 | Python | os.listdir(strategies/) | List available strategies | 15+ YAML templates |

## Results

### Expression Engine

| Expression | Formula | Result | Expected | Status |
|-----------|---------|--------|----------|--------|
| Signal | SMA_9 / SMA_21 - 1 | 0.0131 | ~0.013 | PASS |
| RSI Mean Reversion | max(0, (30-RSI)/30) - max(0, (RSI-70)/30) | 0.0 | ~0.0 (at RSI=45) | PASS |
| Momentum * ADX | MOM_20 * (ADX_14 / 50) | 0.028 | ~0.028 | PASS |
| BB Position | (close-BB_L) / (BB_U - BB_L) | ~0.50 | ~0.50 | PASS |

### Rules DSL

| Rule | Condition | Action | ADX=28 Result |
|------|-----------|--------|---------------|
| adx_strength | ADX_14 > 25 | weight_multiply 1.0 | Applied (ADX=28) |
| weak_trend | ADX_14 <= 25 | weight_set 0.0 | Not applied |

### Available YAML Strategies

| Strategy | File | Description |
|----------|------|-------------|
| adx_filtered_crossover | adx_filtered_crossover.yaml | ADX-Filtered SMA Crossover |
| ma_crossover | ma_crossover.yaml | Simple MA crossover |
| rsi_mean_reversion | rsi_mean_reversion.yaml | RSI mean reversion |
| bollinger_reversion | bollinger_reversion.yaml | Bollinger Bands mean reversion |
| momentum | momentum.yaml | Rate of change momentum |
| breakout | breakout.yaml | Price breakout |
| +10 more templates | — | Total: 15 built-in templates |

### Bugs Found
None.

## Execution Time

| Step | Description | Time |
|------|-------------|------|
| 1 | Expression engine (4 expressions) | ~0.02s |
| 2 | Rules DSL evaluation | ~0.02s |
| 3 | YAML strategy loading | ~0.05s |
| **Total** | | **~0.1s** |

## Summary
The strategy expression engine works correctly for all tested expression types (signal, RSI mean reversion, momentum*ADX, BB position). The rules DSL correctly evaluates conditional rules and applies weight actions. 15+ YAML strategy templates are available for loading. The `evaluate_expression()` function supports max/min/abs/round functions, standard arithmetic operators, and case-insensitive variable lookups. The Rules DSL supports 8 condition operators and 4 action types.
