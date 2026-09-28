"""Tests for GET /live/snapshots/{symbol} and
GET /live/snapshots/{symbol}/{angle_name}/history -- item #5's read side
(missing-pieces-of-system/new-theory-of-trading/system-wide-audit-and-
design/02-open-questions-strategy-and-simulation.md). Same TestClient +
load_config patch pattern test_decision_context_route.py already uses.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from vinu_live.config import LiveConfig
from vinu_live.live_decision.storage import LiveDecisionBackend, record_live_snapshot
from vinu_live.server.app import create_app


@pytest.fixture
def client(tmp_path):
    config = LiveConfig(data_root=tmp_path)
    with patch("vinu_live.server.app.load_config", return_value=config):
        app = create_app()
        yield TestClient(app), config


class TestSnapshotsRoute:
    def test_symbol_with_no_recorded_snapshots_returns_empty_angles(self, client) -> None:
        test_client, _config = client
        resp = test_client.get("/live/snapshots/AAPL")
        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "AAPL"
        assert body["angles"] == {}

    def test_returns_the_latest_recorded_angle_with_read_time_staleness(self, client) -> None:
        test_client, config = client
        backend = LiveDecisionBackend(str(config.data_root / "live_decision.db"))
        try:
            record_live_snapshot(
                backend, symbol="AAPL", angle_name="live_indicators", granularity="15m",
                snapshot_data={"adx_14": 17.8}, computed_at="2020-01-01T00:00:00+00:00",
            )
        finally:
            backend.close()

        resp = test_client.get("/live/snapshots/AAPL")

        assert resp.status_code == 200
        body = resp.json()
        angle = body["angles"]["live_indicators"]
        assert angle["granularity"] == "15m"
        assert angle["snapshot_data"] == {"adx_14": 17.8}
        assert angle["computed_at"] == "2020-01-01T00:00:00+00:00"
        # Not stored -- computed fresh at request time, so it's a large
        # positive number for a fixed past timestamp, not the literal
        # value any writer could have set.
        assert angle["staleness_seconds"] > 0

    def test_only_the_latest_row_is_returned_not_the_full_history(self, client) -> None:
        test_client, config = client
        backend = LiveDecisionBackend(str(config.data_root / "live_decision.db"))
        try:
            record_live_snapshot(
                backend, symbol="AAPL", angle_name="live_indicators", granularity="15m",
                snapshot_data={"adx_14": 10.0}, computed_at="2020-01-01T00:00:00+00:00",
            )
            record_live_snapshot(
                backend, symbol="AAPL", angle_name="live_indicators", granularity="15m",
                snapshot_data={"adx_14": 20.0}, computed_at="2026-09-28T12:15:00+00:00",
            )
        finally:
            backend.close()

        resp = test_client.get("/live/snapshots/AAPL")

        assert resp.json()["angles"]["live_indicators"]["snapshot_data"] == {"adx_14": 20.0}

    def test_symbol_is_case_insensitive(self, client) -> None:
        test_client, config = client
        backend = LiveDecisionBackend(str(config.data_root / "live_decision.db"))
        try:
            record_live_snapshot(
                backend, symbol="AAPL", angle_name="live_indicators", granularity="15m",
                snapshot_data={"adx_14": 10.0}, computed_at="2020-01-01T00:00:00+00:00",
            )
        finally:
            backend.close()

        resp = test_client.get("/live/snapshots/aapl")

        assert resp.status_code == 200
        assert resp.json()["symbol"] == "AAPL"
        assert "live_indicators" in resp.json()["angles"]


class TestSnapshotHistoryRoute:
    def test_unknown_symbol_returns_empty_history_not_404(self, client) -> None:
        test_client, _config = client
        resp = test_client.get("/live/snapshots/AAPL/live_indicators/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["snapshots"] == []

    def test_history_is_most_recent_first_with_per_row_staleness(self, client) -> None:
        test_client, config = client
        backend = LiveDecisionBackend(str(config.data_root / "live_decision.db"))
        try:
            record_live_snapshot(
                backend, symbol="AAPL", angle_name="live_indicators", granularity="15m",
                snapshot_data={"adx_14": 10.0}, computed_at="2020-01-01T00:00:00+00:00",
            )
            record_live_snapshot(
                backend, symbol="AAPL", angle_name="live_indicators", granularity="15m",
                snapshot_data={"adx_14": 20.0}, computed_at="2026-09-28T12:15:00+00:00",
            )
        finally:
            backend.close()

        resp = test_client.get("/live/snapshots/AAPL/live_indicators/history")

        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        assert body["snapshots"][0]["snapshot_data"] == {"adx_14": 20.0}
        assert body["snapshots"][1]["snapshot_data"] == {"adx_14": 10.0}
        assert all("staleness_seconds" in s for s in body["snapshots"])
