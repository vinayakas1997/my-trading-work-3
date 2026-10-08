"""Contract: the agent reads the news service's answer in the shape the service really sends.

vinu-news sends `{"count": n, "data": [article, ...]}` with times as unix seconds. Two readers (memory sync, trade-plan news
section) looked for `results` / `articles` and sliced the time as text, so every ticker looked like "no news" and the first
real article would have crashed the page. Their older tests mocked a bare list. The article below is a real row's shape."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from vinu_agent.memory.sync_service import SyncService
from vinu_agent.memory.unified_store import UnifiedMemoryStore
from vinu_agent.news_payload import article_date, news_articles
from vinu_agent.tools.trade_plan_tool import TradePlanTool

ARTICLE = {
    "id": "56a108ef", "headline": "Why is AbbVie (ABBV) Stock Trending After Hours?", "summary": "Shares moved.",
    "source": "BENZINGA", "link": "https://example.test/abbv", "sort_ts": 1791427951, "published_at": 1791427951,
    "sentiment": "BULLISH", "sentiment_score": 4, "impact": "MEDIUM", "tier": 2,
}
SERVICE_BODY = {"count": 1, "data": [ARTICLE]}


def test_the_service_answer_shape_is_read():
    assert news_articles(SERVICE_BODY) == [ARTICLE]
    assert news_articles([ARTICLE]) == [ARTICLE]
    assert news_articles({"count": 0, "data": []}) == []
    assert news_articles("nope") == [] and news_articles(None) == []


def test_unix_seconds_become_a_date_and_strings_are_kept():
    assert article_date(ARTICLE) == "2026-10-08"
    assert article_date({"date": "2026-07-25T10:00:00"}) == "2026-07-25"
    assert article_date({}) == "—"


def test_trade_plan_news_section_sees_the_services_articles():
    tool = TradePlanTool()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=SERVICE_BODY)

    async def run() -> dict:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://news.test") as client:
            return await tool._fetch_news(client, "http://news.test", "ABBV")

    result = asyncio.run(run())
    assert result["status"] == "available" and len(result["articles"]) == 1

    lines: list[str] = []
    tool._render_news_sensitivity(lines, result)          # an integer time must not crash the page
    text = "\n".join(lines)
    assert "2026-10-08" in text and "AbbVie" in text and "BENZINGA" in text


@pytest.mark.asyncio
async def test_memory_sync_stores_the_services_articles():
    store = UnifiedMemoryStore(":memory:")
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = SERVICE_BODY
    client = AsyncMock()
    client.get.return_value = resp
    client.__aenter__.return_value = client
    with patch("httpx.AsyncClient", return_value=client):
        count = await SyncService(store, {"vinu_news": "http://news-api:8080"}).sync_news("ABBV")
    assert count == 1


def test_trade_plan_asks_for_the_tickers_newest_news_not_a_relevance_search():
    """/news/search ranks by text relevance, so for AAPL the plan showed 2023 headlines. The ticker route is newest first."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=SERVICE_BODY)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await TradePlanTool()._fetch_news(client, "http://news.test", "ABBV")

    asyncio.run(run())
    assert seen[0].url.path == "/news/ticker/ABBV" and "q" not in seen[0].url.params
