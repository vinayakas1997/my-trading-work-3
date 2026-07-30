from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from vinu_portfolio.config import PortfolioConfig
from vinu_portfolio.service import PortfolioService


def _service(**overrides) -> PortfolioService:
    return PortfolioService(config=PortfolioConfig(**overrides))


def _resp(status_code=200, json_body=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body if json_body is not None else {}
    return resp


class TestFetchTradePlan:
    def test_yaml_strategy_returns_none(self) -> None:
        svc = _service()
        data, found = asyncio.run(svc._fetch_trade_plan({"kind": "yaml", "name": "a"}))
        assert data is None
        assert found is False

    def test_llm_strategy_with_no_artifact_id_returns_none(self) -> None:
        svc = _service()
        data, found = asyncio.run(svc._fetch_trade_plan({"kind": "llm_python"}))
        assert data is None
        assert found is False

    def test_llm_strategy_with_artifact_returns_data(self) -> None:
        svc = _service()
        plan_data = {"forecast": {"direction": "bullish"}, "p_failure": 0.3}
        svc._http.get = AsyncMock(return_value=_resp(200, plan_data))
        data, found = asyncio.run(
            svc._fetch_trade_plan({"kind": "llm_python", "artifact_id": "art_1"})
        )
        assert found is True
        assert data == plan_data

    def test_llm_strategy_non_200_returns_none(self) -> None:
        svc = _service()
        svc._http.get = AsyncMock(return_value=_resp(404))
        data, found = asyncio.run(
            svc._fetch_trade_plan({"kind": "llm_python", "artifact_id": "art_1"})
        )
        assert data is None
        assert found is False

    def test_llm_strategy_http_error_returns_none(self) -> None:
        svc = _service()
        svc._http.get = AsyncMock(side_effect=ConnectionError("down"))
        data, found = asyncio.run(
            svc._fetch_trade_plan({"kind": "llm_python", "artifact_id": "art_1"})
        )
        assert data is None
        assert found is False


class TestComputeDailyGamePlan:
    def test_passes_through_empty_portfolio(self) -> None:
        svc = _service()
        svc.compute_daily_allocation = AsyncMock(
            return_value={"status": "empty", "strategies": [], "weights": []}
        )
        result = asyncio.run(svc.compute_daily_game_plan())
        assert result["status"] == "empty"

    def test_readiness_score_zero_when_no_plans(self) -> None:
        svc = _service()
        svc.compute_daily_allocation = AsyncMock(
            return_value={
                "status": "ok",
                "n_strategies": 2,
                "strategies": [
                    {"name": "s1", "kind": "yaml"},
                    {"name": "s2", "kind": "yaml"},
                ],
                "weights": [
                    {"name": "s1", "kind": "yaml", "symbol": "AAPL", "target_weight": 0.5},
                    {"name": "s2", "kind": "yaml", "symbol": "MSFT", "target_weight": 0.5},
                ],
                "correlation_matrix": None,
                "shock_correlation": None,
                "timestamp": "2026-07-31T12:00:00",
                "regime": None,
                "account_equity": None,
            }
        )
        result = asyncio.run(svc.compute_daily_game_plan())
        assert result["readiness_score"] == 0.0
        assert result["readiness_flags"]["n_with_plan"] == 0
        assert result["readiness_flags"]["game_ready"] is False

    def test_readiness_score_partial_when_some_have_plans(self) -> None:
        svc = _service()
        svc.compute_daily_allocation = AsyncMock(
            return_value={
                "status": "ok",
                "n_strategies": 2,
                "strategies": [
                    {"name": "yaml_s", "kind": "yaml"},
                    {"name": "llm_s", "kind": "llm_python", "artifact_id": "art_1"},
                ],
                "weights": [
                    {"name": "yaml_s", "kind": "yaml", "symbol": "AAPL", "target_weight": 0.4},
                    {"name": "llm_s", "kind": "llm_python", "symbol": "MSFT", "target_weight": 0.6},
                ],
                "correlation_matrix": None,
                "shock_correlation": None,
                "timestamp": "2026-07-31T12:00:00",
                "regime": None,
                "account_equity": None,
            }
        )
        svc._fetch_trade_plan = AsyncMock(
            side_effect=[
                (None, False),
                ({"forecast": {"direction": "bullish"}, "p_failure": 0.2}, True),
            ]
        )
        result = asyncio.run(svc.compute_daily_game_plan())
        assert result["readiness_score"] == 0.5
        assert result["readiness_flags"]["n_with_plan"] == 1
        assert result["symbols"][0]["plan_status"] == "no_plan"
        assert result["symbols"][1]["plan_status"] == "found"
        assert result["symbols"][1]["p_failure"] == 0.2

    def test_readiness_score_full_when_all_have_plans(self) -> None:
        svc = _service()
        svc.compute_daily_allocation = AsyncMock(
            return_value={
                "status": "ok",
                "n_strategies": 1,
                "strategies": [
                    {"name": "llm_s", "kind": "llm_python", "artifact_id": "art_1"},
                ],
                "weights": [
                    {"name": "llm_s", "kind": "llm_python", "symbol": "NVDA", "target_weight": 1.0},
                ],
                "correlation_matrix": None,
                "shock_correlation": None,
                "timestamp": "2026-07-31T12:00:00",
                "regime": None,
                "account_equity": None,
            }
        )
        svc._fetch_trade_plan = AsyncMock(
            return_value=({"forecast": {"direction": "bearish"}, "invalidation_conditions": [{"type": "stop_loss"}]}, True)
        )
        result = asyncio.run(svc.compute_daily_game_plan())
        assert result["readiness_score"] == 1.0
        assert result["readiness_flags"]["game_ready"] is True
        assert result["symbols"][0]["forecast"]["direction"] == "bearish"
