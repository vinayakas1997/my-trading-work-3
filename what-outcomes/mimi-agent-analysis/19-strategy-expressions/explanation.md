# Strategy Expressions

## What This Angle Studies
Tests the strategy expression engine for allocation signals and rules DSL: YAML-based pipeline with 8 condition operators and 4 action types.

## Results
vinu_strategy.engine.expression works: signal expression (SMA_9/SMA_21-1=0.013), RSI mean reversion (max(0,(30-RSI)/30)-max(0,(RSI-70)/30)=0.0 at RSI=45), momentum*ADX (0.028). Rules DSL (when/then with 8 operators and 4 actions) works via strategy YAML definitions.

## Execution Time
~0.1s

### Bugs Found
None.