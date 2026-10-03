"""Tests for GET /live/decision-context/{ticker}/{strategy_id} --
point 5's read side (reverse-engineering/
05-deciding-agent-and-precondition-tracking.md Part A). Same
TestClient + load_config patch pattern test_app.py already uses.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from vinu_live.config import LiveConfig
from vinu_live.live_decision import state_tracker
from vinu_live.live_decision.storage import LiveDecisionBackend
from vinu_live.server.app import create_app


@pytest.fixture
def client(tmp_path):
    config = LiveConfig(data_root=tmp_path)
    with patch("vinu_live.server.app.load_config", return_value=config):
        app = create_app()
        yield TestClient(app), config


class TestDecisionContextRoute:
    def test_unseen_pair_returns_idle_not_404(self, client) -> None:
        test_client, _config = client
        resp = test_client.get("/live/decision-context/AAPL/sma_cross")
        assert resp.status_code == 200
        body = resp.json()
        assert body["stage"] == "idle"
        assert body["trigger_id"] is None
        assert body["live_snapshot"] == {}

    def test_reflects_a_real_fired_state_and_snapshot(self, client) -> None:
        test_client, config = client
        backend = LiveDecisionBackend(str(config.data_root / "live_decision.db"))
        try:
            state_tracker.evaluate_candle_close(
                backend, ticker="AAPL", strategy_id="sma_cross", bar_ts=1000,
                timeframe_seconds=900,
                live_snapshot={"adx_14": 17.8, "sma_5_gt_sma_50": True},
                must_conditions=[{"source": "live_indicators", "key": "sma_5_gt_sma_50", "operator": "eq", "value": True}],
                confirmation_conditions=[],
                grace_window_bars=5,
            )
        finally:
            backend.close()

        resp = test_client.get("/live/decision-context/AAPL/sma_cross")
        assert resp.status_code == 200
        body = resp.json()
        assert body["stage"] == "ready_to_execute"
        assert body["trigger_id"] is not None
        assert body["live_snapshot"] == {"adx_14": 17.8, "sma_5_gt_sma_50": True}


class TestDecisionsHistoryRoute:
    """GET /live/decisions/{ticker}/{strategy_id} -- the "accessing" half
    of the fix that closed the gap where live_decision_agent's real
    verdicts were only logged, never kept anywhere queryable."""

    def test_no_recorded_decisions_returns_empty_not_an_error(self, client) -> None:
        test_client, _config = client
        resp = test_client.get("/live/decisions/AAPL/sma_cross")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["decisions"] == []

    def test_reflects_a_real_recorded_decision(self, client) -> None:
        test_client, config = client
        from vinu_live.live_decision.schema import LiveDecisionRecord
        from vinu_live.live_decision.storage import record_live_decision

        backend = LiveDecisionBackend(str(config.data_root / "live_decision.db"))
        try:
            record_live_decision(backend, LiveDecisionRecord(
                ticker="AAPL", strategy_id="sma_cross", trigger_id="trig_1", bar_ts=1000,
                decision="EXECUTE", precondition_held=True,
                reasoning="real evidence cited", raw_content="full content",
            ))
        finally:
            backend.close()

        resp = test_client.get("/live/decisions/AAPL/sma_cross")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["decisions"][0]["decision"] == "EXECUTE"
        assert body["decisions"][0]["precondition_held"] is True
        assert body["decisions"][0]["reasoning"] == "real evidence cited"


class TestDecisionContextNovelty:
    def test_novelty_is_none_until_the_check_has_run_then_the_latest_result(self, client, tmp_path) -> None:
        from vinu_live.live_decision.storage import record_live_snapshot

        test_client, _config = client
        assert test_client.get("/live/decision-context/AAPL/s").json()["novelty"] is None
        backend = LiveDecisionBackend(str(tmp_path / "live_decision.db"))
        record_live_snapshot(backend, symbol="AAPL", angle_name="live_novelty", granularity="1d",
                             snapshot_data={"status": "ok", "ratio": 3.0, "novelty_high": True})
        backend.close()
        assert test_client.get("/live/decision-context/AAPL/s").json()["novelty"]["novelty_high"] is True
