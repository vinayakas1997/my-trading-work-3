"""Tests for PortfolioComparisonTool's vinu-research artifact fetch
(_fetch_artifacts) -- migrated to try the real local strategy_store
in-process first, falling back to HTTP only if that raises. See
vinu_agent/broker/research_link.py.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vinu_agent.tools.portfolio_comparison_tool import PortfolioComparisonTool
from vinu_research.models import Artifact, ArtifactStatus
from vinu_research.storage.strategy_store import SqliteStrategyStore


def _tool(services_config: dict | None = None) -> PortfolioComparisonTool:
    tool = PortfolioComparisonTool()
    tool._services_config = services_config or {}
    return tool


def _force_in_process_unavailable():
    return patch(
        "vinu_agent.broker.research_link.get_strategy_store",
        side_effect=RuntimeError("not available"),
    )


@pytest.fixture
def strategy_store(tmp_path) -> SqliteStrategyStore:
    return SqliteStrategyStore(tmp_path / "strategy_store.db")


def _mock_portfolio_client(status_code=200, body=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body or {"status": "ok", "n_strategies": 0, "weights": []}
    client = AsyncMock()
    client.get.return_value = resp
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False
    return client


class TestFetchArtifactsInProcess:
    @pytest.mark.asyncio
    async def test_reads_real_active_artifacts(self, strategy_store) -> None:
        active = Artifact.create("strategy", "s1", universe=["AAPL"])
        active.status = ArtifactStatus.ACTIVE
        strategy_store.upsert_artifact(active)
        rejected = Artifact.create("strategy", "s2", universe=["MSFT"])
        rejected.status = ArtifactStatus.DISABLED
        strategy_store.upsert_artifact(rejected)

        with patch("vinu_agent.broker.research_link.get_strategy_store", return_value=strategy_store):
            artifacts = await _tool()._fetch_artifacts("http://research-api:8087")

        assert len(artifacts) == 1
        assert artifacts[0]["artifact_id"] == active.artifact_id

    @pytest.mark.asyncio
    async def test_falls_back_to_http_when_in_process_raises(self) -> None:
        with _force_in_process_unavailable(), patch("httpx.AsyncClient", return_value=_mock_portfolio_client(
            body=[{"artifact_id": "art_1", "status": "ACTIVE"}],
        )):
            artifacts = await _tool()._fetch_artifacts("http://research-api:8087")
        assert artifacts == [{"artifact_id": "art_1", "status": "ACTIVE"}]


class TestFetchArtifactsHttpFallback:
    @pytest.mark.asyncio
    async def test_non_200_returns_empty(self) -> None:
        with _force_in_process_unavailable(), patch(
            "httpx.AsyncClient", return_value=_mock_portfolio_client(status_code=500),
        ):
            artifacts = await _tool()._fetch_artifacts("http://research-api:8087")
        assert artifacts == []

    @pytest.mark.asyncio
    async def test_exception_returns_empty(self) -> None:
        client = AsyncMock()
        client.get.side_effect = ConnectionError("down")
        client.__aenter__.return_value = client
        client.__aexit__.return_value = False
        with _force_in_process_unavailable(), patch("httpx.AsyncClient", return_value=client):
            artifacts = await _tool()._fetch_artifacts("http://research-api:8087")
        assert artifacts == []


class TestExecuteAsyncEndToEnd:
    @pytest.mark.asyncio
    async def test_json_format_combines_portfolio_and_artifacts(self, strategy_store) -> None:
        active = Artifact.create("strategy", "s1", universe=["AAPL"])
        active.status = ArtifactStatus.ACTIVE
        strategy_store.upsert_artifact(active)

        tool = _tool({"vinu_portfolio": "http://portfolio-api:8090"})
        with patch(
            "vinu_agent.broker.research_link.get_strategy_store", return_value=strategy_store,
        ), patch("httpx.AsyncClient", return_value=_mock_portfolio_client()):
            result = json.loads(await tool.execute_async(format="json"))

        assert result["portfolio"]["status"] == "ok"
        assert len(result["artifacts"]) == 1
