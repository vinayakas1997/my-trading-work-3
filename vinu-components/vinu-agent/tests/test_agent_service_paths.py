"""Contract: every HTTP fallback in the agent's memory sync and portfolio-comparison tool calls the path the target service really
serves. The configured service URLs are bare hosts (`VINU_RESEARCH_API_URL=http://research-api:8087`), so each call must add the
service's own prefix (`/research/...`, `/simulator/...`, `/news/...`, `/portfolio/...`). Before 2026-10-04 six calls omitted it
and answered 404 whenever the in-process path was unavailable (separate containers). The earlier tests mocked `get` without
looking at the URL, which is why this went unnoticed."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vinu_agent.memory.sync_service import SyncService
from vinu_agent.memory.unified_store import UnifiedMemoryStore
from vinu_agent.tools.portfolio_comparison_tool import PortfolioComparisonTool

BASES = {
    "vinu_research": "http://research-api:8087",
    "vinu_simulator": "http://quant-core-api:8084",
    "vinu_news": "http://news-api:8080",
}


def _client(body):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = body
    client = AsyncMock()
    client.get.return_value = resp
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False
    return client


@pytest.fixture
def store():
    s = UnifiedMemoryStore(":memory:")
    yield s
    s.close()


def _urls(client) -> list[str]:
    return [c.args[0] for c in client.get.call_args_list]


@pytest.mark.asyncio
async def test_sync_research_http_fallback_uses_the_research_prefix(store):
    client = _client([])
    with patch("vinu_agent.broker.research_link.get_research_storage", side_effect=RuntimeError("no local db")), \
         patch("httpx.AsyncClient", return_value=client):
        await SyncService(store, BASES).sync_research("AAPL")
    assert _urls(client) == ["http://research-api:8087/research/runs"]


@pytest.mark.asyncio
async def test_sync_artifacts_http_fallback_uses_the_research_prefix(store):
    client = _client([])
    with patch("vinu_agent.broker.research_link.get_strategy_store", side_effect=RuntimeError("no local db"), create=True), \
         patch("httpx.AsyncClient", return_value=client):
        await SyncService(store, BASES).sync_artifacts()
    assert "http://research-api:8087/research/artifacts" in _urls(client)


@pytest.mark.asyncio
async def test_sync_simulator_uses_the_simulator_prefix(store):
    client = _client([])
    with patch("httpx.AsyncClient", return_value=client):
        await SyncService(store, BASES).sync_simulator("AAPL")
    assert _urls(client) == ["http://quant-core-api:8084/simulator/runs"]


@pytest.mark.asyncio
async def test_sync_news_uses_the_news_prefix(store):
    client = _client({"data": []})
    with patch("httpx.AsyncClient", return_value=client):
        await SyncService(store, BASES).sync_news("AAPL")
    assert _urls(client) == ["http://news-api:8080/news/ticker/AAPL"]


@pytest.mark.asyncio
async def test_portfolio_comparison_reads_the_portfolio_state_route():
    client = _client({"status": "ok", "weights": []})
    await PortfolioComparisonTool()._fetch_portfolio(client, "http://portfolio-api:8090")
    assert _urls(client) == ["http://portfolio-api:8090/portfolio/state"]


@pytest.mark.asyncio
async def test_portfolio_comparison_artifact_fallback_uses_the_research_prefix():
    client = _client([])
    with patch("vinu_agent.broker.research_link.get_strategy_store", side_effect=RuntimeError("no local db"), create=True), \
         patch("httpx.AsyncClient", return_value=client):
        await PortfolioComparisonTool()._fetch_artifacts("http://research-api:8087")
    assert _urls(client) == ["http://research-api:8087/research/artifacts"]
