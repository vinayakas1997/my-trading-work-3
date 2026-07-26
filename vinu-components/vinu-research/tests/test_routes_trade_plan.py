from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vinu_research.models import Forecast, TradePlan
from vinu_research.server import routes_trade_plan
from vinu_research.server.app import create_app
from vinu_research.service import ResearchService


@pytest.fixture
def service(storage, strategy_store):
    from vinu_research.config import ResearchConfig
    cfg = ResearchConfig()
    return ResearchService(config=cfg, storage=storage, strategy_store=strategy_store)


@pytest.fixture
def app(service):
    return create_app(service)


@pytest.fixture
def client(app):
    return TestClient(app)


async def _fake_author_trade_plan(symbol, timeframe, config, tools, llm_client=None):
    return TradePlan(
        symbol=symbol.upper(),
        timeframe=timeframe,
        direction="long",
        position_size_pct=0.04,
        forecast=Forecast(direction="long", confidence=0.6, magnitude_pct=0.02),
    )


class TestGenerateTradePlan:
    def test_generates_and_freezes(self, client, monkeypatch) -> None:
        monkeypatch.setattr(routes_trade_plan, "author_trade_plan", _fake_author_trade_plan)
        resp = client.post("/research/trade-plan/AAPL", json={"timeframe": "daily"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "trade_plan"
        assert data["status"] == "CREATED"
        assert data["universe"] == ["AAPL"]
        assert data["trade_plan_data"]

    def test_rejects_bad_timeframe(self, client, monkeypatch) -> None:
        monkeypatch.setattr(routes_trade_plan, "author_trade_plan", _fake_author_trade_plan)
        resp = client.post("/research/trade-plan/AAPL", json={"timeframe": "yearly"})
        assert resp.status_code == 422


class TestGetTradePlan:
    def test_404_for_missing(self, client) -> None:
        resp = client.get("/research/trade-plan/does_not_exist")
        assert resp.status_code == 404

    def test_returns_frozen_plan(self, client, monkeypatch) -> None:
        monkeypatch.setattr(routes_trade_plan, "author_trade_plan", _fake_author_trade_plan)
        created = client.post("/research/trade-plan/AAPL", json={"timeframe": "daily"}).json()
        resp = client.get(f"/research/trade-plan/{created['artifact_id']}")
        assert resp.status_code == 200
        assert resp.json()["artifact_id"] == created["artifact_id"]


class TestApproveTradePlan:
    def test_404_for_missing(self, client) -> None:
        resp = client.post("/research/trade-plan/does_not_exist/approve")
        assert resp.status_code == 404

    def test_fails_closed_with_no_calibration_history(self, client, monkeypatch) -> None:
        monkeypatch.setattr(routes_trade_plan, "author_trade_plan", _fake_author_trade_plan)
        created = client.post("/research/trade-plan/AAPL", json={"timeframe": "daily"}).json()
        resp = client.post(f"/research/trade-plan/{created['artifact_id']}/approve")
        assert resp.status_code == 409
        assert resp.json()["detail"]["reasons"]

    def test_succeeds_once_enough_realized_outcomes_recorded(self, client, monkeypatch) -> None:
        monkeypatch.setattr(routes_trade_plan, "author_trade_plan", _fake_author_trade_plan)
        created = client.post("/research/trade-plan/AAPL", json={"timeframe": "daily"}).json()
        artifact_id = created["artifact_id"]
        for _ in range(10):
            resp = client.post(
                f"/research/trade-plan/{artifact_id}/record-outcome",
                json={"actual_return_pct": 0.03},
            )
            assert resp.status_code == 200

        resp = client.post(f"/research/trade-plan/{artifact_id}/approve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ACTIVE"


class TestRecordOutcome:
    def test_404_for_missing_artifact(self, client) -> None:
        resp = client.post(
            "/research/trade-plan/does_not_exist/record-outcome",
            json={"actual_return_pct": 0.03},
        )
        assert resp.status_code == 404

    def test_records_and_scores_outcome(self, client, monkeypatch) -> None:
        monkeypatch.setattr(routes_trade_plan, "author_trade_plan", _fake_author_trade_plan)
        created = client.post("/research/trade-plan/AAPL", json={"timeframe": "daily"}).json()
        resp = client.post(
            f"/research/trade-plan/{created['artifact_id']}/record-outcome",
            json={"actual_return_pct": 0.03},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["forecast_direction"] == "long"
        assert data["directional_correct"] is True
