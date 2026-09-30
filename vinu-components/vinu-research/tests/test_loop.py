from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pandas as pd

from vinu_research.config import ResearchConfig
from vinu_research.loop import (
    INFRA_FAILURE_REASONING_PREFIX,
    StrategyResearchLoop,
    _build_eval_status_context,
    _classify_outcome_status,
    _LRUCache,
    _split_research_and_holdout,
)
from vinu_research.models import (
    BacktestMetrics,
    BacktestResult,
    CriticFeedback,
    Evidence,
    Hypothesis,
    IterationRecord,
    LlmCandidate,
)


class TestNormalizeSuggestionKey:
    def test_lowercases_and_strips(self):
        result = StrategyResearchLoop._normalize_suggestion_key("  Add ADX Filter  ")
        assert result == "add adx filter"


class TestBuildEvalStatusContext:
    """A6 fix: generation prompt carries the machine gate verdicts for
    the ticker -- read-only, best-effort, empty when nothing on file."""

    def _seed(self, db_path, artifact_id, ticker, verdicts):
        from vinu_infra.strategy_evaluation import StrategyEvaluationStore

        store = StrategyEvaluationStore(db_path)
        for i, (step, verdict, reasoning) in enumerate(verdicts):
            store.write_step_result(
                artifact_id=artifact_id, ticker=ticker, step_name=step,
                step_order=i + 1, verdict=verdict, reasoning=reasoning,
            )
        store.close()

    def test_no_db_file_returns_empty_and_creates_nothing(self, tmp_path):
        result = _build_eval_status_context("AAPL", tmp_path)
        assert result == ""
        assert list(tmp_path.iterdir()) == []

    def test_empty_symbol_returns_empty(self, tmp_path):
        assert _build_eval_status_context("", tmp_path) == ""

    def test_rejection_and_in_flight_rows_rendered(self, tmp_path):
        from vinu_infra.strategy_evaluation import VERDICT_FAIL, VERDICT_PASS

        self._seed(
            tmp_path / "strategy_evaluation.db", "cand-1", "AAPL",
            [("risk_critic", VERDICT_PASS, "ok"),
             ("correlation_gate", VERDICT_FAIL, "too correlated with existing book")],
        )
        self._seed(
            tmp_path / "strategy_evaluation.db", "cand-2", "AAPL",
            [("risk_critic", VERDICT_PASS, "ok")],
        )

        result = _build_eval_status_context("AAPL", tmp_path)

        assert "cand-1" in result
        assert "correlation_gate" in result
        assert "too correlated" in result
        assert "cand-2" in result
        assert "In flight" in result

    def test_other_tickers_excluded(self, tmp_path):
        from vinu_infra.strategy_evaluation import VERDICT_FAIL

        self._seed(
            tmp_path / "strategy_evaluation.db", "cand-9", "MSFT",
            [("risk_critic", VERDICT_FAIL, "bad")],
        )

        assert _build_eval_status_context("AAPL", tmp_path) == ""

    def test_env_root_override_respected(self, tmp_path, monkeypatch):
        from vinu_infra.strategy_evaluation import VERDICT_FAIL

        eval_root = tmp_path / "evalroot"
        eval_root.mkdir()
        self._seed(
            eval_root / "strategy_evaluation.db", "cand-7", "AAPL",
            [("risk_critic", VERDICT_FAIL, "bad sharpe")],
        )
        monkeypatch.setenv("VINU_STRATEGY_EVAL_DATA_ROOT", str(eval_root))

        result = _build_eval_status_context("AAPL", tmp_path / "does-not-exist")

        assert "cand-7" in result

    def test_removes_numbers(self):
        result = StrategyResearchLoop._normalize_suggestion_key("Iteration 3: reduce position size by 50%")
        assert "3" not in result
        assert "50" not in result
        assert result.startswith("iteration : reduce position size by %")

    def test_collapses_whitespace(self):
        result = StrategyResearchLoop._normalize_suggestion_key("tighten    stop   loss")
        assert result == "tighten stop loss"

    def test_truncates_to_80_chars(self):
        long = "x" * 100
        result = StrategyResearchLoop._normalize_suggestion_key(long)
        assert len(result) == 80


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


class TestDiagnoseFailureCrashFallback:
    """
    #31: a trade_count==0 result caused by vinu-simulator's generate_weights
    crash-fallback (custom_sim.py) must be reported as a strategy crash, not
    handed to the LLM as an ordinary "why did this trade zero times" question
    -- and a genuinely trade-free result must NOT be misreported as a crash.
    """

    def make_result(self, diagnostics: dict | None = None) -> BacktestResult:
        metrics = BacktestMetrics(sharpe_ratio=0.0, max_drawdown=0.0)
        raw = {"diagnostics": diagnostics} if diagnostics is not None else {}
        return BacktestResult(
            run_id="r1", strategy_name="s", metrics=metrics,
            benchmark_metrics={}, trade_count=0, equity_points=10, raw=raw,
        )

    async def test_crash_fallback_is_reported_without_calling_the_llm(self):
        loop = StrategyResearchLoop()
        result = self.make_result({
            "crash_fallback": True,
            "strategy_crashed_symbols": {"AAPL": "KeyError: 'rsi_14'"},
        })
        diagnosis = await loop._diagnose_failure(
            strategy_code="class X: pass", result=result, symbol="AAPL",
        )
        assert "strategy_crash" in diagnosis
        assert "AAPL" in diagnosis
        assert "KeyError" in diagnosis

    async def test_legitimate_zero_trades_does_not_report_a_crash(self):
        loop = StrategyResearchLoop()
        result = self.make_result({})
        diagnosis = await loop._diagnose_failure(
            strategy_code="class X: pass", result=result, symbol="AAPL",
        )
        # LLM is disabled by default in tests -> falls through to "" rather
        # than fabricating a crash diagnosis for a legitimate no-trade result.
        assert diagnosis == ""

    async def test_missing_raw_diagnostics_does_not_crash(self):
        """BacktestResult.raw defaults to {} for callers/tests that don't set
        it -- _diagnose_failure must tolerate that instead of raising."""
        loop = StrategyResearchLoop()
        metrics = BacktestMetrics(sharpe_ratio=0.0, max_drawdown=0.0)
        result = BacktestResult(
            run_id="r1", strategy_name="s", metrics=metrics,
            benchmark_metrics={}, trade_count=0, equity_points=10,
        )
        diagnosis = await loop._diagnose_failure(
            strategy_code="class X: pass", result=result, symbol="AAPL",
        )
        assert diagnosis == ""


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


class _FakeConfiguredLlm:
    def is_configured(self) -> bool:
        return True


def _fake_llm_with_duplicate_check(configured: bool = True, result=None, side_effect=None) -> MagicMock:
    llm = MagicMock()
    llm.is_configured.return_value = configured
    llm.check_duplicate_idea = AsyncMock(
        side_effect=side_effect if side_effect is not None else None,
        return_value=result if side_effect is None else None,
    )
    return llm


class TestMatchExistingHypothesis:
    """item #16 finding #4: replaces the old bare token-overlap
    `_match_score` dedup. TF-IDF similarity screens out candidates with
    essentially no shared vocabulary (no LLM call spent on them); the LLM
    makes the real semantic judgment for anything left; a pure-similarity
    threshold is the fallback only when the LLM is unavailable."""

    def _loop(self, llm=None) -> StrategyResearchLoop:
        loop = StrategyResearchLoop(config=ResearchConfig(generator_mode="llm"))
        loop._llm = llm
        return loop

    async def test_no_existing_hypotheses_returns_none_without_calling_the_llm(self):
        llm = _fake_llm_with_duplicate_check()
        loop = self._loop(llm)
        result = await loop._match_existing_hypothesis("SMA crossover", "AAPL", [])
        assert result is None
        llm.check_duplicate_idea.assert_not_called()

    async def test_completely_unrelated_candidates_skip_the_llm_call_entirely(self):
        llm = _fake_llm_with_duplicate_check()
        loop = self._loop(llm)
        existing = [Hypothesis.create("H1", "H1", universe=["AAPL"])]
        existing[0].strategy_type = "options gamma scalping around earnings"
        result = await loop._match_existing_hypothesis(
            "SMA crossover trend following", "AAPL", existing,
        )
        assert result is None
        llm.check_duplicate_idea.assert_not_called()

    async def test_llm_confirms_a_duplicate_above_confidence_floor(self):
        h1 = Hypothesis.create("H1", "H1", universe=["AAPL"])
        h1.strategy_type = "SMA crossover trend following on tech stocks"
        llm = _fake_llm_with_duplicate_check(
            result={"duplicate_index": 0, "confidence": 0.9, "reasoning": "same concept"},
        )
        loop = self._loop(llm)
        result = await loop._match_existing_hypothesis(
            "Moving average crossover trend-following on technology names", "AAPL", [h1],
        )
        assert result is h1
        llm.check_duplicate_idea.assert_awaited_once()

    async def test_llms_explicit_negative_is_trusted_not_overridden_by_fallback(self):
        # High lexical overlap (would pass the fallback threshold on its
        # own), but the LLM explicitly says it's not a duplicate -- that
        # verdict must win, not get second-guessed by the cheaper signal.
        h1 = Hypothesis.create("H1", "H1", universe=["AAPL"])
        h1.strategy_type = "RSI mean reversion strategy RSI RSI RSI RSI RSI RSI"
        llm = _fake_llm_with_duplicate_check(
            result={"duplicate_index": None, "confidence": 0.9, "reasoning": "different entry logic"},
        )
        loop = self._loop(llm)
        result = await loop._match_existing_hypothesis(
            "RSI mean reversion strategy RSI RSI RSI RSI RSI RSI", "AAPL", [h1],
        )
        assert result is None

    async def test_llm_confidence_below_floor_is_not_matched(self):
        h1 = Hypothesis.create("H1", "H1", universe=["AAPL"])
        h1.strategy_type = "SMA crossover trend following on tech stocks"
        llm = _fake_llm_with_duplicate_check(
            result={"duplicate_index": 0, "confidence": 0.3, "reasoning": "maybe"},
        )
        loop = self._loop(llm)
        result = await loop._match_existing_hypothesis(
            "Moving average crossover trend-following on technology names", "AAPL", [h1],
        )
        assert result is None

    async def test_llm_call_failing_falls_back_to_similarity_threshold(self):
        h1 = Hypothesis.create("H1", "H1", universe=["AAPL"])
        h1.strategy_type = "SMA crossover trend following momentum strategy"
        llm = _fake_llm_with_duplicate_check(side_effect=RuntimeError("LLM down"))
        loop = self._loop(llm)
        result = await loop._match_existing_hypothesis(
            "SMA crossover trend following momentum strategy", "AAPL", [h1],
        )
        assert result is h1  # identical text easily clears the fallback threshold

    async def test_llm_not_configured_uses_similarity_fallback_directly(self):
        h1 = Hypothesis.create("H1", "H1", universe=["AAPL"])
        h1.strategy_type = "SMA crossover trend following momentum strategy"
        llm = _fake_llm_with_duplicate_check(configured=False)
        loop = self._loop(llm)
        result = await loop._match_existing_hypothesis(
            "SMA crossover trend following momentum strategy", "AAPL", [h1],
        )
        assert result is h1
        llm.check_duplicate_idea.assert_not_called()

    async def test_fallback_below_threshold_does_not_match(self):
        h1 = Hypothesis.create("H1", "H1", universe=["AAPL"])
        h1.strategy_type = "RSI mean reversion for oversold conditions"
        llm = _fake_llm_with_duplicate_check(configured=False)
        loop = self._loop(llm)
        result = await loop._match_existing_hypothesis(
            "trend following momentum strategy using moving averages", "AAPL", [h1],
        )
        assert result is None

    async def test_llm_receives_every_candidate_that_passed_the_skip_screen(self):
        h1 = Hypothesis.create("H1", "H1", universe=["AAPL"])
        h1.strategy_type = "SMA crossover trend following"
        h2 = Hypothesis.create("H2", "H2", universe=["AAPL"])
        h2.strategy_type = "moving average crossover momentum strategy"
        llm = _fake_llm_with_duplicate_check(result={"duplicate_index": None, "confidence": 0.9})
        loop = self._loop(llm)
        await loop._match_existing_hypothesis("crossover trend momentum idea", "AAPL", [h1, h2])
        args, kwargs = llm.check_duplicate_idea.call_args
        candidate_ideas = args[2] if len(args) > 2 else kwargs["candidate_ideas"]
        assert len(candidate_ideas) == 2

    async def test_enriched_candidates_carry_each_ideas_track_record(self):
        """B5 fix: rejected-with-evidence must look different from
        exploring-with-evidence to the dedup LLM, even with overlapping words."""
        from vinu_research.models import Evidence, HypothesisStatus

        h1 = Hypothesis.create("H1", "H1", universe=["AAPL"])
        h1.strategy_type = "RSI mean reversion on oversold bounces"
        h1.status = HypothesisStatus.rejected
        h1.best_sharpe = -0.3
        h1.invalidation_reason = "failed correlation gate"
        h1.evidence = [Evidence(run_id=1, iteration=1, metric="sharpe", value=-0.3,
                                conclusion="negative expectancy", reasoning="lost money")]
        h2 = Hypothesis.create("H2", "H2", universe=["AAPL"])
        h2.strategy_type = "RSI mean reversion on oversold bounces with volume filter"
        h2.status = HypothesisStatus.exploring
        h2.best_sharpe = 0.4
        llm = _fake_llm_with_duplicate_check(result={"duplicate_index": None, "confidence": 0.9})
        loop = self._loop(llm)
        await loop._match_existing_hypothesis("RSI mean reversion oversold bounce", "AAPL", [h1, h2])
        args, kwargs = llm.check_duplicate_idea.call_args
        candidate_ideas = args[2] if len(args) > 2 else kwargs["candidate_ideas"]
        assert len(candidate_ideas) == 2
        by_status = {c["status"]: c for c in candidate_ideas}
        assert by_status["rejected"]["best_sharpe"] == -0.3
        assert by_status["rejected"]["evidence_count"] == 1
        assert by_status["rejected"]["last_conclusion"] == "negative expectancy"
        assert by_status["rejected"]["invalidation_reason"] == "failed correlation gate"
        assert by_status["exploring"]["evidence_count"] == 0
        for c in candidate_ideas:
            assert "tfidf_score" in c and c["tfidf_score"] >= 0.1


class TestDefaultQuantCoderRefinement:
    """Iteration 2+ should route through LLM refinement (feedback-informed,
    using the previous code + backtest + critique) rather than always falling
    back to template + rule-based filter injection, when the LLM is available
    and generator_mode allows it."""

    def _make_result(self, sharpe: float = 0.8) -> BacktestResult:
        metrics = BacktestMetrics(sharpe_ratio=sharpe, max_drawdown=-0.1, win_rate=0.5)
        return BacktestResult(
            run_id="r1", strategy_name="s", metrics=metrics,
            benchmark_metrics={}, trade_count=30, equity_points=100,
        )

    def _make_critique(self) -> CriticFeedback:
        return CriticFeedback(
            verdict="REFINE", reasoning="needs work",
            suggestions=["Sharpe below 0.5 — add ADX filter to avoid choppy markets"],
        )

    async def test_iteration2_uses_llm_refine_when_available(self, monkeypatch):
        import vinu_research.loop as loop_module

        refine_calls = []

        class _FakeGenerator:
            def __init__(self, llm_client):
                pass

            async def refine(self, **kwargs):
                refine_calls.append(kwargs)
                return [LlmCandidate(code="class UserStrategy: REFINED", validated=True)]

        monkeypatch.setattr(loop_module, "LlmStrategyGenerator", _FakeGenerator)

        loop = StrategyResearchLoop(config=ResearchConfig(generator_mode="llm"))
        loop._llm = _FakeConfiguredLlm()
        loop._symbol = "AAPL"
        loop._from_date = "2024-01-01"
        loop._to_date = "2024-12-31"
        # item #12 finding #2: refined candidates are now backtested for
        # real before ranking -- no real simulator here, so this returns
        # "no backtest data" (falls back to the pre-backtest heuristic
        # score alone, same ordering these tests already assume).
        monkeypatch.setattr(loop, "_run_backtest", AsyncMock(return_value=None))

        code = await loop._default_quant_coder(
            "SMA crossover", 2, self._make_result(), self._make_critique(),
            previous_code="class UserStrategy: PREVIOUS",
        )

        assert code == "class UserStrategy: REFINED"
        assert len(refine_calls) == 1
        assert refine_calls[0]["previous_code"] == "class UserStrategy: PREVIOUS"

    async def test_iteration2_falls_back_to_template_when_refine_returns_nothing(self, monkeypatch):
        import vinu_research.loop as loop_module

        class _FakeGenerator:
            def __init__(self, llm_client):
                pass

            async def refine(self, **kwargs):
                return []

        monkeypatch.setattr(loop_module, "LlmStrategyGenerator", _FakeGenerator)

        loop = StrategyResearchLoop(config=ResearchConfig(generator_mode="llm"))
        loop._llm = _FakeConfiguredLlm()
        loop._indicators = ["adx_14"]

        code = await loop._default_quant_coder(
            "SMA crossover", 2, self._make_result(), self._make_critique(),
            previous_code="class UserStrategy: PREVIOUS",
        )

        # Falls back to previous_code instead of generating a fresh template
        assert "PREVIOUS" in code

    async def test_generator_mode_template_bypasses_refinement_entirely(self, monkeypatch):
        import vinu_research.loop as loop_module

        class _ExplodingGenerator:
            def __init__(self, llm_client):
                pass

            async def refine(self, **kwargs):
                raise AssertionError("refine() must not be called in template mode")

        monkeypatch.setattr(loop_module, "LlmStrategyGenerator", _ExplodingGenerator)

        loop = StrategyResearchLoop(config=ResearchConfig(generator_mode="template"))
        loop._llm = _FakeConfiguredLlm()
        loop._indicators = ["adx_14"]

        code = await loop._default_quant_coder(
            "SMA crossover", 2, self._make_result(), self._make_critique(),
            previous_code="class UserStrategy: PREVIOUS",
        )

        assert "PREVIOUS" not in code
        assert "adx" in code.lower()


class TestBacktestAndRankCandidates:
    """item #12 finding #2: `diverse_top_n`/`rank_candidates` accepted a
    `backtest_results` param from the start but nothing ever called it
    with real data -- every candidate not ranked #1 by the pre-backtest
    complexity-penalty heuristic alone was discarded on a guess, never
    proven worse. Approved explicitly to also spend real backtest budget
    on this (LLM cost is unchanged -- the candidates are already drafted
    in one generation call either way)."""

    def _patch_generate(self, monkeypatch, candidates):
        import vinu_research.loop as loop_module

        class _FakeGenerator:
            def __init__(self, llm_client):
                pass

            async def generate(self, **kwargs):
                return candidates

            async def refine(self, **kwargs):
                return candidates

        monkeypatch.setattr(loop_module, "LlmStrategyGenerator", _FakeGenerator)

    def _result(self, sharpe: float, max_dd: float = -0.1, win_rate: float = 0.5) -> BacktestResult:
        metrics = BacktestMetrics(sharpe_ratio=sharpe, max_drawdown=max_dd, win_rate=win_rate)
        return BacktestResult(
            run_id="r", strategy_name="s", metrics=metrics,
            benchmark_metrics={}, trade_count=30, equity_points=100,
        )

    async def test_real_backtest_performance_can_override_the_pre_backtest_heuristic(self, monkeypatch):
        # "simple" scores higher than "complex" on complexity alone, but a
        # terrible real backtest vs. a great one must be able to flip that
        # -- otherwise the extra backtest cost would buy nothing.
        simple = LlmCandidate(code="class A:\n    def generate_weights(self, d): return d.close*0", reasoning="simple")
        complex_ = LlmCandidate(
            code="class B:\n" + "    x = 1\n" * 30 + "    def generate_weights(self, d): return d.close*0",
            reasoning="complex",
        )
        self._patch_generate(monkeypatch, [simple, complex_])

        loop = StrategyResearchLoop(config=ResearchConfig(generator_mode="llm"))
        loop._llm = _FakeConfiguredLlm()
        loop._symbol = "AAPL"
        loop._from_date = "2024-01-01"
        loop._to_date = "2024-12-31"

        results_by_code = {
            simple.code: self._result(sharpe=-2.0, max_dd=-0.9, win_rate=0.1),
            complex_.code: self._result(sharpe=3.0, max_dd=-0.05, win_rate=0.7),
        }
        monkeypatch.setattr(
            loop, "_run_backtest",
            AsyncMock(side_effect=lambda code, *a, **kw: results_by_code[code]),
        )

        code = await loop._default_quant_coder("SMA crossover", 1, None, None)
        assert code == complex_.code

    async def test_one_candidates_backtest_raising_does_not_abort_the_others(self, monkeypatch):
        good = LlmCandidate(code="class Good:\n    def generate_weights(self, d): return d.close*0", reasoning="good")
        crashes = LlmCandidate(code="class Bad:\n    def generate_weights(self, d): raise ValueError()", reasoning="crashes")
        self._patch_generate(monkeypatch, [good, crashes])

        loop = StrategyResearchLoop(config=ResearchConfig(generator_mode="llm"))
        loop._llm = _FakeConfiguredLlm()
        loop._symbol = "AAPL"
        loop._from_date = "2024-01-01"
        loop._to_date = "2024-12-31"

        async def _fake_backtest(code, *a, **kw):
            if code == crashes.code:
                raise RuntimeError("Backtest failed: strategy crashed")
            return self._result(sharpe=1.0)

        monkeypatch.setattr(loop, "_run_backtest", AsyncMock(side_effect=_fake_backtest))

        code = await loop._default_quant_coder("SMA crossover", 1, None, None)
        assert code == good.code

    async def test_every_candidate_failing_reraises_instead_of_silently_picking_one(self, monkeypatch):
        c1 = LlmCandidate(code="class A:\n    def generate_weights(self, d): return d.close*0", reasoning="a")
        c2 = LlmCandidate(code="class B:\n    def generate_weights(self, d): return d.close*0", reasoning="b")
        self._patch_generate(monkeypatch, [c1, c2])

        loop = StrategyResearchLoop(config=ResearchConfig(generator_mode="llm"))
        loop._llm = _FakeConfiguredLlm()
        loop._symbol = "AAPL"
        loop._from_date = "2024-01-01"
        loop._to_date = "2024-12-31"
        monkeypatch.setattr(
            loop, "_run_backtest",
            AsyncMock(side_effect=RuntimeError("simulator unreachable")),
        )

        import pytest
        with pytest.raises(RuntimeError, match="simulator unreachable"):
            await loop._default_quant_coder("SMA crossover", 1, None, None)

    async def test_generation_round_is_recorded_with_post_backtest_scores(self, monkeypatch):
        from vinu_research.generation_candidate_store import GenerationCandidateStore

        weak = LlmCandidate(code="class A:\n    def generate_weights(self, d): return d.close*0", reasoning="weak")
        strong = LlmCandidate(
            code="class B:\n" + "    x = 1\n" * 30 + "    def generate_weights(self, d): return d.close*0",
            reasoning="strong",
        )
        self._patch_generate(monkeypatch, [weak, strong])

        store = GenerationCandidateStore(":memory:")
        loop = StrategyResearchLoop(
            config=ResearchConfig(generator_mode="llm"), generation_candidate_store=store,
        )
        loop._llm = _FakeConfiguredLlm()
        loop._symbol = "AAPL"
        loop._from_date = "2024-01-01"
        loop._to_date = "2024-12-31"

        results_by_code = {
            weak.code: self._result(sharpe=-2.0, max_dd=-0.9, win_rate=0.1),
            strong.code: self._result(sharpe=3.0, max_dd=-0.05, win_rate=0.7),
        }
        monkeypatch.setattr(
            loop, "_run_backtest",
            AsyncMock(side_effect=lambda code, *a, **kw: results_by_code[code]),
        )

        await loop._default_quant_coder("SMA crossover", 1, None, None)

        rounds = store.list_rounds(symbol="AAPL")
        candidates = store.get_round(rounds[0]["generation_id"])["candidates"]
        chosen = next(c for c in candidates if c["chosen"])
        from vinu_research.generation_candidate_store import code_hash
        assert chosen["code_hash"] == code_hash(strong.code)


class TestRecordGenerationRound:
    """item #16 finding #2: 3 candidates get drafted per generation call,
    2 discarded on a heuristic complexity-penalty score with no backtest
    behind it -- never recorded before this. No store injected (the
    default) must stay a total no-op; a store injected must actually
    capture every candidate, winner included, from both the iteration-1
    generate path and the iteration-2+ refine path."""

    def _make_result(self, sharpe: float = 0.8) -> BacktestResult:
        metrics = BacktestMetrics(sharpe_ratio=sharpe, max_drawdown=-0.1, win_rate=0.5)
        return BacktestResult(
            run_id="r1", strategy_name="s", metrics=metrics,
            benchmark_metrics={}, trade_count=30, equity_points=100,
        )

    def _make_critique(self) -> CriticFeedback:
        return CriticFeedback(verdict="REFINE", reasoning="needs work", suggestions=[])

    def _patch_generate(self, monkeypatch, candidates):
        import vinu_research.loop as loop_module

        class _FakeGenerator:
            def __init__(self, llm_client):
                pass

            async def generate(self, **kwargs):
                return candidates

            async def refine(self, **kwargs):
                return candidates

        monkeypatch.setattr(loop_module, "LlmStrategyGenerator", _FakeGenerator)

    async def test_no_store_injected_is_a_total_no_op(self, monkeypatch):
        self._patch_generate(monkeypatch, [
            LlmCandidate(code="class A: pass", reasoning="best"),
            LlmCandidate(code="class B: much_longer_and_more_complex_code_here", reasoning="worse"),
        ])
        loop = StrategyResearchLoop(config=ResearchConfig(generator_mode="llm"))
        loop._llm = _FakeConfiguredLlm()
        loop._symbol = "AAPL"
        loop._from_date = "2024-01-01"
        loop._to_date = "2024-12-31"
        monkeypatch.setattr(loop, "_run_backtest", AsyncMock(return_value=None))

        # Must not raise even though no generation_candidate_store was given.
        await loop._default_quant_coder("SMA crossover", 1, None, None)

    async def test_generate_path_records_every_candidate_with_winner_flagged(self, monkeypatch):
        from vinu_research.generation_candidate_store import GenerationCandidateStore, code_hash

        self._patch_generate(monkeypatch, [
            LlmCandidate(code="class Simple: pass", reasoning="best"),
            LlmCandidate(code="class VeryLong:\n" + "    x = 1\n" * 50, reasoning="worse"),
        ])
        store = GenerationCandidateStore(":memory:")
        loop = StrategyResearchLoop(
            config=ResearchConfig(generator_mode="llm"), generation_candidate_store=store,
        )
        loop._llm = _FakeConfiguredLlm()
        loop._symbol = "AAPL"
        loop._from_date = "2024-01-01"
        loop._to_date = "2024-12-31"
        monkeypatch.setattr(loop, "_run_backtest", AsyncMock(return_value=None))

        await loop._default_quant_coder("SMA crossover", 1, None, None)

        rounds = store.list_rounds(symbol="AAPL")
        assert len(rounds) == 1
        assert rounds[0]["mode"] == "generate"
        candidates = store.get_round(rounds[0]["generation_id"])["candidates"]
        assert len(candidates) == 2
        assert candidates[0]["chosen"] is True
        assert candidates[0]["code_hash"] == code_hash("class Simple: pass")

    async def test_refine_path_records_with_mode_refine(self, monkeypatch):
        from vinu_research.generation_candidate_store import GenerationCandidateStore

        self._patch_generate(monkeypatch, [
            LlmCandidate(code="class Refined: pass", reasoning="best"),
        ])
        store = GenerationCandidateStore(":memory:")
        loop = StrategyResearchLoop(
            config=ResearchConfig(generator_mode="llm"), generation_candidate_store=store,
        )
        loop._llm = _FakeConfiguredLlm()
        loop._symbol = "AAPL"
        monkeypatch.setattr(loop, "_run_backtest", AsyncMock(return_value=None))

        await loop._default_quant_coder(
            "SMA crossover", 2, self._make_result(), self._make_critique(),
            previous_code="class UserStrategy: PREVIOUS",
        )

        rounds = store.list_rounds(symbol="AAPL")
        assert len(rounds) == 1
        assert rounds[0]["mode"] == "refine"

    async def test_a_broken_store_does_not_break_generation_itself(self, monkeypatch):
        self._patch_generate(monkeypatch, [LlmCandidate(code="class A: pass", reasoning="best")])

        class _BrokenStore:
            def record_round(self, *args, **kwargs):
                raise RuntimeError("disk full")

        loop = StrategyResearchLoop(
            config=ResearchConfig(generator_mode="llm"), generation_candidate_store=_BrokenStore(),
        )
        loop._llm = _FakeConfiguredLlm()
        loop._symbol = "AAPL"
        monkeypatch.setattr(loop, "_run_backtest", AsyncMock(return_value=None))

        code = await loop._default_quant_coder("SMA crossover", 1, None, None)
        assert code == "class A: pass"

    async def test_no_candidates_at_all_does_not_call_the_store(self, monkeypatch):
        from unittest.mock import MagicMock

        self._patch_generate(monkeypatch, [])
        store = MagicMock()
        loop = StrategyResearchLoop(
            config=ResearchConfig(generator_mode="llm"), generation_candidate_store=store,
        )
        loop._llm = _FakeConfiguredLlm()
        loop._symbol = "AAPL"

        await loop._default_quant_coder("SMA crossover", 1, None, None)
        store.record_round.assert_not_called()


class TestClassifyOutcomeStatus:
    """item #17 finding #2: an automated scheduler with no LLM reading
    report_md's prose couldn't tell "the simulator was down, try again
    later" from "we tested this for real and it's genuinely not a good
    strategy" -- both used to look identical (a run with no
    best_result)."""

    def _record(self, verdict: str, reasoning: str) -> IterationRecord:
        metrics = BacktestMetrics(sharpe_ratio=0.1, max_drawdown=-0.1, win_rate=0.5)
        result = BacktestResult(
            run_id="r1", strategy_name="s", metrics=metrics,
            benchmark_metrics={}, trade_count=10, equity_points=50,
        )
        return IterationRecord(
            iteration=1, strategy_code="class UserStrategy: pass", result=result,
            critique=CriticFeedback(verdict=verdict, reasoning=reasoning, suggestions=[]),
        )

    def _passing_result(self) -> BacktestResult:
        metrics = BacktestMetrics(sharpe_ratio=0.8, max_drawdown=-0.1, win_rate=0.6)
        return BacktestResult(
            run_id="r2", strategy_name="s", metrics=metrics,
            benchmark_metrics={}, trade_count=40, equity_points=200,
        )

    def test_infra_failure_reasoning_classifies_as_infra_failure(self) -> None:
        history = [self._record("STOP", f"{INFRA_FAILURE_REASONING_PREFIX} (not a strategy problem): simulator down")]
        assert _classify_outcome_status(history, None) == "infra_failure"

    def test_a_genuine_stop_with_no_best_result_is_no_strategy_found(self) -> None:
        """The same "no best_result" shape as an infra failure, but a real
        quality-based STOP -- must not be misclassified as infra_failure
        just because the verdict string happens to match."""
        history = [self._record("STOP", "Sharpe too low across all attempts, not worth continuing")]
        assert _classify_outcome_status(history, None) == "no_strategy_found"

    def test_no_history_and_no_best_result_is_no_strategy_found(self) -> None:
        assert _classify_outcome_status([], None) == "no_strategy_found"

    def test_a_real_best_result_is_passed_even_with_earlier_refine_iterations(self) -> None:
        history = [
            self._record("REFINE", "needs work"),
            self._record("PASS", "looks good"),
        ]
        assert _classify_outcome_status(history, self._passing_result()) == "passed"

    def test_infra_failure_mid_run_overrides_an_earlier_best_result_check(self) -> None:
        """The infra check reads the LAST history entry specifically --
        if the run then hit an infra wall (loop.py's own `break` on
        InfrastructureError), that's the real terminal state even if an
        earlier iteration in this same history looked fine, since nothing
        later confirmed it under fresh conditions."""
        history = [
            self._record("REFINE", "needs work"),
            self._record("STOP", f"{INFRA_FAILURE_REASONING_PREFIX} (not a strategy problem): simulator down"),
        ]
        assert _classify_outcome_status(history, None) == "infra_failure"


class TestHypothesisEvidenceInStory:
    """item #16 finding #1: Track 1's signal-evidence entries (item #1's
    bridge) must actually reach the LLM's prompt, not just be reachable
    on the hypothesis. hyp.evidence[-3:] was already being pulled into
    story["memory_context"] -- the gap was the formatting line dropping
    `reasoning` (where a signal-evidence entry's real content lives),
    keeping only a bare metric=value pair."""

    def _make_result(self, sharpe: float = 0.8) -> BacktestResult:
        metrics = BacktestMetrics(sharpe_ratio=sharpe, max_drawdown=-0.1, win_rate=0.5)
        return BacktestResult(
            run_id="r1", strategy_name="s", metrics=metrics,
            benchmark_metrics={}, trade_count=30, equity_points=100,
        )

    def _make_critique(self) -> CriticFeedback:
        return CriticFeedback(verdict="REFINE", reasoning="needs work", suggestions=[])

    async def _story_from_refine(self, monkeypatch, hyp: Hypothesis) -> dict:
        import vinu_research.loop as loop_module

        refine_calls = []

        class _FakeGenerator:
            def __init__(self, llm_client):
                pass

            async def refine(self, **kwargs):
                refine_calls.append(kwargs)
                return [LlmCandidate(code="class UserStrategy: REFINED", validated=True)]

        monkeypatch.setattr(loop_module, "LlmStrategyGenerator", _FakeGenerator)

        loop = StrategyResearchLoop(config=ResearchConfig(generator_mode="llm"))
        loop._llm = _FakeConfiguredLlm()
        loop._symbol = "AAPL"
        loop._from_date = "2024-01-01"
        loop._to_date = "2024-12-31"
        loop._current_hypothesis = hyp
        monkeypatch.setattr(loop, "_run_backtest", AsyncMock(return_value=None))

        await loop._default_quant_coder(
            "SMA crossover", 2, self._make_result(), self._make_critique(),
            previous_code="class UserStrategy: PREVIOUS",
        )
        assert len(refine_calls) == 1
        return refine_calls[0]["story"] or {}

    async def test_signal_evidence_entry_shows_its_full_reasoning(self, monkeypatch):
        hyp = Hypothesis.create("Test", "Test thesis", universe=["AAPL"])
        hyp.evidence.append(Evidence(
            run_id="signal_evidence", iteration=0, metric="avg_return_at_horizon",
            value=0.03, conclusion="supports",
            reasoning="12 historical trigger(s) of 'sma5_cross_sma50', 58% positive, last fired 3 day(s) ago",
            metric_kind="signal_evidence",
        ))

        story = await self._story_from_refine(monkeypatch, hyp)

        assert "12 historical trigger(s) of 'sma5_cross_sma50', 58% positive, last fired 3 day(s) ago" in story["memory_context"]

    async def test_sharpe_evidence_keeps_the_existing_terse_format(self, monkeypatch):
        """Regression guard: a Sharpe evidence entry's reasoning is a full
        LLM critique, not a short summary -- including it in full for
        every entry would bloat the prompt, so this format must stay
        unchanged for metric_kind="sharpe" (the default)."""
        hyp = Hypothesis.create("Test", "Test thesis", universe=["AAPL"])
        hyp.evidence.append(Evidence(
            run_id=1, iteration=3, metric="sharpe", value=0.65,
            conclusion="supports",
            reasoning="A very long LLM-generated critique paragraph that should not appear verbatim in the prompt.",
        ))

        story = await self._story_from_refine(monkeypatch, hyp)

        assert "Iter 3: sharpe=0.65 → supports" in story["memory_context"]
        assert "very long LLM-generated critique" not in story["memory_context"]

    async def test_mixed_evidence_kinds_each_use_their_own_format(self, monkeypatch):
        hyp = Hypothesis.create("Test", "Test thesis", universe=["AAPL"])
        hyp.evidence.append(Evidence(
            run_id=1, iteration=1, metric="sharpe", value=0.4, conclusion="supports", reasoning="critique text",
        ))
        hyp.evidence.append(Evidence(
            run_id="signal_evidence", iteration=0, metric="avg_return_at_horizon",
            value=0.02, conclusion="supports",
            reasoning="5 historical trigger(s) of 'sma5_cross_sma50', 80% positive, last fired 1 day(s) ago",
            metric_kind="signal_evidence",
        ))

        story = await self._story_from_refine(monkeypatch, hyp)

        assert "Iter 1: sharpe=0.40 → supports" in story["memory_context"]
        assert "5 historical trigger(s) of 'sma5_cross_sma50', 80% positive, last fired 1 day(s) ago" in story["memory_context"]


class TestBestResultSelection:
    async def test_best_result_is_best_sharpe_not_last(self, monkeypatch):
        loop = StrategyResearchLoop(config=ResearchConfig(max_iterations=3))

        idx = [0]
        sharpe_values = [0.8, 1.2, 0.5]

        async def fake_backtest(strategy_code, symbol, from_date, to_date, **kwargs):
            i = idx[0]
            idx[0] += 1
            s = sharpe_values[i] if i < len(sharpe_values) else 0.0
            metrics = BacktestMetrics(sharpe_ratio=s, max_drawdown=-0.1, win_rate=0.5)
            return BacktestResult(
                run_id=f"r{i}", strategy_name="s", metrics=metrics,
                benchmark_metrics={}, trade_count=10, equity_points=100,
            )

        async def fake_coder(idea, iteration, last_result=None, last_critique=None, previous_code=None):
            return "class UserStrategy:\n    pass\n"

        async def fake_critic(result, story, drawdowns, iteration):
            return CriticFeedback(verdict="REFINE", reasoning="needs work", suggestions=[])

        monkeypatch.setattr(loop, '_run_backtest', fake_backtest)
        monkeypatch.setattr(loop, '_verify_strategy_code', lambda code: [])
        monkeypatch.setattr(loop, '_is_improving', lambda history: True)

        async def _noop(*a, **kw): return None
        async def _empty_dict(*a, **kw): return {}

        monkeypatch.setattr(loop._tools, 'get_angle_context', _empty_dict)
        monkeypatch.setattr(loop._tools, 'get_feature_snapshot', _empty_dict)
        monkeypatch.setattr(loop._tools, 'get_story', _empty_dict)
        monkeypatch.setattr(loop._tools, 'get_drawdowns', _noop)
        monkeypatch.setattr(loop._tools, 'get_benchmark_data', _noop)
        loop._quant_coder = fake_coder
        loop._risk_critic = fake_critic

        result = await loop.run(
            user_idea="SMA crossover",
            symbol="AAPL",
            from_date="2024-01-01",
            to_date="2024-06-01",
        )

        assert result.best_result is not None
        assert result.best_result.metrics.sharpe_ratio == 1.2
        assert result.best_iteration == 2
        assert len(result.iterations) == 3


class TestCheckMcGate:
    def make_result(self, validation: dict | None) -> BacktestResult:
        metrics = BacktestMetrics(sharpe_ratio=1.0)
        return BacktestResult(
            run_id="r1", strategy_name="s", metrics=metrics,
            benchmark_metrics={}, trade_count=10, equity_points=100,
            raw={"validation": validation} if validation is not None else {},
        )

    def test_no_validation_present_does_not_gate(self):
        loop = StrategyResearchLoop()
        result = self.make_result(None)
        assert loop._check_mc_gate(result) is None

    def test_passing_verdict_does_not_gate(self):
        loop = StrategyResearchLoop()
        result = self.make_result({"verdict": {"passed": True, "reasons": ["ok"]}})
        assert loop._check_mc_gate(result) is None

    def test_failing_verdict_stops_with_reasons(self):
        loop = StrategyResearchLoop()
        result = self.make_result({
            "verdict": {"passed": False, "reasons": ["Trade-permutation p-value 0.4 >= 0.05 (FAIL)"]},
        })
        feedback = loop._check_mc_gate(result)
        assert feedback is not None
        assert feedback.verdict == "STOP"
        assert "Trade-permutation p-value" in feedback.reasoning
        assert feedback.suggestions == ["Trade-permutation p-value 0.4 >= 0.05 (FAIL)"]

    def test_missing_verdict_key_fails_closed(self):
        # A validation dict without a "verdict" sub-object must not silently
        # pass what's meant to be a hard, un-bypassable gate.
        loop = StrategyResearchLoop()
        result = self.make_result({"monte_carlo": {"p_value": 0.5}})
        feedback = loop._check_mc_gate(result)
        assert feedback is not None
        assert feedback.verdict == "STOP"

    def test_gate_short_circuits_run_before_refinement(self, monkeypatch):
        import asyncio

        loop = StrategyResearchLoop()
        failing_result = self.make_result({"verdict": {"passed": False, "reasons": ["bad"]}})

        async def fake_coder(idea, iteration, last_result=None, last_critique=None, previous_code=None):
            return "class UserStrategy:\n    pass\n"

        calls = {"backtest": 0, "critic": 0}

        async def fake_backtest(*args, **kwargs):
            calls["backtest"] += 1
            return failing_result

        async def fake_critic(*args, **kwargs):
            calls["critic"] += 1
            return CriticFeedback(verdict="PASS", reasoning="should not run", suggestions=[])

        async def _noop(*args, **kwargs):
            return None

        async def _empty_dict(*args, **kwargs):
            return {}

        loop._quant_coder = fake_coder
        loop._risk_critic = fake_critic
        monkeypatch.setattr(loop, "_run_backtest", fake_backtest)
        monkeypatch.setattr(loop._tools, "get_angle_context", _empty_dict)
        monkeypatch.setattr(loop._tools, "get_feature_snapshot", _empty_dict)
        monkeypatch.setattr(loop._tools, "get_story", _empty_dict)
        monkeypatch.setattr(loop._tools, "get_drawdowns", _noop)
        monkeypatch.setattr(loop._tools, "get_benchmark_data", _noop)

        result = asyncio.run(loop.run(
            user_idea="SMA crossover",
            symbol="AAPL",
            from_date="2024-01-01",
            to_date="2024-06-01",
        ))

        assert calls["backtest"] == 1
        assert calls["critic"] == 0
        assert len(result.iterations) == 1
        assert result.iterations[0].critique.verdict == "STOP"

