"""Tests for the FastAPI app's rebalance-request route -- the HTTP intake
point Phase 2's capital_allocator rebalancer needed (previously flagged as
"no HTTP route yet, on purpose... needs a decision on shared persistence
before an HTTP route can safely be added", closed alongside
RebalanceRequestQueue's move to a SQLite-backed, shared on-disk store).
See server/app.py, trade_plan/rebalance_intake.py.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from vinu_live.config import LiveConfig
from vinu_live.server.app import create_app
from vinu_live.trade_plan.rebalance_intake import RebalanceRequestQueue


@pytest.fixture
def client(tmp_path):
    config = LiveConfig(data_root=tmp_path)
    with patch("vinu_live.server.app.load_config", return_value=config):
        app = create_app()
        yield TestClient(app), config


class TestRebalanceRequestRoute:
    def test_submits_and_acks(self, client) -> None:
        test_client, _config = client
        resp = test_client.post("/live/trade-plan/rebalance-request", json={"symbol": "aapl", "reason": "free capital"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "symbol": "AAPL"}

    def test_request_is_visible_to_a_separate_orchestrator_instance(self, client) -> None:
        """The actual bug this route's design has to avoid: the route
        handler constructs its own throwaway TradePlanOrchestrator per
        request. Proves a second, independent RebalanceRequestQueue
        pointed at the same config.data_root sees the request -- the real
        trade-plan-worker's own long-running orchestrator, in production."""
        test_client, config = client
        resp = test_client.post("/live/trade-plan/rebalance-request", json={"symbol": "MSFT", "reason": "unwind X"})
        assert resp.status_code == 200

        reader = RebalanceRequestQueue(str(config.data_root / "rebalance_requests.db"))
        try:
            request = reader.pending_for("MSFT")
            assert request is not None
            assert request.reason == "unwind X"
        finally:
            reader.close()

    def test_missing_required_fields_is_a_422(self, client) -> None:
        test_client, _config = client
        resp = test_client.post("/live/trade-plan/rebalance-request", json={"symbol": "AAPL"})
        assert resp.status_code == 422
