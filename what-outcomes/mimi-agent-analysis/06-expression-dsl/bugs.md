# Angle 06: Expression DSL — Bugs

| # | Bug | Error | Root Cause | Status |
|---|-----|-------|------------|--------|
| 1 | QLib evaluator `evaluate_expression` not exported | `ImportError: cannot import name 'evaluate_expression'` | The function is named `evaluate` in `evaluator.py`, not documented as `evaluate_expression` | Open |
| 2 | Strategy engine import path mismatch | `ModuleNotFoundError: No module named 'vinu_strategy.rules'` | Correct path is `vinu_strategy.engine.expression` not `vinu_strategy.rules.expression` | Open |
| 3 | `Ref($close, 1)` returns all None | `return` expression has 0 non-null out of 100 | `Ref($close, 1)` shifts 1 period forward, making the last element NaN which `evaluate()` converts to None. The entire series becomes None because the forward-shifted close creates NaN at the last position. | Design limitation |
| 4 | `compute_expression()` cannot use indicator names (SMA, RSI) | Unknown factor error | Only registered alpha factor IDs work; indicators require different path | Design |
| 5 | No logical operators in `compute_expression()` | `&&`, `||`, comparisons not available | Only QLib evaluator supports `&&`/`||` | Design |
| 6 | No `scale` function in `compute_expression()` | Function exists in `operators.py` but not wired | `scale` is not in the `_FUNCTIONS` dict of `factor_expressions.py` | Open |
