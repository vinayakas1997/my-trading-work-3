from __future__ import annotations

import re

from vinu_research.generator import (
    BUILTIN_RECIPES,
    _generate_from_description,
    _safe_format,
    find_recipe,
    generate_strategy,
    list_recipe_details,
    list_recipes,
)

_TEMPLATES = [
    "crossover", "triple_crossover", "macd", "vwap_crossover",
    "rsi", "bollinger_bands", "mean_reversion_zscore",
    "momentum", "rate_of_change", "breakout",
    "volatility_breakout", "supertrend", "adx_filtered_crossover",
    "volume_confirmed_breakout", "momentum_mean_reversion",
]


class TestListRecipes:
    def test_all_templates_present(self):
        recipes = list_recipes()
        for t in _TEMPLATES:
            assert t in recipes, f"Missing template: {t}"
        assert len(recipes) >= 15

    def test_list_recipe_details_returns_metadata(self):
        details = list_recipe_details()
        assert len(details) >= 15
        for d in details:
            assert "key" in d
            assert "name" in d
            assert "description" in d
            assert "regimes" in d
            assert "params" in d


class TestAllTemplates:
    def test_each_template_generates_valid_code(self):
        for recipe in _TEMPLATES:
            code = generate_strategy(recipe=recipe)
            assert "class UserStrategy" in code, f"{recipe}: missing UserStrategy"
            assert "def generate_weights" in code, f"{recipe}: missing generate_weights"
            assert "return signal" in code, f"{recipe}: missing return signal"

    def test_each_template_accepts_custom_params(self):
        for recipe in _TEMPLATES:
            code = generate_strategy(recipe=recipe, params={"allocation": 0.5})
            assert "class UserStrategy" in code

    def test_each_template_has_unique_body(self):
        bodies = set()
        for recipe in _TEMPLATES:
            code = generate_strategy(recipe=recipe)
            bodies.add(code)
        assert len(bodies) == len(_TEMPLATES)

    def test_parameters_are_injected(self):
        code = generate_strategy(recipe="crossover", params={"fast_period": 10, "slow_period": 30})
        assert "self.fast_period" in code
        assert "self.slow_period" in code

    def test_no_unresolved_template_placeholders(self):
        for recipe in _TEMPLATES:
            code = generate_strategy(recipe=recipe)
            remaining = re.findall(r"\{(\w+)\}", code)
            assert not remaining, f"{recipe}: unresolved placeholders: {remaining}"


class TestGenerateCrossover:
    def test_generates_valid_code(self):
        code = generate_strategy(recipe="crossover")
        assert "class UserStrategy" in code
        assert "fast_ma" in code
        assert "slow_ma" in code

    def test_uses_custom_params(self):
        code = generate_strategy(recipe="crossover", params={"fast_period": 10, "slow_period": 30})
        assert "fast_ma" in code


class TestGenerateRSI:
    def test_generates_rsi_code(self):
        code = generate_strategy(recipe="rsi")
        assert "rsi" in code

    def test_custom_rsi_period(self):
        code = generate_strategy(recipe="rsi", params={"rsi_period": 7, "oversold": 25})
        assert "class UserStrategy" in code


class TestGenerateMomentum:
    def test_generates_momentum_code(self):
        code = generate_strategy(recipe="momentum")
        assert "momentum" in code


class TestSanitizeParams:
    def test_unknown_keys_removed(self):
        code = generate_strategy(recipe="crossover", params={"unknown_key": 100})
        assert "unknown_key" not in code

    def test_none_params(self):
        code = generate_strategy(recipe="crossover", params=None)
        assert "class UserStrategy" in code


class TestFindRecipe:
    def test_finds_crossover_by_keywords(self):
        assert find_recipe("sma crossover") == "crossover"
        assert find_recipe("golden cross") == "crossover"
        assert find_recipe("death cross") == "crossover"

    def test_finds_rsi_by_keywords(self):
        assert find_recipe("rsi mean reversion") == "rsi"
        assert find_recipe("oversold") == "rsi"
        assert find_recipe("overbought") == "rsi"

    def test_finds_momentum_by_keywords(self):
        assert find_recipe("trend following") == "momentum"
        assert find_recipe("rate of change") == "rate_of_change"

    def test_finds_bollinger_by_keywords(self):
        assert find_recipe("bollinger bands") == "bollinger_bands"
        assert find_recipe("bb strategy") == "bollinger_bands"

    def test_finds_breakout_by_keywords(self):
        assert find_recipe("breakout") == "breakout"
        assert find_recipe("52 week high breakout") == "breakout"

    def test_finds_macd_by_keywords(self):
        assert find_recipe("macd crossover") == "macd"

    def test_finds_adx_by_keywords(self):
        assert find_recipe("adx filtered crossover") == "adx_filtered_crossover"
        assert find_recipe("trend strength") == "adx_filtered_crossover"

    def test_finds_volume_breakout_by_keywords(self):
        assert find_recipe("volume confirmed breakout") == "volume_confirmed_breakout"

    def test_finds_hybrid_by_keywords(self):
        assert find_recipe("hybrid momentum mean reversion") == "momentum_mean_reversion"

    def test_returns_none_for_gibberish(self):
        assert find_recipe("asdfghjkl") is None

    def test_best_match_is_selected(self):
        result = find_recipe("volatility breakout breakout")
        assert result is not None


class TestGenerateFromDescription:
    def test_keyword_detection_routes_to_correct_template(self):
        code = _generate_from_description("buy when RSI oversold", {})
        assert "rsi" in code

    def test_fallback_to_crossover(self):
        code = _generate_from_description("some random strategy idea", {})
        assert "fast_ma" in code or "slow_ma" in code

    def test_specific_keyword_routes_correctly(self):
        code = _generate_from_description("MACD crossover strategy", {})
        assert "ema_fast" in code or "macd_line" in code
