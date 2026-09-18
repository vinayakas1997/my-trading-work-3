"""Tests for `classify_strategy_family` (B, `Artifact.strategy_family`)."""

from __future__ import annotations

from vinu_research.strategy_family import UNCLASSIFIED, classify_strategy_family


class TestClassifyStrategyFamily:
    def test_none_and_empty_are_unclassified(self):
        assert classify_strategy_family(None) == UNCLASSIFIED
        assert classify_strategy_family("") == UNCLASSIFIED

    def test_sma_crossover_is_momentum(self):
        assert classify_strategy_family("SMA crossover") == "momentum"
        assert classify_strategy_family("test SMA crossover on AAPL") == "momentum"

    def test_mean_reversion_bollinger_is_mean_reversion(self):
        assert classify_strategy_family("mean reversion using bollinger bands strategy") == "mean_reversion"

    def test_rsi_oversold_is_mean_reversion(self):
        assert classify_strategy_family("buy when RSI is oversold") == "mean_reversion"

    def test_counter_trend_is_mean_reversion_not_momentum(self):
        # Real false-positive risk this classifier deliberately avoids --
        # "counter-trend" contains "trend" but is a mean-reversion synonym.
        assert classify_strategy_family("counter-trend reversal on SPY") == "mean_reversion"

    def test_trend_following_fallback_string_is_momentum(self):
        # ResearchService._propose_idea's non-LLM fallback string, verbatim.
        assert classify_strategy_family(
            "Trend-following strategy for accumulation stage with low risk regime"
        ) == "momentum"

    def test_momentum_breakout_resolves_to_momentum(self):
        # Real value from this codebase's own tests -- momentum is checked
        # before breakout deliberately, see the module docstring.
        assert classify_strategy_family("momentum breakout") == "momentum"

    def test_pure_breakout_is_breakout(self):
        assert classify_strategy_family("donchian channel breakout system") == "breakout"

    def test_volatility_targeting_is_volatility(self):
        assert classify_strategy_family("volatility targeting overlay") == "volatility"

    def test_pairs_trading_is_stat_arb(self):
        assert classify_strategy_family("pairs trading between AAPL and MSFT") == "stat_arb"

    def test_earnings_is_event_driven(self):
        assert classify_strategy_family("earnings drift strategy") == "event_driven"

    def test_refresh_and_refine_strings_are_unclassified(self):
        # Real autonomous-refresh user_idea values (service.py) -- restate
        # no style at all, a real "unclassified" case, not a bug.
        assert classify_strategy_family("Refresh strategy_abc123") == UNCLASSIFIED
        assert classify_strategy_family("Refine existing strategy for AAPL_42") == UNCLASSIFIED

    def test_generic_test_string_is_unclassified(self):
        assert classify_strategy_family("test") == UNCLASSIFIED

    def test_case_insensitive(self):
        assert classify_strategy_family("MOMENTUM STRATEGY") == "momentum"
        assert classify_strategy_family("Mean Reversion Play") == "mean_reversion"
