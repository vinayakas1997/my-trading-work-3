"""item #8: GET /indicators/pool, the read-only HTTP surface over
HypothesisRegistry.pool_evidence_by_indicator() -- whether a supporting
indicator matters in general, across every strategy/hypothesis that used
it, not siloed per-strategy."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import vinu_research.hypothesis_registry as hr
from vinu_research.hypothesis_registry import HypothesisRegistry
from vinu_research.models import Evidence, Hypothesis
from vinu_research.server.app import create_app


@pytest.fixture
def client(monkeypatch):
    tmp = Path(tempfile.mkdtemp()) / "hyp.json"
    monkeypatch.setattr(hr, "HYPOTHESES_PATH", tmp)
    from unittest.mock import MagicMock
    svc = MagicMock()
    app = create_app(service=svc)
    return TestClient(app), tmp


def test_empty_registry_returns_empty_pool(client) -> None:
    test_client, _ = client
    resp = test_client.get("/research/indicators/pool")
    assert resp.status_code == 200
    assert resp.json() == {"indicators": {}}


def test_pools_across_hypotheses_sharing_an_indicator(client) -> None:
    test_client, hyp_path = client
    reg = HypothesisRegistry(hyp_path)
    h1 = Hypothesis.create("Momentum", "Momentum strategy", universe=["AAPL"])
    h1.indicators_used = ["adx_gt_25"]
    h2 = Hypothesis.create("Breakout", "Breakout strategy", universe=["MSFT"])
    h2.indicators_used = ["adx_gt_25"]
    reg.create(h1)
    reg.create(h2)
    reg.add_evidence_batch(h1.hypothesis_id, [
        Evidence(run_id=1, iteration=1, metric="sharpe", value=0.6, conclusion="supports", reasoning="r"),
    ])
    reg.add_evidence_batch(h2.hypothesis_id, [
        Evidence(run_id=1, iteration=1, metric="sharpe", value=0.2, conclusion="contradicts", reasoning="r"),
    ])

    resp = test_client.get("/research/indicators/pool")
    assert resp.status_code == 200
    body = resp.json()["indicators"]["adx_gt_25"]["sharpe"]
    assert body["evidence_count"] == 2
    assert body["hypothesis_count"] == 2
    assert body["support_rate"] == pytest.approx(0.5)
