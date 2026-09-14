from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import vinu_agent.server.routes_swarm as routes_swarm


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hours_ago_iso(hours: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


@pytest.fixture
def fake_runtime() -> MagicMock:
    return MagicMock()


@pytest.fixture
def client(fake_runtime: MagicMock) -> TestClient:
    fake_service = MagicMock()
    fake_service.swarm_runtime = fake_runtime
    routes_swarm._get_service = lambda: fake_service
    app = FastAPI()
    app.include_router(routes_swarm.router)
    return TestClient(app)


class TestGetLatestSwarmRun:
    def test_no_matching_run_returns_none_status(self, client, fake_runtime) -> None:
        fake_runtime.get_latest_run.return_value = None

        resp = client.get("/swarm/runs/latest", params={"preset_name": "investment_committee", "symbol": "AAPL"})

        assert resp.status_code == 200
        assert resp.json() == {"status": "none"}

    def test_matching_run_returns_final_report_and_tasks(self, client, fake_runtime) -> None:
        run = MagicMock()
        run.run_id = "run_1"
        run.preset_name = "investment_committee"
        run.final_report = "Bullish overall."
        run.completed_at = "2024-06-01T00:00:00Z"
        task = MagicMock(agent_name="risk_officer", role="Risk Officer", result="Bullish, high conviction.")
        run.tasks = [task]
        fake_runtime.get_latest_run.return_value = run

        resp = client.get("/swarm/runs/latest", params={"preset_name": "investment_committee", "symbol": "AAPL"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["run_id"] == "run_1"
        assert body["final_report"] == "Bullish overall."
        assert body["tasks"][0]["agent_name"] == "risk_officer"
        assert body["tasks"][0]["result"] == "Bullish, high conviction."

    def test_literal_latest_path_not_shadowed_by_run_id_route(self, client, fake_runtime) -> None:
        # Regression guard: /swarm/runs/latest must resolve to this route,
        # not be swallowed as run_id="latest" by the dynamic
        # /swarm/runs/{run_id} route registered later in the file.
        fake_runtime.get_latest_run.return_value = None
        resp = client.get("/swarm/runs/latest", params={"preset_name": "x", "symbol": "y"})
        assert resp.status_code == 200
        fake_runtime.get_run.assert_not_called()


class TestEnsureFreshSwarmRun:
    """In-trade thesis re-check follow-up: /swarm/runs/ensure-fresh returns
    whatever the latest run currently is immediately, and kicks off a new
    background run (fire-and-forget) only when it's missing or stale --
    never blocks the caller waiting for a new run to finish."""

    def test_fresh_run_returned_without_starting_a_new_one(self, client, fake_runtime) -> None:
        run = MagicMock()
        run.run_id = "run_1"
        run.preset_name = "investment_committee"
        run.final_report = "Bullish overall."
        run.completed_at = _now_iso()
        run.tasks = []
        fake_runtime.get_latest_run.return_value = run

        resp = client.post(
            "/swarm/runs/ensure-fresh",
            params={"preset_name": "investment_committee", "symbol": "AAPL", "max_age_minutes": 60},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["stale"] is False
        fake_runtime.create_run.assert_not_called()

    def test_stale_run_still_returned_but_triggers_refresh(self, client, fake_runtime) -> None:
        run = MagicMock()
        run.run_id = "run_1"
        run.preset_name = "investment_committee"
        run.final_report = "Bullish overall."
        run.completed_at = _hours_ago_iso(3)
        run.tasks = []
        fake_runtime.get_latest_run.return_value = run
        new_run = MagicMock(run_id="run_2")
        fake_runtime.create_run.return_value = new_run

        resp = client.post(
            "/swarm/runs/ensure-fresh",
            params={"preset_name": "investment_committee", "symbol": "AAPL", "max_age_minutes": 60},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["run_id"] == "run_1"  # the stale result, not the new one
        assert body["stale"] is True
        fake_runtime.create_run.assert_called_once_with("investment_committee", {"symbol": "AAPL"})
        fake_runtime.start_run.assert_called_once_with("run_2")

    def test_no_existing_run_triggers_refresh_and_returns_none_status(self, client, fake_runtime) -> None:
        fake_runtime.get_latest_run.return_value = None
        new_run = MagicMock(run_id="run_2")
        fake_runtime.create_run.return_value = new_run

        resp = client.post(
            "/swarm/runs/ensure-fresh",
            params={"preset_name": "investment_committee", "symbol": "AAPL"},
        )

        assert resp.status_code == 200
        assert resp.json() == {"status": "none"}
        fake_runtime.create_run.assert_called_once()

    def test_refresh_failure_does_not_break_the_response(self, client, fake_runtime) -> None:
        fake_runtime.get_latest_run.return_value = None
        fake_runtime.create_run.side_effect = RuntimeError("preset not found")

        resp = client.post(
            "/swarm/runs/ensure-fresh",
            params={"preset_name": "bogus", "symbol": "AAPL"},
        )

        assert resp.status_code == 200
        assert resp.json() == {"status": "none"}
