"""Direct unit tests for apply_risk_gatekeeper_verdict's sizing math.

The hook is also exercised end-to-end through test_team.py's TeamManager
harness; these tests poke the one branch that harness doesn't vary --
Stage A (A17)'s final clamp of the sized dollar amount down to the hard
mandate ceiling.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from vinu_agent.agent.risk_gatekeeper_hook import apply_risk_gatekeeper_verdict
from vinu_agent.broker.mandate import TradingMandate
from vinu_research.models import Artifact, ArtifactStatus
from vinu_research.storage.strategy_store import SqliteStrategyStore


@pytest.fixture
def strategy_store():
    store = SqliteStrategyStore(Path(tempfile.mktemp(suffix=".db")))
    yield store
    store.close()


def _benching(store) -> str:
    artifact = Artifact.create("strategy", "AAPL-test", universe=["AAPL"])
    artifact.status = ArtifactStatus.BENCHING
    store.upsert_artifact(artifact)
    return artifact.artifact_id


def _content(artifact_id: str, *, approved_size: float, sizing_inputs: dict) -> str:
    import json

    block = {
        "verdict": "APPROVED",
        "artifact_id": artifact_id,
        "reason": "ok",
        "approved_size": approved_size,
        "sizing_inputs": sizing_inputs,
    }
    return f"```json\n{json.dumps(block)}\n```"


def test_size_is_clamped_to_the_mandate_ceiling(strategy_store, monkeypatch) -> None:
    # fixed_fractional at 80% of 100k equity -> formula wants 80,000.
    # Mandate ceiling: min(max_position_pct * equity, max_order_value)
    #                = min(0.25 * 100_000, 50_000) = 25,000.
    monkeypatch.setattr(
        TradingMandate, "load",
        classmethod(lambda cls: cls(max_position_pct=0.25, max_order_value=50_000.0)),
    )
    artifact_id = _benching(strategy_store)
    content = _content(
        artifact_id,
        approved_size=90_000.0,
        sizing_inputs={
            "account_equity": 100_000.0,
            "method": "fixed_fractional",
            "risk_pct": 0.8,
        },
    )

    returned = apply_risk_gatekeeper_verdict(content, strategy_store=strategy_store)
    assert returned == artifact_id

    updated = strategy_store.get_artifact(artifact_id)
    assert updated.status == ArtifactStatus.PEND
    assert updated.approved_size == pytest.approx(25_000.0)


def test_size_below_ceiling_passes_through_untouched(strategy_store, monkeypatch) -> None:
    monkeypatch.setattr(
        TradingMandate, "load",
        classmethod(lambda cls: cls(max_position_pct=0.25, max_order_value=50_000.0)),
    )
    artifact_id = _benching(strategy_store)
    content = _content(
        artifact_id,
        approved_size=20_000.0,
        sizing_inputs={
            "account_equity": 100_000.0,
            "method": "fixed_fractional",
            "risk_pct": 0.1,  # -> 10,000, and min(20k, 10k) = 10k, under the 25k ceiling
        },
    )

    apply_risk_gatekeeper_verdict(content, strategy_store=strategy_store)
    updated = strategy_store.get_artifact(artifact_id)
    assert updated.approved_size == pytest.approx(10_000.0)


def test_clamp_failure_is_swallowed_and_leaves_size_to_orderguard(strategy_store, monkeypatch) -> None:
    def _boom(cls):
        raise RuntimeError("no mandate file")

    monkeypatch.setattr(TradingMandate, "load", classmethod(_boom))
    artifact_id = _benching(strategy_store)
    content = _content(
        artifact_id,
        approved_size=90_000.0,
        sizing_inputs={
            "account_equity": 100_000.0,
            "method": "fixed_fractional",
            "risk_pct": 0.8,
        },
    )

    # Must not raise -- the clamp is best-effort, OrderGuard is the real gate.
    returned = apply_risk_gatekeeper_verdict(content, strategy_store=strategy_store)
    assert returned == artifact_id
    updated = strategy_store.get_artifact(artifact_id)
    # Unclamped: min(approved_size 90k, formula 80k) = 80k.
    assert updated.approved_size == pytest.approx(80_000.0)
