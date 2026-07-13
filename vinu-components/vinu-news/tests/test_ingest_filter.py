"""Tests for ticker-mode ingestion filtering with persist."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from vinu_news.analysis.storage.models import ArticleRecord, EnrichedArticle, TickerMention
from vinu_news.analysis.pipeline import ProcessResult

from vinu_news.service import NewsService
from vinu_news.storage.sqlite_backend import SqliteBackend


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _lead(ticker: str) -> EnrichedArticle:
    ts = _now_ts()
    record = ArticleRecord(
        id=f"id-{ticker}-{ts}",
        headline=f"{ticker} news",
        summary="s",
        source="TEST",
        link=f"https://example.com/{ticker}-{ts}",
        sort_ts=ts,
        region="US",
        tier=1,
        category="MARKETS",
        priority="NORMAL",
        sentiment="NEUTRAL",
        sentiment_score=0,
        impact="LOW",
        tickers=f'["{ticker}"]',
        lang="en",
        threat_level="NONE",
        threat_cat="",
        threat_conf=0.0,
        source_flag=0,
    )
    return EnrichedArticle(
        article=record,
        mentions=[
            TickerMention(
                id=f"m-{ticker}",
                article_id=record.id,
                ticker=ticker,
                dominance=1.0,
                is_primary=1,
            )
        ],
        norm_text=f"{ticker} news",
    )


@pytest.fixture
def service(tmp_path: Path) -> NewsService:
    storage = SqliteBackend(tmp_path / "ingest.db")
    svc = NewsService(storage=storage)
    yield svc
    svc.close()


def test_ticker_mode_persist_filter(service: NewsService):
    service.patch_settings(mode="ticker")
    service.add_watchlist_tickers(["AAPL"])

    leads = [_lead("AAPL"), _lead("MSFT")]
    process_result = ProcessResult(
        articles=leads,
        validated_count=2,
        enriched_count=2,
        clusters_found=0,
        duplicates_dropped=0,
        post_process_applied=True,
        url_dedup_dropped=0,
    )

    with patch("vinu_news.service.load_feeds", return_value=[]), patch(
        "vinu_news.service.poll_all_feeds",
        return_value=([], []),
    ), patch("vinu_news.service.update_feed_health"), patch(
        "vinu_news.service.process_batch",
        return_value=process_result,
    ):
        result = service.run_ingestion_cycle()

    assert result.mode == "ticker"
    assert result.leads_before_filter == 2
    assert result.leads_after_filter == 1
    assert result.inserted == 1
    assert service.storage.article_count() == 1
    rows = service.get_ticker_news("AAPL")
    assert len(rows) == 1
    rows_msft = service.get_ticker_news("MSFT")
    assert len(rows_msft) == 0
