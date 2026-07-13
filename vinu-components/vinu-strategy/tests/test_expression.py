import pytest

from vinu_strategy.engine.expression import evaluate_expression, ExpressionError


class TestEvaluateExpression:
    def test_basic_arithmetic(self):
        ctx = {"SMA_9": 110.0, "SMA_21": 100.0}
        result = evaluate_expression("SMA_9 / SMA_21 - 1", ctx)
        assert abs(result - 0.1) < 0.001

    def test_max_function(self):
        ctx = {"RSI_14": 25.0}
        expr = "max(0, (30 - RSI_14) / 30)"
        result = evaluate_expression(expr, ctx)
        assert abs(result - 5.0 / 30.0) < 0.001

    def test_max_function_negative_clamp(self):
        ctx = {"RSI_14": 50.0}
        expr = "max(0, (30 - RSI_14) / 30) - max(0, (RSI_14 - 70) / 30)"
        result = evaluate_expression(expr, ctx)
        assert abs(result - 0.0) < 0.001

    def test_abs_function(self):
        ctx = {"val": -5.0}
        result = evaluate_expression("abs(val)", ctx)
        assert result == 5.0

    def test_round_function(self):
        ctx = {"val": 3.14159}
        result = evaluate_expression("round(val, 2)", ctx)
        assert result == 3.14

    def test_min_function(self):
        ctx = {"a": 10.0, "b": 20.0}
        result = evaluate_expression("min(a, b)", ctx)
        assert result == 10.0

    def test_power(self):
        ctx = {"x": 3.0}
        result = evaluate_expression("x ** 2", ctx)
        assert result == 9.0

    def test_modulo(self):
        ctx = {"x": 10.0}
        result = evaluate_expression("x % 3", ctx)
        assert result == 1.0

    def test_negative_numbers(self):
        ctx = {"x": -5.0}
        result = evaluate_expression("-x", ctx)
        assert result == 5.0

    def test_unknown_variable(self):
        ctx = {"X": 1.0}
        with pytest.raises(ExpressionError, match="Unknown variable"):
            evaluate_expression("Y + 1", ctx)

    def test_disallowed_function(self):
        ctx = {"x": 1.0}
        with pytest.raises(ExpressionError, match="not allowed"):
            evaluate_expression("int(x)", ctx)

    def test_empty_expression(self):
        with pytest.raises(ExpressionError, match="empty"):
            evaluate_expression("", {})

    def test_invalid_syntax(self):
        with pytest.raises(ExpressionError, match="Invalid expression syntax"):
            evaluate_expression("+ +", {})

    def test_nested_max(self):
        ctx = {"RSI_14": 25.0, "ADX_14": 30.0}
        expr = "max(RSI_14, ADX_14) / min(RSI_14, ADX_14)"
        result = evaluate_expression(expr, ctx)
        assert abs(result - 30.0 / 25.0) < 0.001

    def test_division_by_zero(self):
        ctx = {"x": 1.0, "y": 0.0}
        with pytest.raises(ZeroDivisionError):
            evaluate_expression("x / y", ctx)
