"""item #2 (system-wide-audit-and-design): `StrategyEvaluationStore`
already consolidates every gate a candidate passes through into one
current-state view (`status`/`rejected_at_step`/`rejected_reason`,
recomputed on every write) -- it just had no HTTP surface anywhere. These
are the new read-only routes for it, same "read access to state that
already existed" idiom as every other route in routes_introspect.py."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vinu_infra.strategy_evaluation import StrategyEvaluationStore
from vinu_research.server.app import create_app


@pytest.fixture
def client(service, tmp_path, monkeypatch):
    monkeypatch.setenv("VINU_STRATEGY_EVAL_DATA_ROOT", str(tmp_path))
    app = create_app(service)
    with TestClient(app) as test_client:
        yield test_client, tmp_path


def _eval_store(tmp_path) -> StrategyEvaluationStore:
    return StrategyEvaluationStore(tmp_path / "strategy_evaluation.db")


class TestGetEvaluationStatus:
    def test_unknown_artifact_is_404(self, client) -> None:
        test_client, _ = client
        resp = test_client.get("/research/evaluation-status/ghost-artifact")
        assert resp.status_code == 404

    def test_a_rejected_step_reports_the_real_status(self, client) -> None:
        test_client, tmp_path = client
        store = _eval_store(tmp_path)
        store.write_step_result(
            artifact_id="art-1", ticker="AAPL", step_name="risk_critic",
            step_order=1, verdict="PASS", reasoning="looked fine",
        )
        store.write_step_result(
            artifact_id="art-1", ticker="AAPL", step_name="correlation_gate",
            step_order=3, verdict="FAIL", reasoning="too correlated with active strategies",
        )

        resp = test_client.get("/research/evaluation-status/art-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "rejected"
        assert body["rejected_at_step"] == "correlation_gate"
        assert "too correlated" in body["rejected_reason"]


class TestListEvaluationStatusForTicker:
    def test_empty_ticker_returns_zero_count(self, client) -> None:
        test_client, _ = client
        resp = test_client.get("/research/evaluation-status/by-ticker/MSFT")
        assert resp.status_code == 200
        assert resp.json() == {"ticker": "MSFT", "count": 0, "statuses": []}

    def test_lists_every_artifact_evaluated_for_the_ticker(self, client) -> None:
        test_client, tmp_path = client
        store = _eval_store(tmp_path)
        store.write_step_result(
            artifact_id="art-1", ticker="AAPL", step_name="risk_critic",
            step_order=1, verdict="PASS", reasoning="ok",
        )
        store.write_step_result(
            artifact_id="art-2", ticker="AAPL", step_name="risk_critic",
            step_order=1, verdict="FAIL", reasoning="bad",
        )
        resp = test_client.get("/research/evaluation-status/by-ticker/aapl")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        assert {s["artifact_id"] for s in body["statuses"]} == {"art-1", "art-2"}


class TestGetEvaluationHistory:
    def test_unknown_artifact_returns_empty_history_not_404(self, client) -> None:
        # Unlike get_status (a derived summary that legitimately doesn't
        # exist yet), history is a plain list query -- an empty result is
        # the correct answer for an artifact nothing was ever written for.
        test_client, _ = client
        resp = test_client.get("/research/evaluation-history/ghost-artifact")
        assert resp.status_code == 200
        assert resp.json() == {"artifact_id": "ghost-artifact", "count": 0, "history": []}

    def test_returns_every_step_in_order(self, client) -> None:
        test_client, tmp_path = client
        store = _eval_store(tmp_path)
        store.write_step_result(
            artifact_id="art-1", ticker="AAPL", step_name="risk_critic",
            step_order=1, verdict="PASS", reasoning="ok",
        )
        store.write_step_result(
            artifact_id="art-1", ticker="AAPL", step_name="trade_score_gate",
            step_order=8, verdict="PASS", reasoning="tier clears minimum",
        )
        resp = test_client.get("/research/evaluation-history/art-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        assert [h["step_name"] for h in body["history"]] == ["risk_critic", "trade_score_gate"]
