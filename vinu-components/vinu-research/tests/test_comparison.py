from __future__ import annotations

import pytest

from vinu_research.comparison import RankedCandidate, best_candidate, rank_candidates
from vinu_research.models import BacktestResult, BacktestMetrics, LlmCandidate


@pytest.fixture
def good_metrics() -> BacktestMetrics:
    return BacktestMetrics(
        sharpe_ratio=1.5,
        sortino_ratio=2.0,
        calmar_ratio=1.8,
        max_drawdown=-0.15,
        total_return=0.35,
        win_rate=0.55,
        annual_volatility=0.18,
        alpha=0.05,
        beta=0.8,
    )


@pytest.fixture
def bad_metrics() -> BacktestMetrics:
    return BacktestMetrics(
        sharpe_ratio=-0.5,
        sortino_ratio=-0.3,
        calmar_ratio=-0.2,
        max_drawdown=-0.45,
        total_return=-0.15,
        win_rate=0.35,
        annual_volatility=0.30,
        alpha=-0.05,
        beta=1.2,
    )


@pytest.fixture
def short_candidate() -> LlmCandidate:
    return LlmCandidate(
        code="class UserStrategy(BaseStrategy):\n    def generate_weights(self, data):\n        return data['close'] * 0.5",
        features_required=["close"],
        reasoning="short",
        params={},
    )


@pytest.fixture
def long_candidate() -> LlmCandidate:
    lines = [f"    x{i} = 1" for i in range(30)]
    code = "class UserStrategy(BaseStrategy):\n    def generate_weights(self, data):\n" + "\n".join(lines)
    return LlmCandidate(
        code=code,
        features_required=["close"],
        reasoning="long",
        params={},
    )


class TestRankCandidates:
    def test_ranks_by_score(self, short_candidate, long_candidate):
        ranked = rank_candidates([short_candidate, long_candidate])
        assert ranked[0].score >= ranked[1].score
        assert ranked[0].candidate.code == short_candidate.code

    def test_empty_list_returns_empty(self):
        assert rank_candidates([]) == []

    def test_good_backtest_boosts_score(self, short_candidate, good_metrics, bad_metrics):
        good_result = BacktestResult(run_id="g", strategy_name="g", metrics=good_metrics, benchmark_metrics={}, trade_count=10, equity_points=0)
        bad_result = BacktestResult(run_id="b", strategy_name="b", metrics=bad_metrics, benchmark_metrics={}, trade_count=10, equity_points=0)
        ranked = rank_candidates(
            [short_candidate, short_candidate],
            [good_result, bad_result],
        )
        assert ranked[0].score > ranked[1].score

    def test_risk_score_computed(self, short_candidate, good_metrics):
        good_result = BacktestResult(run_id="g", strategy_name="g", metrics=good_metrics, benchmark_metrics={}, trade_count=10, equity_points=0)
        ranked = rank_candidates([short_candidate], [good_result])
        assert ranked[0].risk_score > 0

    def test_complexity_score_computed(self, short_candidate, long_candidate):
        ranked = rank_candidates([short_candidate, long_candidate])
        assert ranked[0].complexity_score >= ranked[1].complexity_score


class TestBestCandidate:
    def test_returns_highest_scoring(self, short_candidate, long_candidate):
        best = best_candidate([short_candidate, long_candidate])
        assert best is not None
        assert best.candidate.code == short_candidate.code

    def test_returns_none_for_empty(self):
        assert best_candidate([]) is None

    def test_respects_backtest_results(self, short_candidate, good_metrics, bad_metrics):
        good_result = BacktestResult(run_id="g", strategy_name="g", metrics=good_metrics, benchmark_metrics={}, trade_count=10, equity_points=0)
        bad_result = BacktestResult(run_id="b", strategy_name="b", metrics=bad_metrics, benchmark_metrics={}, trade_count=10, equity_points=0)
        good_c = LlmCandidate(code=short_candidate.code + "\n# good", features_required=[], reasoning="", params={})
        bad_c = LlmCandidate(code=short_candidate.code + "\n# bad", features_required=[], reasoning="", params={})
        best = best_candidate([bad_c, good_c], [bad_result, good_result])
        assert best is not None
        assert "good" in best.candidate.code
