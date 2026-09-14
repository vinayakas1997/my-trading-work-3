from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vinu_research.models import Forecast, InvalidationCondition, TradePlan
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


async def _fake_author_trade_plan(symbol, timeframe, config, tools, llm_client=None, summary_context=None):
    return TradePlan(
        symbol=symbol.upper(),
        timeframe=timeframe,
        direction="long",
        position_size_pct=0.04,
        forecast=Forecast(direction="long", confidence=0.6, magnitude_pct=0.02),
        # Stage A (A9): freeze_trade_plan refuses a plan with none.
        invalidation_conditions=[
            InvalidationCondition(
                metric="unrealized_pnl_pct", operator="<=", threshold=-0.08, action="exit",
            ),
        ],
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


class TestGetAngleCalibration:
    def test_no_entries_yet(self, client) -> None:
        resp = client.get("/research/angle-calibration/patchtst")
        assert resp.status_code == 200
        data = resp.json()
        assert data["angle_name"] == "patchtst"
        assert data["n_entries"] == 0

    def test_reflects_recorded_entries(self, service, client, monkeypatch) -> None:
        from vinu_research.models import AngleCalibrationEntry

        monkeypatch.setattr(routes_trade_plan, "author_trade_plan", _fake_author_trade_plan)
        created = client.post("/research/trade-plan/AAPL", json={"timeframe": "daily"}).json()

        service.strategy_store.append_angle_calibration_entry(AngleCalibrationEntry(
            angle_name="patchtst", artifact_id=created["artifact_id"], forecast_direction="long",
            actual_return_pct=0.03, directional_correct=True, brier_score=0.01,
        ))
        resp = client.get("/research/angle-calibration/patchtst")
        data = resp.json()
        assert data["n_entries"] == 1
        assert data["accuracy"] == 1.0

    def test_no_pass_fail_field_in_response(self, client) -> None:
        resp = client.get("/research/angle-calibration/patchtst")
        assert "passed" not in resp.json()


class TestGetCalibration:
    def test_no_entries_yet(self, client, monkeypatch) -> None:
        monkeypatch.setattr(routes_trade_plan, "author_trade_plan", _fake_author_trade_plan)
        created = client.post("/research/trade-plan/AAPL", json={"timeframe": "daily"}).json()
        resp = client.get(f"/research/trade-plan/{created['artifact_id']}/calibration")
        assert resp.status_code == 200
        data = resp.json()
        assert data["artifact_id"] == created["artifact_id"]
        assert data["n_entries"] == 0
        assert data["passed"] is False

    def test_reflects_recorded_outcomes(self, client, monkeypatch) -> None:
        monkeypatch.setattr(routes_trade_plan, "author_trade_plan", _fake_author_trade_plan)
        created = client.post("/research/trade-plan/AAPL", json={"timeframe": "daily"}).json()
        artifact_id = created["artifact_id"]
        for _ in range(3):
            client.post(
                f"/research/trade-plan/{artifact_id}/record-outcome",
                json={"actual_return_pct": 0.03},
            )
        resp = client.get(f"/research/trade-plan/{artifact_id}/calibration")
        assert resp.status_code == 200
        data = resp.json()
        assert data["n_entries"] == 3
        assert data["accuracy"] == pytest.approx(1.0)

    def test_unknown_artifact_returns_empty_result(self, client) -> None:
        resp = client.get("/research/trade-plan/does_not_exist/calibration")
        assert resp.status_code == 200
        data = resp.json()
        assert data["artifact_id"] == "does_not_exist"
        assert data["n_entries"] == 0


class TestUpdateInTradeActionRoute:
    def test_persists_a_valid_action(self, client, monkeypatch) -> None:
        monkeypatch.setattr(routes_trade_plan, "author_trade_plan", _fake_author_trade_plan)
        created = client.post("/research/trade-plan/AAPL", json={"timeframe": "daily"}).json()

        resp = client.post(
            f"/research/trade-plan/{created['artifact_id']}/action", json={"action": "ADD"},
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["in_trade_action"] == "ADD"

    def test_invalid_action_string_is_422(self, client, monkeypatch) -> None:
        monkeypatch.setattr(routes_trade_plan, "author_trade_plan", _fake_author_trade_plan)
        created = client.post("/research/trade-plan/AAPL", json={"timeframe": "daily"}).json()

        resp = client.post(
            f"/research/trade-plan/{created['artifact_id']}/action", json={"action": "SELL_EVERYTHING"},
        )

        assert resp.status_code == 422

    def test_unknown_artifact_does_not_raise(self, client) -> None:
        resp = client.post(
            "/research/trade-plan/does_not_exist/action", json={"action": "HOLD"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "not_persisted"


class TestApproveDecayActionRoute:
    """approve_decay_action used to have no HTTP route or CLI command --
    `propose`-mode decay actions had no way to actually be acted on short of
    a Python REPL. This route mirrors approve_trade_plan_route's shape."""

    @staticmethod
    def _artifact_with_proposal(strategy_store):
        from vinu_research.models import Artifact, ArtifactStatus

        a = Artifact.create("strategy", "Test", universe=["AAPL"])
        a.status = ArtifactStatus.MONITORING
        strategy_store.upsert_artifact(a)
        strategy_store.record_proposed_decay_action(a.artifact_id, "MONITORING", "DECAYED")
        return a

    def test_approves_and_applies_the_transition(self, client, strategy_store) -> None:
        artifact = self._artifact_with_proposal(strategy_store)

        resp = client.post(
            f"/research/decay/{artifact.artifact_id}/approve", params={"approver": "alice"},
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "DECAYED"

    def test_missing_approver_is_400(self, client, strategy_store) -> None:
        artifact = self._artifact_with_proposal(strategy_store)

        resp = client.post(f"/research/decay/{artifact.artifact_id}/approve")

        assert resp.status_code == 400

    def test_no_proposal_is_404(self, client, strategy_store) -> None:
        from vinu_research.models import Artifact

        a = Artifact.create("strategy", "Test", universe=["AAPL"])
        strategy_store.upsert_artifact(a)

        resp = client.post(
            f"/research/decay/{a.artifact_id}/approve", params={"approver": "alice"},
        )

        assert resp.status_code == 404

    def test_unknown_artifact_is_404(self, client) -> None:
        resp = client.post(
            "/research/decay/does_not_exist/approve", params={"approver": "alice"},
        )
        assert resp.status_code == 404


class TestApproveTradeScoreCalibrationRoute:
    """approve_proposal (trade_score_calibration.py) used to have no HTTP
    route or CLI command -- mirrors approve_decay_action_route's shape,
    except this isn't artifact-keyed (one global pending proposal, or
    none), so no artifact_id path parameter."""

    @pytest.fixture(autouse=True)
    def _isolated_state(self, tmp_path, monkeypatch):
        import vinu_research.trade_score_calibration as tsc
        monkeypatch.setattr(tsc, "DEFAULT_STATE_PATH", str(tmp_path / "trade_score_calibration.json"))

    def test_approves_and_applies_the_proposal(self, client) -> None:
        from vinu_research.config import TradeScoreThresholds
        from vinu_research.trade_score_calibration import save_proposal

        save_proposal(TradeScoreThresholds(confluence_max=45.0), {"status": "ok", "n_entries": 30})

        resp = client.post("/research/trade-score-calibration/approve", params={"approver": "alice"})

        assert resp.status_code == 200
        assert resp.json()["confluence_max"] == 45.0

    def test_missing_approver_is_400(self, client) -> None:
        from vinu_research.config import TradeScoreThresholds
        from vinu_research.trade_score_calibration import save_proposal

        save_proposal(TradeScoreThresholds(confluence_max=45.0), {"status": "ok"})

        resp = client.post("/research/trade-score-calibration/approve")

        assert resp.status_code == 400

    def test_no_pending_proposal_is_404(self, client) -> None:
        resp = client.post("/research/trade-score-calibration/approve", params={"approver": "alice"})
        assert resp.status_code == 404
