"""Tests for SyncService's vinu-research call sites (sync_research,
sync_artifacts) -- migrated to try vinu-research's real local stores
in-process first, falling back to HTTP only if that raises. See
vinu_agent/broker/research_link.py and component-consolidation-plan.md.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from vinu_research.models import Artifact, ArtifactStatus
from vinu_research.storage.models import STATUS_DONE, ResearchRunRecord
from vinu_research.storage.sqlite_backend import ResearchStorage
from vinu_research.storage.strategy_store import SqliteStrategyStore

from vinu_agent.memory.sync_service import SyncService
from vinu_agent.memory.unified_store import UnifiedMemoryStore


@pytest.fixture
def store():
    s = UnifiedMemoryStore(":memory:")
    yield s
    s.close()


@pytest.fixture
def research_storage(tmp_path):
    return ResearchStorage(tmp_path / "research_meta.db")


@pytest.fixture
def strategy_store(tmp_path):
    return SqliteStrategyStore(tmp_path / "strategy_store.db")


class TestSyncResearchInProcess:
    @pytest.mark.asyncio
    async def test_syncs_real_runs_from_local_storage(self, store, research_storage):
        research_storage.insert_run(ResearchRunRecord(
            user_idea="mean reversion", symbol="AAPL", from_date="2024-01-01",
            to_date="2024-06-01", status=STATUS_DONE, best_sharpe=1.5,
        ))
        svc = SyncService(store, {})
        with patch("vinu_agent.broker.research_link.get_research_storage", return_value=research_storage):
            count = await svc.sync_research("AAPL")

        assert count == 1
        entries = store.recent_entries(source="research")
        assert len(entries) == 1
        assert "AAPL" in entries[0].symbol

    @pytest.mark.asyncio
    async def test_falls_back_to_http_when_in_process_raises(self, store):
        svc = SyncService(store, {"vinu_research": "http://research:8087"})
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{
            "id": 7, "symbol": "MSFT", "user_idea": "breakout", "best_sharpe": 1.1,
            "best_max_dd": -0.1, "status": "done",
        }]
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = False

        with patch(
            "vinu_agent.broker.research_link.get_research_storage",
            side_effect=RuntimeError("no local db"),
        ), patch("httpx.AsyncClient", return_value=mock_client):
            count = await svc.sync_research("MSFT")

        assert count == 1
        entries = store.recent_entries(source="research")
        assert entries[0].symbol == "MSFT"

    @pytest.mark.asyncio
    async def test_both_paths_failing_returns_zero(self, store):
        svc = SyncService(store, {"vinu_research": "http://research:8087"})
        with patch(
            "vinu_agent.broker.research_link.get_research_storage",
            side_effect=RuntimeError("no local db"),
        ), patch("httpx.AsyncClient", side_effect=RuntimeError("network down")):
            count = await svc.sync_research("MSFT")
        assert count == 0


class TestSyncArtifactsInProcess:
    @pytest.mark.asyncio
    async def test_syncs_real_active_and_monitoring_artifacts(self, store, strategy_store):
        active = Artifact.create("strategy", "s1", universe=["AAPL"])
        active.status = ArtifactStatus.ACTIVE
        active.initial_sharpe = 1.2
        strategy_store.upsert_artifact(active)
        benching = Artifact.create("strategy", "s2", universe=["MSFT"])
        benching.status = ArtifactStatus.BENCHING
        strategy_store.upsert_artifact(benching)

        svc = SyncService(store, {})
        with patch("vinu_agent.broker.research_link.get_strategy_store", return_value=strategy_store):
            count = await svc.sync_artifacts()

        assert count == 1
        entries = store.recent_entries(source="research")
        assert entries[0].metadata["artifact_id"] == active.artifact_id

    @pytest.mark.asyncio
    async def test_falls_back_to_http_when_in_process_raises(self, store):
        svc = SyncService(store, {"vinu_research": "http://research:8087"})
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{
            "artifact_id": "art_1", "universe": ["NVDA"], "initial_sharpe": 2.0, "status": "ACTIVE",
        }]
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = False

        with patch(
            "vinu_agent.broker.research_link.get_strategy_store",
            side_effect=RuntimeError("no local db"),
        ), patch("httpx.AsyncClient", return_value=mock_client):
            count = await svc.sync_artifacts()

        assert count == 1
        entries = store.recent_entries(source="research")
        assert entries[0].metadata["artifact_id"] == "art_1"
