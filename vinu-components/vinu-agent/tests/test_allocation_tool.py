"""Tests for ComputeAllocationCandidatesTool -- Phase 2's PEND-batch,
vinu-portfolio-backed funding decision. See
vinu_agent/tools/allocation_tool.py's module docstring, and New-talk-agents/
new-thinking/new-restructure/phases/phase-2-funding-mechanics/.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.tools.allocation_tool import ComputeAllocationCandidatesTool
from vinu_research.models import Artifact
from vinu_research.storage.strategy_store import SqliteStrategyStore


@pytest.fixture
def strategy_store():
    store_path = Path(tempfile.mktemp(suffix=".db"))
    store = SqliteStrategyStore(store_path)
    yield store
    store.close()
    store_path.unlink(missing_ok=True)


def _pend_artifact(strategy_store: SqliteStrategyStore, name: str, approved_size: float) -> str:
    artifact = Artifact.create("strategy", name, universe=[name.split("-")[0]])
    strategy_store.upsert_artifact(artifact)
    strategy_store.mark_benching(artifact.artifact_id)
    strategy_store.mark_pend(artifact.artifact_id, approved_size=approved_size)
    return artifact.artifact_id


def _tool(strategy_store) -> ComputeAllocationCandidatesTool:
    tool = ComputeAllocationCandidatesTool()
    tool._strategy_store = strategy_store
    return tool


def _portfolio_resp(weights: list[dict]) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"status": "ok", "weights": weights}
    return resp


class TestComputeAllocationCandidatesTool:
    def test_no_strategy_store_errors(self) -> None:
        tool = ComputeAllocationCandidatesTool()
        result = json.loads(tool.execute(artifact_ids=["art_1"], budget=1000))
        assert result["status"] == "error"

    def test_nonpositive_budget_errors(self, strategy_store) -> None:
        result = json.loads(_tool(strategy_store).execute(artifact_ids=[], budget=0))
        assert result["status"] == "error"

    def test_unknown_artifact_id_rejected(self, strategy_store) -> None:
        with patch("httpx.post") as mock_post:
            result = json.loads(_tool(strategy_store).execute(artifact_ids=["art_nope"], budget=1000))
        mock_post.assert_not_called()  # nothing to send -- no real candidates
        [c] = result["candidates"]
        assert c["funded"] is False
        assert "not found" in c["reason"]

    def test_non_pend_artifact_rejected(self, strategy_store) -> None:
        artifact = Artifact.create("strategy", "AAPL-created")
        strategy_store.upsert_artifact(artifact)
        result = json.loads(_tool(strategy_store).execute(artifact_ids=[artifact.artifact_id], budget=1000))
        [c] = result["candidates"]
        assert c["funded"] is False
        assert "not PEND" in c["reason"]

    def test_single_candidate_funded_at_portfolio_weight_capped_by_approved_size(self, strategy_store) -> None:
        artifact_id = _pend_artifact(strategy_store, "AAPL-x", approved_size=50_000.0)
        with patch("httpx.post", return_value=_portfolio_resp(
            [{"artifact_id": artifact_id, "target_weight": 0.3}]
        )) as mock_post:
            result = json.loads(_tool(strategy_store).execute(artifact_ids=[artifact_id], budget=100_000))

        assert mock_post.call_args[0][0].endswith("/portfolio/evaluate-batch")
        [c] = result["candidates"]
        assert c["funded"] is True
        assert c["amount"] == pytest.approx(30_000.0)  # 0.3 * 100_000, under the 50k cap
        assert result["remaining_unallocated"] == pytest.approx(70_000.0)

    def test_funding_never_exceeds_gatekeeper_approved_size(self, strategy_store) -> None:
        """vinu-portfolio (mocked) returns a weight implying MORE than
        risk_gatekeeper approved -- funded amount must be capped at the
        smaller, originally-approved size, never expanded."""
        artifact_id = _pend_artifact(strategy_store, "AAPL-y", approved_size=10_000.0)
        with patch("httpx.post", return_value=_portfolio_resp(
            [{"artifact_id": artifact_id, "target_weight": 0.5}]  # 0.5 * 100_000 = 50_000, way over approved
        )):
            result = json.loads(_tool(strategy_store).execute(artifact_ids=[artifact_id], budget=100_000))
        [c] = result["candidates"]
        assert c["funded"] is True
        assert c["amount"] == pytest.approx(10_000.0)

    def test_funding_uses_smaller_portfolio_computed_size(self, strategy_store) -> None:
        artifact_id = _pend_artifact(strategy_store, "AAPL-z", approved_size=50_000.0)
        with patch("httpx.post", return_value=_portfolio_resp(
            [{"artifact_id": artifact_id, "target_weight": 0.05}]  # 5_000, under the 50k cap
        )):
            result = json.loads(_tool(strategy_store).execute(artifact_ids=[artifact_id], budget=100_000))
        [c] = result["candidates"]
        assert c["funded"] is True
        assert c["amount"] == pytest.approx(5_000.0)

    def test_vinu_portfolio_unreachable_skips_funding_never_falls_back(self, strategy_store) -> None:
        artifact_id = _pend_artifact(strategy_store, "AAPL-w", approved_size=10_000.0)
        with patch("httpx.post", side_effect=ConnectionError("refused")):
            result = json.loads(_tool(strategy_store).execute(artifact_ids=[artifact_id], budget=100_000))
        assert result["status"] == "error"
        assert "unreachable" in result["error"]
        assert "candidates" not in result  # never a fixed-fraction fallback result

    def test_candidate_missing_from_portfolio_weights_not_funded(self, strategy_store) -> None:
        artifact_id = _pend_artifact(strategy_store, "AAPL-v", approved_size=10_000.0)
        with patch("httpx.post", return_value=_portfolio_resp([])):  # empty weights list
            result = json.loads(_tool(strategy_store).execute(artifact_ids=[artifact_id], budget=100_000))
        [c] = result["candidates"]
        assert c["funded"] is False
        assert "not present" in c["reason"]

    def test_batch_sent_in_one_call_for_multiple_candidates(self, strategy_store) -> None:
        id_a = _pend_artifact(strategy_store, "AAA-a", approved_size=50_000.0)
        id_b = _pend_artifact(strategy_store, "BBB-b", approved_size=50_000.0)
        with patch("httpx.post", return_value=_portfolio_resp([
            {"artifact_id": id_a, "target_weight": 0.2},
            {"artifact_id": id_b, "target_weight": 0.1},
        ])) as mock_post:
            result = json.loads(_tool(strategy_store).execute(artifact_ids=[id_a, id_b], budget=100_000))

        assert mock_post.call_count == 1  # one call for the whole batch, not one per candidate
        sent_payload = mock_post.call_args[1]["json"]
        assert {c["artifact_id"] for c in sent_payload["candidates"]} == {id_a, id_b}
        by_id = {c["artifact_id"]: c for c in result["candidates"]}
        assert by_id[id_a]["amount"] == pytest.approx(20_000.0)
        assert by_id[id_b]["amount"] == pytest.approx(10_000.0)
