from __future__ import annotations

from vinu_research.generator import (
    BUILTIN_RECIPES,
    generate_strategy,
    list_recipes,
)


class TestListRecipes:
    def test_lists_builtin(self):
        recipes = list_recipes()
        assert "crossover" in recipes
        assert "rsi" in recipes
        assert "momentum" in recipes


class TestGenerateCrossover:
    def test_generates_valid_code(self):
        code = generate_strategy(recipe="crossover")
        assert "class UserStrategy" in code
        assert "def generate_weights" in code
        assert "fast_ma" in code
        assert "slow_ma" in code

    def test_uses_custom_params(self):
        code = generate_strategy(recipe="crossover", params={"fast_period": 10, "slow_period": 30})
        assert "fast_ma" in code


class TestGenerateRSI:
    def test_generates_rsi_code(self):
        code = generate_strategy(recipe="rsi")
        assert "class UserStrategy" in code
        assert "rsi" in code
        assert "rsi_14" in code or "rsi_period" in code

    def test_custom_rsi_period(self):
        code = generate_strategy(recipe="rsi", params={"rsi_period": 7, "oversold": 25})
        assert "class UserStrategy" in code


class TestGenerateMomentum:
    def test_generates_momentum_code(self):
        code = generate_strategy(recipe="momentum")
        assert "class UserStrategy" in code
        assert "momentum" in code


class TestSanitizeParams:
    def test_unknown_keys_removed(self):
        sanitized = generate_strategy(recipe="crossover", params={"unknown_key": 100})
        assert "unknown_key" not in sanitized

    def test_none_params(self):
        code = generate_strategy(recipe="crossover", params=None)
        assert "class UserStrategy" in code
