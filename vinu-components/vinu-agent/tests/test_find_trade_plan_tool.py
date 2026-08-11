import json
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.tools.find_trade_plan_tool import FindTradePlanArtifactTool
from vinu_research.models import Artifact
from vinu_research.storage.strategy_store import SqliteStrategyStore


def _tool() -> FindTradePlanArtifactTool:
    return FindTradePlanArtifactTool()


def _resp(json_body):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = json_body
    return resp


def _force_in_process_unavailable():
    return patch(
        "vinu_agent.broker.research_link.get_strategy_store",
        side_effect=RuntimeError("not available"),
    )


@pytest.fixture
def strategy_store(tmp_path) -> SqliteStrategyStore:
    return SqliteStrategyStore(tmp_path / "strategy_store.db")


class TestFindTradePlanArtifactToolInProcess:
    def test_finds_real_trade_plan_artifact_by_universe(self, strategy_store) -> None:
        plan = Artifact.create("trade_plan", "plan-aapl", universe=["AAPL"])
        strategy_store.upsert_artifact(plan)
        other = Artifact.create("strategy", "s-msft", universe=["MSFT"])
        strategy_store.upsert_artifact(other)

        with patch("vinu_agent.broker.research_link.get_strategy_store", return_value=strategy_store):
            result = json.loads(_tool().execute(symbol="aapl"))

        assert result["status"] == "ok"
        assert result["artifact_id"] == plan.artifact_id

    def test_type_filter_excludes_non_trade_plan_artifacts(self, strategy_store) -> None:
        strategy = Artifact.create("strategy", "s-aapl", universe=["AAPL"])
        strategy_store.upsert_artifact(strategy)

        with patch("vinu_agent.broker.research_link.get_strategy_store", return_value=strategy_store):
            result = json.loads(_tool().execute(symbol="AAPL"))

        assert result["status"] == "not_found"

    def test_falls_back_to_http_when_in_process_raises(self) -> None:
        artifacts = [{"artifact_id": "art_1", "universe": ["AAPL"], "status": "ACTIVE"}]
        with _force_in_process_unavailable(), patch("httpx.get", return_value=_resp(artifacts)):
            result = json.loads(_tool().execute(symbol="aapl"))
        assert result["status"] == "ok"
        assert result["artifact_id"] == "art_1"


class TestFindTradePlanArtifactToolHttpFallback:
    def test_finds_matching_artifact_by_universe(self) -> None:
        artifacts = [
            {"artifact_id": "art_1", "universe": ["AAPL"], "status": "ACTIVE"},
            {"artifact_id": "art_2", "universe": ["MSFT"], "status": "ACTIVE"},
        ]
        with _force_in_process_unavailable(), patch("httpx.get", return_value=_resp(artifacts)):
            result = json.loads(_tool().execute(symbol="aapl"))
        assert result["status"] == "ok"
        assert result["artifact_id"] == "art_1"

    def test_no_matching_artifact_returns_not_found(self) -> None:
        with _force_in_process_unavailable(), patch(
            "httpx.get", return_value=_resp([{"artifact_id": "art_1", "universe": ["MSFT"], "status": "ACTIVE"}]),
        ):
            result = json.loads(_tool().execute(symbol="AAPL"))
        assert result["status"] == "not_found"

    def test_both_transports_unavailable_reports_error_not_raised(self) -> None:
        with _force_in_process_unavailable(), patch("httpx.get", side_effect=ConnectionError("down")):
            result = json.loads(_tool().execute(symbol="AAPL"))
        assert result["status"] == "error"

    def test_requests_trade_plan_type_only(self) -> None:
        with _force_in_process_unavailable(), patch("httpx.get", return_value=_resp([])) as mock_get:
            _tool().execute(symbol="AAPL")
        assert mock_get.call_args[1]["params"] == {"type_": "trade_plan"}
