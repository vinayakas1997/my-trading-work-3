from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from vinu_research.config import ResearchConfig
from vinu_research.llm import (
    LLM_SYSTEM_PROMPT,
    LlmCache,
    ResearchLlmClient,
    _build_risk_critic_prompt,
)
from vinu_research.models import BacktestMetrics, BacktestResult, CriticFeedback
from vinu_research.loop import StrategyResearchLoop


@pytest.fixture
def sample_result() -> BacktestResult:
    metrics = BacktestMetrics(
        sharpe_ratio=0.72, max_drawdown=-0.183, win_rate=0.51,
        total_return=0.082, sortino_ratio=0.6, calmar_ratio=0.4,
    )
    return BacktestResult(
        run_id="r1", strategy_name="test", metrics=metrics,
        benchmark_metrics={}, trade_count=50, equity_points=100,
    )


@pytest.fixture
def sample_story() -> dict:
    return {
        "drawdown_events": [
            {"drop_pct": -12.3, "sessions_involved": ["london", "ny_regular"]},
            {"drop_pct": -5.1, "sessions_involved": ["ny_regular"]},
        ],
        "correlations": {
            "by_session": {
                "london": {"pearson": -0.41, "sample_hours": 450},
                "ny_regular": {"pearson": -0.18, "sample_hours": 890},
            },
        },
        "baseline_anomalies": [
            {"session": "london", "z_score": 3.8},
        ],
    }


def test_build_risk_critic_prompt(sample_result, sample_story):
    rules = CriticFeedback(
        verdict="REFINE",
        reasoning="Sharpe=0.72, MaxDD=-18.3%",
        suggestions=["Add volatility guard", "Add ADX filter"],
    )
    prompt = _build_risk_critic_prompt(
        "test SMA crossover", "AAPL", "2024-01-01", "2024-12-31",
        sample_result, rules, sample_story,
    )
    assert "test SMA crossover" in prompt
    assert "AAPL" in prompt
    assert "2024-01-01" in prompt
    assert "Sharpe: 0.72" in prompt
    assert "MaxDD: -18.3%" in prompt
    assert "Win Rate: 51%" in prompt
    assert "Add volatility guard" in prompt
    assert "Add ADX filter" in prompt
    assert "london" in prompt
    assert "Drawdown events: 2" in prompt


def test_build_risk_critic_prompt_no_story(sample_result):
    rules = CriticFeedback(verdict="REFINE", reasoning="test", suggestions=["Fix it"])
    prompt = _build_risk_critic_prompt(
        "test", "AAPL", "2024-01-01", "2024-12-31",
        sample_result, rules, None,
    )
    assert "Story Blocks:" not in prompt


class TestLlmCache:
    def test_cache_miss(self, tmp_path):
        cache = LlmCache(tmp_path / "test_cache.db", 3600)
        assert cache.get("missing_key") is None

    def test_cache_set_get(self, tmp_path):
        cache = LlmCache(tmp_path / "test_cache.db", 3600)
        data = {"suggestions": ["test"]}
        cache.set("key1", data)
        result = cache.get("key1")
        assert result == data

    def test_cache_ttl_expiry(self, tmp_path):
        cache = LlmCache(tmp_path / "test_cache.db", 0)
        cache.set("key1", {"val": 1})
        assert cache.get("key1") is None


class TestMergeFeedback:
    def test_rules_only_when_llm_none(self):
        loop = StrategyResearchLoop()
        rules = CriticFeedback(verdict="REFINE", reasoning="test", suggestions=["rule 1"])
        merged = loop._merge_feedback(rules, None)
        assert merged.verdict == "REFINE"
        assert merged.suggestions == ["rule 1"]

    def test_llm_adds_suggestions(self):
        loop = StrategyResearchLoop()
        rules = CriticFeedback(verdict="REFINE", reasoning="test", suggestions=["rule 1"])
        llm = {"additional_suggestions": ["llm suggestion 1"]}
        merged = loop._merge_feedback(rules, llm)
        assert "rule 1" in merged.suggestions
        assert "llm suggestion 1" in merged.suggestions

    def test_llm_does_not_deduplicate_identical(self):
        loop = StrategyResearchLoop()
        rules = CriticFeedback(verdict="REFINE", reasoning="test", suggestions=["rule 1"])
        llm = {"additional_suggestions": ["rule 1"]}
        merged = loop._merge_feedback(rules, llm)
        assert merged.suggestions == ["rule 1"]

    def test_llm_upgrades_verdict(self):
        loop = StrategyResearchLoop()
        rules = CriticFeedback(verdict="REFINE", reasoning="test", suggestions=[])
        llm = {"verdict_upgrade": "PASS", "additional_suggestions": []}
        merged = loop._merge_feedback(rules, llm)
        assert merged.verdict == "PASS"

    def test_llm_does_not_downgrade_verdict(self):
        loop = StrategyResearchLoop()
        rules = CriticFeedback(verdict="PASS", reasoning="test", suggestions=[])
        llm = {"verdict_upgrade": "STOP", "additional_suggestions": []}
        merged = loop._merge_feedback(rules, llm)
        assert merged.verdict == "PASS"


class TestRuleBasedCheck:
    def test_rules_always_run_with_llm_disabled(self, sample_result, sample_story):
        loop = StrategyResearchLoop(config=ResearchConfig(llm_enabled=False))
        feedback = loop._rule_based_check(sample_result, sample_story, None, iteration=1)
        assert feedback.verdict == "REFINE"
        assert len(feedback.suggestions) > 0

    def test_rules_pass_with_good_metrics(self, sample_result, sample_story):
        loop = StrategyResearchLoop()
        good_result = BacktestResult(
            run_id="r2", strategy_name="good", metrics=BacktestMetrics(
                sharpe_ratio=1.6, max_drawdown=-0.05, win_rate=0.7,
            ), benchmark_metrics={}, trade_count=50, equity_points=100,
        )
        feedback = loop._rule_based_check(good_result, sample_story, None, iteration=1)
        assert feedback.verdict == "PASS"
