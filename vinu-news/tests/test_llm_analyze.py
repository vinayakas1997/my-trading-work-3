"""Tests for LLM article analysis (TASK-N01)."""

import json
from pathlib import Path

import pytest

from vinu_news.analysis.llm.analyze import analyze_article
from vinu_news.analysis.llm.client import LlmClient
from vinu_news.analysis.storage.repository import NewsRepository
from vinu_news.config import VinuConfig


@pytest.fixture
def repo(tmp_path: Path) -> NewsRepository:
    return NewsRepository(tmp_path / "news.db")


def _insert_article(repo: NewsRepository) -> str:
    repo.conn.execute(
        """
        INSERT INTO articles (
            id, headline, summary, source, link, sort_ts, region, tier,
            category, priority, sentiment, sentiment_score, impact, tickers,
            lang, threat_level, threat_cat, threat_conf, source_flag
        ) VALUES (
            'art1', 'Apple beats earnings', 'Revenue up', 'TEST', 'https://example.com/a1',
            1700000000, 'US', 2, 'EARNINGS', 'ROUTINE', 'BULLISH', 50, 'HIGH',
            '["AAPL"]', 'en', 'Low', 'NONE', 0.1, 0
        )
        """
    )
    repo.conn.commit()
    return "https://example.com/a1"


def test_analyze_article_cached(repo: NewsRepository, monkeypatch):
    url = _insert_article(repo)
    cfg = VinuConfig(
        storage="sqlite",
        db_path=repo.db_path,
        database_url=None,
        default_mode="ticker",
        default_poll_interval_sec=600,
        host="127.0.0.1",
        port=8080,
        shared_watchlist_path=None,
        stock_api_url="http://127.0.0.1:8081",
        llm_base_url="http://localhost/v1",
        llm_model="test",
        llm_api_key=None,
        llm_ttl_sec=3600,
        fmp_api_key="",
    )

    analysis = {
        "sentiment_score": 0.8,
        "confidence": 90,
        "risk_flags": ["volatility"],
        "summary": "Bullish earnings beat.",
    }

    class FakeLlm(LlmClient):
        def chat_json(self, system, user):
            return analysis

    result1 = analyze_article(repo, url, config=cfg, client=FakeLlm(cfg))
    assert result1["cached"] is False
    assert result1["analysis"]["sentiment_score"] == 0.8

    result2 = analyze_article(repo, url, config=cfg, client=FakeLlm(cfg))
    assert result2["cached"] is True
