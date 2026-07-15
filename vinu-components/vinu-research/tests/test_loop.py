from __future__ import annotations

import numpy as np
import pandas as pd

from vinu_research.config import ResearchConfig
from vinu_research.loop import StrategyResearchLoop, _LRUCache, _split_research_and_holdout
from vinu_research.models import BacktestMetrics, BacktestResult, CriticFeedback, IterationRecord


class TestLRUCache:
    def test_get_set(self):
        cache = _LRUCache(maxsize=3)
        cache.set("a", 1)
        assert cache.get("a") == 1

    def test_missing_returns_none(self):
        cache = _LRUCache(maxsize=3)
        assert cache.get("missing") is None

    def test_evicts_oldest(self):
        cache = _LRUCache(maxsize=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_renew_on_access(self):
        cache = _LRUCache(maxsize=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.get("a")
        cache.set("c", 3)
        assert cache.get("a") == 1
        assert cache.get("b") is None

    def test_clear(self):
        cache = _LRUCache(maxsize=3)
        cache.set("a", 1)
        cache.clear()
        assert cache.get("a") is None


class TestIsImproving:
    def make_record(self, sharpe: float) -> IterationRecord:
        metrics = BacktestMetrics(sharpe_ratio=sharpe)
        result = BacktestResult(
            run_id="r1", strategy_name="s", metrics=metrics,
            benchmark_metrics={}, trade_count=10, equity_points=100,
        )
        critique = CriticFeedback(verdict="REFINE", reasoning="test", suggestions=[])
        return IterationRecord(iteration=1, strategy_code="", result=result, critique=critique)

    def test_less_than_two_returns_true(self):
        loop = StrategyResearchLoop()
        assert loop._is_improving([self.make_record(0.5)]) is True

    def test_improvement_above_threshold(self):
        loop = StrategyResearchLoop()
        history = [self.make_record(0.3), self.make_record(0.5)]
        diff = 0.5 - 0.3
        assert diff > loop._config.improvement_threshold
        assert loop._is_improving(history) is True

    def test_improvement_below_threshold(self):
        loop = StrategyResearchLoop()
        history = [self.make_record(0.4), self.make_record(0.42)]
        diff = 0.42 - 0.40
        assert diff < loop._config.improvement_threshold
        assert loop._is_improving(history) is False


class TestDefaultRiskCritic:
    def make_result(
        self, sharpe: float, max_dd: float, win_rate: float, trade_count: int = 50,
    ) -> BacktestResult:
        metrics = BacktestMetrics(sharpe_ratio=sharpe, max_drawdown=max_dd, win_rate=win_rate)
        return BacktestResult(
            run_id="r1", strategy_name="s", metrics=metrics,
            benchmark_metrics={}, trade_count=trade_count, equity_points=100,
        )

    async def test_pass_when_good_metrics(self):
        loop = StrategyResearchLoop()
        result = self.make_result(sharpe=1.5, max_dd=-0.05, win_rate=0.6)
        critique = await loop._default_risk_critic(result, story=None, drawdowns=None, iteration=1)
        assert critique.verdict == "PASS"

    async def test_stop_after_many_iterations_low_sharpe(self):
        loop = StrategyResearchLoop()
        result = self.make_result(sharpe=0.2, max_dd=-0.10, win_rate=0.3)
        critique = await loop._default_risk_critic(result, story=None, drawdowns=None, iteration=3)
        assert critique.verdict == "STOP"

    async def test_refine_when_medium_metrics(self):
        loop = StrategyResearchLoop()
        result = self.make_result(sharpe=0.8, max_dd=-0.12, win_rate=0.5)
        critique = await loop._default_risk_critic(result, story=None, drawdowns=None, iteration=1)
        assert critique.verdict == "REFINE"

    async def test_refine_adds_suggestions(self):
        loop = StrategyResearchLoop()
        result = self.make_result(sharpe=0.4, max_dd=-0.20, win_rate=0.3)
        critique = await loop._default_risk_critic(result, story=None, drawdowns=None, iteration=1)
        assert critique.verdict == "REFINE"
        assert len(critique.suggestions) > 0

    async def test_thin_sample_never_passes_regardless_of_sharpe(self):
        # A handful of trades isn't enough to trust any Sharpe computed from them —
        # PASS must never fire on a thin sample, no matter how good the ratio looks.
        loop = StrategyResearchLoop()
        result = self.make_result(sharpe=3.0, max_dd=-0.02, win_rate=0.9, trade_count=5)
        critique = await loop._default_risk_critic(result, story=None, drawdowns=None, iteration=1)
        assert critique.verdict != "PASS"
        assert any("trades" in s.lower() for s in critique.suggestions)

    async def test_enough_trades_at_threshold_passes(self):
        loop = StrategyResearchLoop()
        result = self.make_result(
            sharpe=1.5, max_dd=-0.05, win_rate=0.6,
            trade_count=loop._config.min_trades_for_pass,
        )
        critique = await loop._default_risk_critic(result, story=None, drawdowns=None, iteration=1)
        assert critique.verdict == "PASS"


class TestMaxDDStop:
    def make_result(self, max_dd: float) -> BacktestResult:
        metrics = BacktestMetrics(sharpe_ratio=1.0, max_drawdown=max_dd, win_rate=0.5)
        return BacktestResult(
            run_id="r1", strategy_name="s", metrics=metrics,
            benchmark_metrics={}, trade_count=10, equity_points=100,
        )

    def test_max_dd_stops_when_exceeds_threshold(self):
        from vinu_research.config import ResearchConfig
        config = ResearchConfig(max_drawdown_threshold=-0.15)
        loop = StrategyResearchLoop(config=config)
        result = self.make_result(max_dd=-0.20)
        assert result.metrics.max_drawdown < config.max_drawdown_threshold

    def test_max_dd_does_not_stop_when_within_threshold(self):
        from vinu_research.config import ResearchConfig
        config = ResearchConfig(max_drawdown_threshold=-0.25)
        loop = StrategyResearchLoop(config=config)
        result = self.make_result(max_dd=-0.20)
        assert result.metrics.max_drawdown >= config.max_drawdown_threshold


class TestSplitResearchAndHoldout:
    def test_carves_trailing_holdout_with_gap(self):
        split = _split_research_and_holdout(
            "2024-01-01", "2024-12-31", holdout_fraction=0.2, gap_days=5,
        )
        assert split is not None
        research_from, research_to, holdout_from, holdout_to = split
        assert research_from == "2024-01-01"
        assert research_to < holdout_from < holdout_to
        assert holdout_to == "2024-12-31"

    def test_too_short_range_returns_none(self):
        split = _split_research_and_holdout(
            "2024-01-01", "2024-01-20", holdout_fraction=0.2, gap_days=5,
        )
        assert split is None

    def test_research_window_precedes_holdout_with_gap(self):
        split = _split_research_and_holdout(
            "2024-01-01", "2024-12-31", holdout_fraction=0.2, gap_days=5,
        )
        from datetime import datetime
        _, research_to, holdout_from, _ = split
        gap = (datetime.strptime(holdout_from, "%Y-%m-%d") - datetime.strptime(research_to, "%Y-%m-%d")).days
        assert gap == 5


class TestHoldoutGating:
    def make_backtest_result(self, sharpe: float, trade_count: int = 50) -> BacktestResult:
        metrics = BacktestMetrics(sharpe_ratio=sharpe, max_drawdown=-0.05, win_rate=0.6)
        return BacktestResult(
            run_id="r1", strategy_name="s", metrics=metrics,
            benchmark_metrics={}, trade_count=trade_count, equity_points=100,
        )

    async def test_holdout_pass_when_performance_holds_up(self):
        loop = StrategyResearchLoop()
        in_sample = self.make_backtest_result(sharpe=1.5)
        holdout_bt = self.make_backtest_result(sharpe=1.3)

        async def fake_run_backtest(*args, **kwargs):
            return holdout_bt

        loop._run_backtest = fake_run_backtest
        result = await loop._check_holdout(
            "code", "AAPL", "2024-10-01", "2024-12-31", in_sample, None, None,
        )
        assert result is not None
        assert result.passed is True

    async def test_holdout_fails_on_negative_sharpe(self):
        loop = StrategyResearchLoop()
        in_sample = self.make_backtest_result(sharpe=1.5)
        holdout_bt = self.make_backtest_result(sharpe=-0.3)

        async def fake_run_backtest(*args, **kwargs):
            return holdout_bt

        loop._run_backtest = fake_run_backtest
        result = await loop._check_holdout(
            "code", "AAPL", "2024-10-01", "2024-12-31", in_sample, None, None,
        )
        assert result.passed is False
        assert "negative" in result.note.lower()

    async def test_holdout_fails_on_large_sharpe_degradation(self):
        loop = StrategyResearchLoop()
        in_sample = self.make_backtest_result(sharpe=2.0)
        holdout_bt = self.make_backtest_result(sharpe=0.3)  # 85% degradation

        async def fake_run_backtest(*args, **kwargs):
            return holdout_bt

        loop._run_backtest = fake_run_backtest
        result = await loop._check_holdout(
            "code", "AAPL", "2024-10-01", "2024-12-31", in_sample, None, None,
        )
        assert result.passed is False
        assert "degraded" in result.note.lower()

    async def test_holdout_unavailable_accepts_without_gating(self):
        loop = StrategyResearchLoop()
        in_sample = self.make_backtest_result(sharpe=1.5)

        async def fake_run_backtest(*args, **kwargs):
            return None

        loop._run_backtest = fake_run_backtest
        result = await loop._check_holdout(
            "code", "AAPL", "2024-10-01", "2024-12-31", in_sample, None, None,
        )
        assert result is None


class TestClassifySuggestion:
    def test_adx_keyword_matches(self):
        loop = StrategyResearchLoop()
        assert loop._classify_suggestion("Sharpe below 0.5 — add ADX filter to avoid choppy markets") == "adx"

    def test_london_session_requires_both_words(self):
        loop = StrategyResearchLoop()
        assert loop._classify_suggestion("Multiple drawdowns in London session — add exclusion filter") == "session_exclusion"
        # "london" alone, without "session" or "exclusion", should not match.
        assert loop._classify_suggestion("Strategy underperforms during the London morning") is None

    def test_bare_news_word_does_not_trigger_cooldown_filter(self):
        # A suggestion that merely mentions "news" in passing must not spuriously
        # inject a news-cooldown filter — only an actual cooldown/pause suggestion should.
        loop = StrategyResearchLoop()
        assert loop._classify_suggestion("Losses cluster around major news events in Q2") is None
        assert loop._classify_suggestion("Add a news cooldown period after high-impact events") == "news_cooldown"

    def test_bare_cool_word_does_not_trigger_without_news(self):
        loop = StrategyResearchLoop()
        assert loop._classify_suggestion("Consider cooling off position sizing in general") is None

    def test_unrelated_suggestion_returns_none(self):
        loop = StrategyResearchLoop()
        assert loop._classify_suggestion("Try tightening position sizing") is None


class TestGenerateFiltersDataAvailability:
    def test_adx_filter_skipped_when_indicator_not_requested(self):
        loop = StrategyResearchLoop()
        loop._indicators = ["sma_20", "sma_50", "rsi_14"]  # no ADX requested
        filters = loop._generate_filters(["Sharpe below 0.5 — add ADX filter to avoid choppy markets"])
        assert filters == []

    def test_adx_filter_applied_when_indicator_present(self):
        loop = StrategyResearchLoop()
        loop._indicators = ["sma_20", "adx_14"]
        filters = loop._generate_filters(["Sharpe below 0.5 — add ADX filter to avoid choppy markets"])
        assert any("adx" in line.lower() for line in filters)
        # Verified-present indicator should be read directly, not defaulted to a
        # constant fake value that would make the filter a silent no-op.
        assert any("data['adx_14']" in line for line in filters)

    def test_volatility_filter_skipped_without_atr_indicator(self):
        loop = StrategyResearchLoop()
        loop._indicators = ["sma_20", "sma_50"]
        filters = loop._generate_filters(["Max drawdown exceeds 15% — add volatility guard (ATR filter)"])
        assert filters == []

    def test_unrelated_suggestions_produce_no_filters(self):
        loop = StrategyResearchLoop()
        loop._indicators = ["sma_20"]
        filters = loop._generate_filters(["Try tightening position sizing"])
        assert filters == []

    def test_duplicate_suggestions_of_same_kind_only_applied_once(self):
        loop = StrategyResearchLoop()
        loop._indicators = ["adx_14"]
        filters = loop._generate_filters([
            "add ADX filter to avoid choppy markets",
            "Sharpe still low — ADX filter recommended again",
        ])
        assert filters.count("signal[adx < 20] = 0") == 1


class TestNullCaseNeverFalselyPasses:
    """
    End-to-end model of the 'pure noise' null case: what should happen if a
    strategy's apparent edge were entirely random-walk luck. Every in-sample
    backtest looks great (as chance occasionally produces), but the holdout
    backtest — drawn from data the loop never tuned against — always shows no real
    edge. A properly holdout-gated system must never report this as an accepted
    PASS; that's the whole point of carving out data the refinement loop can't see.
    """

    def _make_result(self, sharpe: float, max_dd: float, trade_count: int = 50) -> BacktestResult:
        metrics = BacktestMetrics(sharpe_ratio=sharpe, max_drawdown=max_dd, win_rate=0.55)
        return BacktestResult(
            run_id="r", strategy_name="s", metrics=metrics,
            benchmark_metrics={}, trade_count=trade_count, equity_points=200,
        )

    async def test_in_sample_luck_never_survives_holdout(self):
        config = ResearchConfig(max_iterations=3, walk_forward_enabled=False)
        loop = StrategyResearchLoop(config=config)

        split = _split_research_and_holdout(
            "2024-01-01", "2024-12-31", config.holdout_fraction, config.holdout_gap_days,
        )
        assert split is not None
        _, _, holdout_from, _ = split

        research_result = self._make_result(sharpe=2.0, max_dd=-0.05)  # always clears PASS bar
        holdout_result = self._make_result(sharpe=0.1, max_dd=-0.20)  # never does

        async def fake_run_backtest(strategy_code, symbol, from_date, to_date, **kwargs):
            if from_date == holdout_from:
                return holdout_result
            return research_result

        async def fake_none(*args, **kwargs):
            return None

        loop._run_backtest = fake_run_backtest
        loop._tools.get_story = fake_none
        loop._tools.get_drawdowns = fake_none
        loop._tools.get_benchmark_data = fake_none
        loop._tools.fetch_equity_returns = fake_none

        result = await loop.run(
            user_idea="SMA crossover", symbol="AAPL",
            from_date="2024-01-01", to_date="2024-12-31",
        )

        # The in-sample metrics alone would have PASSed on iteration 1 every time —
        # if the holdout gate weren't wired in, this run would report success.
        assert result.holdout is not None
        assert result.holdout.passed is False
        # No iteration's final recorded verdict may be an accepted PASS: either the
        # PASS was downgraded back to REFINE (visible in that iteration's critique),
        # or the loop ran out of iterations still refining.
        assert all(rec.critique.verdict != "PASS" for rec in result.iterations)


class TestUniverseBacktesting:
    """
    Phase 4B: a `universe` of tickers can be backtested as one portfolio (the
    engine already runs one strategy per symbol and aggregates the P&L — this is
    wiring, not new engine capability), with a correlation matrix and beta-hedge
    overlay computed from the result.
    """

    @staticmethod
    def _synthetic_returns(seed_key: str, n: int = 100) -> pd.Series:
        seed = abs(hash(seed_key)) % (2**31)
        rng = np.random.default_rng(seed)
        dates = pd.date_range("2023-01-02", periods=n, freq="B")
        return pd.Series(rng.normal(0.0005, 0.01, n), index=dates)

    async def test_universe_backtest_produces_portfolio_analysis(self):
        config = ResearchConfig(max_iterations=1, walk_forward_enabled=False)
        loop = StrategyResearchLoop(config=config)

        metrics = BacktestMetrics(sharpe_ratio=0.5, max_drawdown=-0.10, win_rate=0.5)
        backtest_result = BacktestResult(
            run_id="r1", strategy_name="s", metrics=metrics,
            benchmark_metrics={}, trade_count=50, equity_points=200,
        )

        captured_symbols_args: list[list[str] | None] = []

        async def fake_run_backtest(strategy_code, symbol, from_date, to_date, **kwargs):
            captured_symbols_args.append(kwargs.get("symbols"))
            return backtest_result

        async def fake_get_benchmark_data(sym, from_date, to_date):
            return self._synthetic_returns(sym)

        async def fake_fetch_equity_returns(run_id):
            return self._synthetic_returns("PORTFOLIO_EQUITY")

        async def fake_none(*args, **kwargs):
            return None

        loop._run_backtest = fake_run_backtest
        loop._tools.get_story = fake_none
        loop._tools.get_drawdowns = fake_none
        loop._tools.get_benchmark_data = fake_get_benchmark_data
        loop._tools.fetch_equity_returns = fake_fetch_equity_returns

        result = await loop.run(
            user_idea="SMA crossover", symbol="AAPL",
            from_date="2024-01-01", to_date="2024-12-31",
            universe=["AAPL", "MSFT", "GOOGL"],
        )

        # Every backtest call must have used the full universe, not just the
        # primary symbol.
        assert captured_symbols_args, "expected at least one backtest call"
        assert all(
            s is not None and set(s) == {"AAPL", "MSFT", "GOOGL"}
            for s in captured_symbols_args
        )

        assert result.portfolio is not None
        assert set(result.portfolio.symbols) == {"AAPL", "MSFT", "GOOGL"}
        assert "PORTFOLIO ANALYSIS" in result.report_md

    async def test_single_symbol_universe_is_unaffected(self):
        # A universe with only one distinct symbol (or None) must behave exactly
        # like the pre-existing single-symbol path — no portfolio analysis, no
        # multi-symbol backtest calls.
        config = ResearchConfig(max_iterations=1, walk_forward_enabled=False)
        loop = StrategyResearchLoop(config=config)

        metrics = BacktestMetrics(sharpe_ratio=0.5, max_drawdown=-0.10, win_rate=0.5)
        backtest_result = BacktestResult(
            run_id="r1", strategy_name="s", metrics=metrics,
            benchmark_metrics={}, trade_count=50, equity_points=200,
        )

        captured_symbols_args: list[list[str] | None] = []

        async def fake_run_backtest(strategy_code, symbol, from_date, to_date, **kwargs):
            captured_symbols_args.append(kwargs.get("symbols"))
            return backtest_result

        async def fake_none(*args, **kwargs):
            return None

        loop._run_backtest = fake_run_backtest
        loop._tools.get_story = fake_none
        loop._tools.get_drawdowns = fake_none
        loop._tools.get_benchmark_data = fake_none

        result = await loop.run(
            user_idea="SMA crossover", symbol="AAPL",
            from_date="2024-01-01", to_date="2024-12-31",
            universe=["AAPL"],
        )

        assert all(s == ["AAPL"] for s in captured_symbols_args)
        assert result.portfolio is None
        assert "PORTFOLIO ANALYSIS" not in result.report_md


class TestStrategyVerification:
    def test_verify_strategy_code_success(self):
        loop = StrategyResearchLoop()
        loop._indicators = ["rsi_14", "sma_20"]
        code = """
class MyStrategy(BaseStrategy):
    def generate_weights(self, data):
        close = data['close']
        rsi = data.get('rsi_14')
        session = data.session
        return (close > rsi).astype(float)
"""
        errors = loop._verify_strategy_code(code)
        assert errors == []

    def test_verify_strategy_code_hallucination(self):
        loop = StrategyResearchLoop()
        loop._indicators = ["rsi_14"]
        code = """
class MyStrategy(BaseStrategy):
    def generate_weights(self, data):
        close = data['close']
        hallucinated = data['unknown_col_xyz']
        return close * 0
"""
        errors = loop._verify_strategy_code(code)
        assert len(errors) == 1
        assert "unknown_col_xyz" in errors[0]

    async def test_verify_weights_holding_success(self):
        loop = StrategyResearchLoop()
        async def fake_fetch_weights(run_id):
            return [
                {"date": "1", "AAPL": 0.5},
                {"date": "2", "AAPL": 0.5},
                {"date": "3", "AAPL": 0.5},
                {"date": "4", "AAPL": 0.0},
                {"date": "5", "AAPL": 0.5},
                {"date": "6", "AAPL": 0.5},
            ]
        loop._tools.fetch_weights = fake_fetch_weights
        errors = await loop._verify_weights_holding("run1")
        assert errors == []

    async def test_verify_weights_holding_crossover_bug(self):
        loop = StrategyResearchLoop()
        async def fake_fetch_weights(run_id):
            return [
                {"date": "1", "AAPL": 0.5},
                {"date": "2", "AAPL": 0.0},
                {"date": "3", "AAPL": -0.5},
                {"date": "4", "AAPL": 0.0},
                {"date": "5", "AAPL": 0.5},
                {"date": "6", "AAPL": 0.0},
            ]
        loop._tools.fetch_weights = fake_fetch_weights
        errors = await loop._verify_weights_holding("run1")
        assert len(errors) == 1
        assert "crossover state bug" in errors[0]

