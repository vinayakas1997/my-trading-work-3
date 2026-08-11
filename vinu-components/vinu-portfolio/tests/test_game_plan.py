from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

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


def _force_research_link_unavailable():
    return patch(
        "vinu_portfolio.research_link.get_strategy_store",
        side_effect=RuntimeError("not available"),
    )


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

    def test_llm_strategy_with_real_artifact_returns_data_in_process(self) -> None:
        from pathlib import Path
        import tempfile

        from vinu_research.models import Artifact
        from vinu_research.storage.strategy_store import SqliteStrategyStore

        store = SqliteStrategyStore(Path(tempfile.mktemp(suffix=".db")))
        artifact = Artifact.create("trade_plan", "plan-aapl", universe=["AAPL"])
        store.upsert_artifact(artifact)

        svc = _service()
        with patch("vinu_portfolio.research_link.get_strategy_store", return_value=store):
            data, found = asyncio.run(
                svc._fetch_trade_plan({"kind": "llm_python", "artifact_id": artifact.artifact_id})
            )
        assert found is True
        assert data["artifact_id"] == artifact.artifact_id

    def test_llm_strategy_with_artifact_returns_data(self) -> None:
        svc = _service()
        plan_data = {"forecast": {"direction": "bullish"}, "p_failure": 0.3}
        svc._http.get = AsyncMock(return_value=_resp(200, plan_data))
        with _force_research_link_unavailable():
            data, found = asyncio.run(
                svc._fetch_trade_plan({"kind": "llm_python", "artifact_id": "art_1"})
            )
        assert found is True
        assert data == plan_data

    def test_llm_strategy_non_200_returns_none(self) -> None:
        svc = _service()
        svc._http.get = AsyncMock(return_value=_resp(404))
        with _force_research_link_unavailable():
            data, found = asyncio.run(
                svc._fetch_trade_plan({"kind": "llm_python", "artifact_id": "art_1"})
            )
        assert data is None
        assert found is False

    def test_llm_strategy_http_error_returns_none(self) -> None:
        svc = _service()
        svc._http.get = AsyncMock(side_effect=ConnectionError("down"))
        with _force_research_link_unavailable():
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
        assert result["readiness_flags"]["regime_available"] is False
        assert result["readiness_flags"]["equity_available"] is False
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
        # 1/2 symbols have plans, regime and equity both unavailable: 1 of 4 data points live.
        assert result["readiness_score"] == 0.25
        assert result["readiness_flags"]["n_with_plan"] == 1
        assert result["readiness_flags"]["regime_available"] is False
        assert result["readiness_flags"]["equity_available"] is False
        assert result["symbols"][0]["plan_status"] == "no_plan"
        assert result["symbols"][1]["plan_status"] == "found"
        assert result["symbols"][1]["p_failure"] == 0.2

    def test_readiness_score_reflects_regime_and_equity_availability(self) -> None:
        svc = _service()
        svc.compute_daily_allocation = AsyncMock(
            return_value={
                "status": "ok",
                "n_strategies": 1,
                "strategies": [
                    {"name": "s1", "kind": "yaml"},
                ],
                "weights": [
                    {"name": "s1", "kind": "yaml", "symbol": "AAPL", "target_weight": 1.0},
                ],
                "correlation_matrix": None,
                "shock_correlation": None,
                "timestamp": "2026-07-31T12:00:00",
                "regime": None,
                "account_equity": None,
            }
        )
        result = asyncio.run(svc.compute_daily_game_plan())
        assert result["readiness_flags"]["regime_available"] is False
        assert result["readiness_flags"]["equity_available"] is False
        # No plan, no regime, no equity: 0 of 3 data points live.
        assert result["readiness_score"] == 0.0

    def test_all_data_unavailable_edge_case(self) -> None:
        svc = _service()
        svc.compute_daily_allocation = AsyncMock(
            return_value={
                "status": "ok",
                "n_strategies": 2,
                "strategies": [
                    {"name": "s1", "kind": "llm_python", "artifact_id": "art_1"},
                    {"name": "s2", "kind": "llm_python", "artifact_id": "art_2"},
                ],
                "weights": [
                    {"name": "s1", "kind": "llm_python", "symbol": "AAPL", "target_weight": 0.5},
                    {"name": "s2", "kind": "llm_python", "symbol": "MSFT", "target_weight": 0.5},
                ],
                "correlation_matrix": None,
                "shock_correlation": None,
                "timestamp": "2026-07-31T12:00:00",
                "regime": {"status": "unavailable", "regime": None},
                "account_equity": None,
            }
        )
        svc._fetch_trade_plan = AsyncMock(return_value=(None, False))
        result = asyncio.run(svc.compute_daily_game_plan())
        assert result["readiness_score"] == 0.0
        assert result["readiness_flags"]["n_with_plan"] == 0
        assert result["readiness_flags"]["regime_available"] is False
        assert result["readiness_flags"]["equity_available"] is False
        assert result["readiness_flags"]["game_ready"] is False
        assert all(s["plan_status"] == "no_plan" for s in result["symbols"])

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
                "regime": {"status": "ok", "regime": "bull"},
                "account_equity": 100_000.0,
            }
        )
        svc._fetch_trade_plan = AsyncMock(
            return_value=({"forecast": {"direction": "bearish"}, "invalidation_conditions": [{"type": "stop_loss"}]}, True)
        )
        result = asyncio.run(svc.compute_daily_game_plan())
        assert result["readiness_score"] == 1.0
        assert result["readiness_flags"]["regime_available"] is True
        assert result["readiness_flags"]["equity_available"] is True
        assert result["readiness_flags"]["game_ready"] is True
        assert result["symbols"][0]["forecast"]["direction"] == "bearish"
