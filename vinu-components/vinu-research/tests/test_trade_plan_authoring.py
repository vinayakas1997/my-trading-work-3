from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_research.config import ResearchConfig
from vinu_research.forecast_skill import ForecastSkillConfig
from vinu_research.models import ArtifactStatus, Forecast, TradePlan
from vinu_research.trade_plan_authoring import (
    TradePlanApprovalError,
    approve_trade_plan,
    author_trade_plan,
    fetch_personality_features,
    fetch_risk_state,
    freeze_trade_plan,
    record_realized_outcome,
)


class _StubTools:
    """Duck-types the subset of ResearchTools trade_plan_authoring depends on."""

    def __init__(self, returns: pd.Series | None, angle_rows: dict[str, list[dict]]) -> None:
        self._returns = returns
        self._angle_rows = angle_rows

    async def get_benchmark_data(self, symbol, from_date, to_date):
        return self._returns

    async def get_angle_rows(self, angle_name, symbol):
        return self._angle_rows.get(angle_name, [])


def _synthetic_returns(n: int = 120, seed: int = 7) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(loc=0.0005, scale=0.015, size=n))


class _StubLlmClient:
    def __init__(self, response: dict) -> None:
        self._response = response

    async def chat_json(self, system, user):
        return self._response


class TestFetchRiskState:
    async def test_insufficient_data_when_no_returns(self) -> None:
        tools = _StubTools(returns=None, angle_rows={})
        state = await fetch_risk_state(tools, "AAPL")
        assert state["status"] == "insufficient_data"

    async def test_insufficient_data_when_too_few_returns(self) -> None:
        tools = _StubTools(returns=_synthetic_returns(5), angle_rows={})
        state = await fetch_risk_state(tools, "AAPL")
        assert state["status"] == "insufficient_data"

    async def test_ok_status_has_expected_fields(self) -> None:
        tools = _StubTools(returns=_synthetic_returns(120), angle_rows={})
        state = await fetch_risk_state(tools, "AAPL")
        assert state["status"] == "ok"
        for key in (
            "annualized_volatility", "var_95_daily", "cvar_95_daily",
            "expected_move_1d_pct", "kelly_fraction", "garch_persistence",
        ):
            assert key in state


class TestFetchPersonalityFeatures:
    async def test_returns_latest_row_of_each_angle(self) -> None:
        tools = _StubTools(
            returns=None,
            angle_rows={
                "shock_personality": [{"gap_fill_rate": {"mean": 0.3}}, {"gap_fill_rate": {"mean": 0.5}}],
                "shock_clustering": [{"cluster_members": [{"symbol": "MSFT", "shock_correlation": 0.8}]}],
            },
        )
        features = await fetch_personality_features(tools, "AAPL")
        assert features["shock_personality"]["gap_fill_rate"]["mean"] == 0.5
        assert features["shock_clustering"]["cluster_members"][0]["symbol"] == "MSFT"

    async def test_empty_when_no_angle_data(self) -> None:
        tools = _StubTools(returns=None, angle_rows={})
        features = await fetch_personality_features(tools, "AAPL")
        assert features == {"shock_personality": {}, "shock_clustering": {}}


class TestAuthorTradePlan:
    async def test_produces_complete_plan(self) -> None:
        tools = _StubTools(
            returns=_synthetic_returns(120),
            angle_rows={
                "shock_clustering": [{"cluster_members": [{"symbol": "MSFT", "shock_correlation": 0.75}]}],
            },
        )
        llm = _StubLlmClient({
            "direction": "long",
            "confidence": 0.65,
            "magnitude_pct": 0.03,
            "magnitude_std": 0.01,
            "horizon_days": 5,
            "reasoning": "personality gap-fill + positive drift",
        })
        plan = await author_trade_plan("aapl", "daily", ResearchConfig(), tools, llm)

        assert isinstance(plan, TradePlan)
        assert plan.symbol == "AAPL"
        assert plan.direction == "long"
        assert plan.forecast is not None
        assert plan.position_size_pct == plan.risk_bands.max_position_size_pct
        assert plan.risk_bands.var_95_limit >= 0
        # Cluster membership present -> the cluster-correlation contingency rule fires.
        assert any(r.metric == "shock_cluster_correlation" for r in plan.contingency_rules)
        # Every rule is a mechanically evaluable metric/operator/threshold triple.
        for rule in plan.contingency_rules + plan.invalidation_conditions:
            assert rule.metric
            assert rule.operator in (">=", "<=", ">", "<", "==", "!=")
            assert isinstance(rule.threshold, float)

    async def test_no_cluster_rule_without_cluster_members(self) -> None:
        tools = _StubTools(returns=_synthetic_returns(120), angle_rows={})
        llm = _StubLlmClient({
            "direction": "neutral", "confidence": 0.0, "magnitude_pct": 0.0,
            "magnitude_std": 0.0, "horizon_days": 1,
        })
        plan = await author_trade_plan("AAPL", "daily", ResearchConfig(), tools, llm)
        assert not any(r.metric == "shock_cluster_correlation" for r in plan.contingency_rules)


class TestFreezeAndApprove:
    def _sample_plan(self) -> TradePlan:
        return TradePlan(
            symbol="AAPL",
            timeframe="daily",
            direction="long",
            position_size_pct=0.05,
            forecast=Forecast(direction="long", confidence=0.6, magnitude_pct=0.02),
        )

    def test_freeze_persists_as_created(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, self._sample_plan())
        assert artifact.type == "trade_plan"
        assert artifact.status == ArtifactStatus.CREATED
        assert artifact.trade_plan_data

        reloaded = strategy_store.get_artifact(artifact.artifact_id)
        assert reloaded is not None
        round_tripped = TradePlan.from_json(reloaded.trade_plan_data)
        assert round_tripped.symbol == "AAPL"
        assert round_tripped.forecast.direction == "long"

    def test_approve_fails_closed_with_no_calibration_entries(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, self._sample_plan())
        with pytest.raises(TradePlanApprovalError) as exc_info:
            approve_trade_plan(strategy_store, artifact.artifact_id)
        assert exc_info.value.reasons

    def test_approve_succeeds_when_calibration_passes(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, self._sample_plan())
        cfg = ForecastSkillConfig(min_calibration_window=5)
        for _ in range(5):
            record_realized_outcome(strategy_store, artifact.artifact_id, 0.03, cfg)

        approved = approve_trade_plan(strategy_store, artifact.artifact_id, cfg)
        assert approved.status == ArtifactStatus.ACTIVE

    def test_approve_rejects_mutation_once_active(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, self._sample_plan())
        cfg = ForecastSkillConfig(min_calibration_window=5)
        for _ in range(5):
            record_realized_outcome(strategy_store, artifact.artifact_id, 0.03, cfg)
        approve_trade_plan(strategy_store, artifact.artifact_id, cfg)

        with pytest.raises(TradePlanApprovalError):
            approve_trade_plan(strategy_store, artifact.artifact_id, cfg)

    def test_approve_raises_for_missing_artifact(self, strategy_store) -> None:
        with pytest.raises(ValueError):
            approve_trade_plan(strategy_store, "does_not_exist")
