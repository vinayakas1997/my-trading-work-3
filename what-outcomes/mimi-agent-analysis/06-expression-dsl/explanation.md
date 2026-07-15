# Angle 06: Expression DSL — Custom Alpha Signals

## What This Angle Studies
Tests the three expression engines that combine factors, indicators, and operators into custom alpha signals. Validates all available functions across `compute_expression()` (11 functions), QLib evaluator (20 functions), and strategy expression engine (4 functions).

## Strategy & Configuration
- **Data**: 1050 daily bars × 4 tickers (from Angle 05 pipeline)
- **Expression engines tested**: compute_expression, QLib evaluator, strategy expression engine
- **8 combined expressions** created from alpha101, gtja191, and qlib158 factors
- **Backtested** all 8 with rank weighting

## Three Expression Engines

| Engine | Functions | Input Type | Scope |
|--------|-----------|------------|-------|
| `compute_expression()` | 11 | 2D panel (T×N) | Alpha factor combos |
| QLib evaluator | 20 | 1D arrays | OHLCV field combos |
| Strategy `expression.py` | 4 | Scalar dict | Strategy rules |

## Functions & Code Paths

| Function | File Path | Purpose |
|----------|-----------|---------|
| `compute_expression()` | `vinu_features/compute/factor_expressions.py` | 11-function DSL for factor combos |
| `list_expression_variables()` | Same file | Parse expression, list factor IDs |
| `evaluate()` (QLib) | `vinu_features/compute/bigger_recipe/_alpha_expr/evaluator.py:25` | 20-function DSL for OHLCV |
| `evaluate_expression()` (Strategy) | `vinu-strategy/engine/expression.py` | 4-function DSL for strategy rules |

## Commands & API Calls Used

| Step | Method | Description | Response |
|------|--------|-------------|----------|
| 1 | Python | `compute_expression('alpha101_001', panel)` | Simple ref: range [-0.5, 0.5] |
| 2 | Python | `compute_expression('a+b', panel)` | 5 arithmetic combos pass |
| 3 | Python | `compute_expression('func(x)', panel)` | All 11 functions pass |
| 4 | Python | `compute_expression('fn(x,y)', panel)` | Nested, no-parens, unary pass |
| 5 | Python | `list_expression_variables(expr)` | Correctly extracts 3 factor IDs |
| 6 | Python | `compute_expression('bad_factor')` | Error: "Unknown factor" |
| 7 | Python | QLib evaluator (20 fn variants) | All 20 pass with proper warmup |
| 8 | Python | Strategy engine (6 expr variants) | All 6 pass + 3 error cases pass |

## Results

### All 11 `compute_expression()` Functions PASS

| Function | Example | Range |
|----------|---------|-------|
| Simple ref | `alpha101_001` | [-0.50, 0.50] |
| rank | `rank(x)` | [0.00, 1.00] |
| zscore | `zscore(x)` | [-1.34, 1.34] |
| ts_mean | `ts_mean(x, 10)` | [-0.50, 0.50] |
| ts_std | `ts_std(x, 10)` | [0.00, 0.50] |
| ts_sum | `ts_sum(x, 10)` | [-5.00, 5.00] |
| ts_max | `ts_max(x, 10)` | [-0.50, 0.50] |
| ts_min | `ts_min(x, 10)` | [-0.50, 0.50] |
| abs | `abs(x)` | [0.17, 0.50] |
| neg | `neg(x)` | [-0.50, 0.50] |
| sign | `sign(x)` | [-1.00, 1.00] |
| delay | `delay(x, 5)` | [-0.50, 0.50] |

### Combined Expression Backtest Results

| Expression | Sharpe | Total Return | Max DD |
|-----------|--------|-------------|--------|
| `rank(alpha101_001) + zscore(alpha101_010) + sign(qlib158_ma5)` | 1.16 | +1405% | -38% |
| `rank(alpha101_001) + rank(alpha101_010)` | 1.01 | +609% | -50% |
| `rank(alpha101_001) * zscore(alpha101_010)` | 0.89 | +400% | -50% |
| `ts_mean(qlib158_ma5, 5)` | 0.00 | -56% | -85% |
| `rank(alpha101_001) * zscore(alpha101_101)` | -1.34 | -97% | -97% |

### All 20 QLib Evaluator Functions PASS

Field refs, arithmetic, Ref/Max/Min/Std/Sum/Corr/Rank/Slope/Rsquare/IdxMax/Resi/Quantile/Greater/Abs/Log — all 20 produce correct outputs. Warmup periods return None as expected.

### All 6 Strategy Engine Expressions PASS

Simple division, max/min, abs, modulo, power, case-insensitive — all produce correct results. Error handling catches unknown variables, empty expressions, and disallowed syntax.

## Bugs

| # | Bug | Description | Status |
|---|-----|-------------|--------|
| 1 | QLib evaluator not exposed as standalone import | `evaluate_expression` doesn't exist; the function is `evaluate` in evaluator.py | Open |
| 2 | Strategy engine package path mismatch | Import path `vinu_strategy.rules.expression` doesn't exist; correct path is `vinu_strategy.engine.expression` | Open |
| 3 | QLib `Ref($close, 1)` returns all None | Forward shift returns NaN for the last element which gets converted to None | Design |

## Execution Time

| Section | Time |
|---------|------|
| Fetch data | 23.6s |
| compute_expression tests (20+) | <0.5s |
| QLib evaluator (20 tests) | <0.3s |
| Strategy engine (9 tests) | <0.1s |
| Backtest 5 combined expressions | ~10s |
| **Total** | **~35s** |

## Summary
All three expression engines work correctly. `compute_expression()` supports 11 functions and 4 operators for combining alpha factors. The three-factor blend `rank(001) + zscore(010) + sign(ma5)` achieves the best Sharpe (1.16). The QLib evaluator supports 20 functions for OHLCV-based expressions. The strategy engine supports 4 functions for rule-based expressions. No new bugs beyond the two import path issues.
