"""Tests for ListActiveArtifactsForRebalanceTool -- read-only context for
capital_allocator's rebalancer role. See
vinu_agent/tools/rebalance_context_tool.py's module docstring.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from vinu_agent.tools.rebalance_context_tool import ListActiveArtifactsForRebalanceTool
from vinu_research.models import Artifact
from vinu_research.storage.strategy_store import SqliteStrategyStore


@pytest.fixture
def strategy_store():
    store_path = Path(tempfile.mktemp(suffix=".db"))
    store = SqliteStrategyStore(store_path)
    yield store
    store.close()
    store_path.unlink(missing_ok=True)


def _active_artifact(strategy_store: SqliteStrategyStore, symbol: str, approved_size: float = 20000.0) -> str:
    artifact = Artifact.create("strategy", f"{symbol}-test", universe=[symbol])
    strategy_store.upsert_artifact(artifact)
    strategy_store.mark_benching(artifact.artifact_id)
    strategy_store.mark_pend(artifact.artifact_id, approved_size=approved_size)
    with patch("vinu_agent.broker.kill_switch.is_trading_halted", return_value=False):
        strategy_store.mark_active(artifact.artifact_id)
    return artifact.artifact_id


def _tool(strategy_store) -> ListActiveArtifactsForRebalanceTool:
    tool = ListActiveArtifactsForRebalanceTool()
    tool._strategy_store = strategy_store
    return tool


class TestListActiveArtifactsForRebalanceTool:
    def test_no_strategy_store_configured_is_an_error(self) -> None:
        tool = ListActiveArtifactsForRebalanceTool()
        result = json.loads(tool.execute())
        assert result["status"] == "error"

    def test_lists_active_artifacts_with_calibration(self, strategy_store) -> None:
        artifact_id = _active_artifact(strategy_store, "AAPL", approved_size=15000.0)
        calibration = {"artifact_id": artifact_id, "n_entries": 12, "passed": True, "reasons": [], "source": "in_process"}

        with patch(
            "vinu_agent.agent.trade_plan_calibration.get_trade_plan_calibration", return_value=calibration,
        ):
            result = json.loads(_tool(strategy_store).execute())

        assert result["status"] == "ok"
        assert len(result["active_artifacts"]) == 1
        entry = result["active_artifacts"][0]
        assert entry["artifact_id"] == artifact_id
        assert entry["symbol"] == "AAPL"
        assert entry["approved_size"] == 15000.0
        assert entry["calibration"] == calibration

    def test_only_active_artifacts_are_listed(self, strategy_store) -> None:
        """A PEND artifact (never funded) has no real position to unwind
        -- must not appear here."""
        artifact = Artifact.create("strategy", "MSFT-test", universe=["MSFT"])
        strategy_store.upsert_artifact(artifact)
        strategy_store.mark_benching(artifact.artifact_id)
        strategy_store.mark_pend(artifact.artifact_id, approved_size=5000.0)

        with patch("vinu_agent.agent.trade_plan_calibration.get_trade_plan_calibration", return_value={}):
            result = json.loads(_tool(strategy_store).execute())

        assert result["active_artifacts"] == []

    def test_tickers_filter_restricts_results(self, strategy_store) -> None:
        _active_artifact(strategy_store, "AAPL")
        _active_artifact(strategy_store, "MSFT")

        with patch("vinu_agent.agent.trade_plan_calibration.get_trade_plan_calibration", return_value={}):
            result = json.loads(_tool(strategy_store).execute(tickers=["AAPL"]))

        assert len(result["active_artifacts"]) == 1
        assert result["active_artifacts"][0]["symbol"] == "AAPL"

    def test_no_tickers_filter_returns_every_active_artifact(self, strategy_store) -> None:
        _active_artifact(strategy_store, "AAPL")
        _active_artifact(strategy_store, "MSFT")

        with patch("vinu_agent.agent.trade_plan_calibration.get_trade_plan_calibration", return_value={}):
            result = json.loads(_tool(strategy_store).execute())

        assert {e["symbol"] for e in result["active_artifacts"]} == {"AAPL", "MSFT"}
