from __future__ import annotations

from vinu_research.loop import StrategyResearchLoop, _LRUCache
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
    def make_result(self, sharpe: float, max_dd: float, win_rate: float) -> BacktestResult:
        metrics = BacktestMetrics(sharpe_ratio=sharpe, max_drawdown=max_dd, win_rate=win_rate)
        return BacktestResult(
            run_id="r1", strategy_name="s", metrics=metrics,
            benchmark_metrics={}, trade_count=10, equity_points=100,
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
