"""Tests for `POST /artifacts/{id}/promote`'s strategy_evaluation wiring
and the real DISABLED-on-rejection fix (missing-pieces-of-system/
startegy-enhancer/02-implementation.md) -- a real, third call site for
`meets_promotion_bar()`/`correlation_gate` found while implementing the
K-cap fix, previously entirely unwired (and, it turned out, previously
untested at all)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vinu_research.models import Artifact, ArtifactStatus
from vinu_research.server.app import create_app


@pytest.fixture
def app(service):
    return create_app(service)


@pytest.fixture
def client(app):
    return TestClient(app)


def _benching_artifact(strategy_store, *, clears_bar: bool) -> str:
    artifact = Artifact.create("strategy", "AAPL-test", universe=["AAPL"])
    artifact.status = ArtifactStatus.BENCHING
    if clears_bar:
        artifact.deflated_sharpe = 1.5
        artifact.holdout_passed = True
        artifact.stress_test_passed = True
        artifact.pbo = 0.1
    strategy_store.upsert_artifact(artifact)
    return artifact.artifact_id


class TestPromoteRoutePersistsEvaluation:
    def test_passing_promotion_writes_pass_and_activates(self, client, strategy_store, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("VINU_STRATEGY_EVAL_DATA_ROOT", str(tmp_path))
        artifact_id = _benching_artifact(strategy_store, clears_bar=True)

        resp = client.post(f"/research/artifacts/{artifact_id}/promote")
        assert resp.status_code == 200
        assert strategy_store.get_artifact(artifact_id).status == ArtifactStatus.ACTIVE

        from vinu_infra.strategy_evaluation import StrategyEvaluationStore

        eval_store = StrategyEvaluationStore(tmp_path / "strategy_evaluation.db")
        rows = eval_store.get_history(artifact_id)
        promo = [r for r in rows if r["step_name"] == "promotion_bar"]
        assert len(promo) == 1
        assert promo[0]["verdict"] == "PASS"

    def test_failing_promotion_writes_fail_and_disables(self, client, strategy_store, tmp_path, monkeypatch) -> None:
        """Real fix: used to leave the artifact stuck in BENCHING forever
        (a real K-cap-blocking bug). Now DISABLED, a genuine terminal
        state -- deflated_sharpe/holdout/pbo are fixed, so a re-check
        would only ever reach the same verdict."""
        monkeypatch.setenv("VINU_STRATEGY_EVAL_DATA_ROOT", str(tmp_path))
        artifact_id = _benching_artifact(strategy_store, clears_bar=False)

        resp = client.post(f"/research/artifacts/{artifact_id}/promote")
        assert resp.status_code == 409
        assert strategy_store.get_artifact(artifact_id).status == ArtifactStatus.DISABLED

        from vinu_infra.strategy_evaluation import StrategyEvaluationStore

        eval_store = StrategyEvaluationStore(tmp_path / "strategy_evaluation.db")
        rows = eval_store.get_history(artifact_id)
        promo = [r for r in rows if r["step_name"] == "promotion_bar"]
        assert len(promo) == 1
        assert promo[0]["verdict"] == "FAIL"

    def test_forced_promotion_does_not_disable(self, client, strategy_store, tmp_path, monkeypatch) -> None:
        """force=true is a human override -- it must still activate the
        artifact, never leave it DISABLED despite the override succeeding."""
        monkeypatch.setenv("VINU_STRATEGY_EVAL_DATA_ROOT", str(tmp_path))
        artifact_id = _benching_artifact(strategy_store, clears_bar=False)

        resp = client.post(f"/research/artifacts/{artifact_id}/promote", params={"force": "true"})
        assert resp.status_code == 200
        assert strategy_store.get_artifact(artifact_id).status == ArtifactStatus.ACTIVE

    def test_unset_env_ships_inert(self, client, strategy_store, monkeypatch) -> None:
        monkeypatch.delenv("VINU_STRATEGY_EVAL_DATA_ROOT", raising=False)
        artifact_id = _benching_artifact(strategy_store, clears_bar=True)

        resp = client.post(f"/research/artifacts/{artifact_id}/promote")
        assert resp.status_code == 200
