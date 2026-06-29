"""Tests mirroring step_1_1_news.md worked examples."""

import tempfile
from pathlib import Path

from vinu_news.analysis.enrichment.category import refine_category
from vinu_news.analysis.enrichment.impact import classify_impact
from vinu_news.analysis.enrichment.priority import classify_priority
from vinu_news.analysis.enrichment.sentiment import score_sentiment
from vinu_news.analysis.enrichment.source_credibility import check_source_flag
from vinu_news.analysis.enrichment.ticker_dominance import compute_dominance
from vinu_news.analysis.enrichment.ticker_extractor import extract_tickers
from vinu_news.analysis.enrichment.threat import classify_threat
from vinu_news.analysis.pipeline import enrich_article, process_batch
from vinu_news.analysis.storage.repository import NewsRepository


class TestPriority:
    def test_urgent_alert_is_flash_not_urgent(self):
        text = "URGENT ALERT: ECB announces emergency bailout plan"
        assert classify_priority(text) == "FLASH"


class TestSentiment:
    def test_nvidia_headline_bullish_net_four(self):
        text = (
            "NVIDIA profit surges, beats estimates, "
            "but chip shortage fears warning looms"
        )
        result = score_sentiment(text)
        assert result["sentiment"] == "BULLISH"
        assert result["sentiment_score"] == 4
        assert result["positive_total"] == 7
        assert result["negative_total"] == 3


class TestImpact:
    def test_high_impact_from_extreme_sentiment_despite_routine_priority(self):
        text = (
            "Nvidia shares skyrocket as earnings surge, beats estimates "
            "on record high demand, guidance raised"
        )
        sent = score_sentiment(text)
        priority = classify_priority(text)
        assert priority == "ROUTINE"
        assert classify_impact(priority, sent["sentiment_score"]) == "HIGH"

    def test_low_impact_tesla_miss(self):
        text = "Tesla quarterly results miss estimates, profits drop"
        sent = score_sentiment(text)
        priority = classify_priority(text)
        assert classify_impact(priority, sent["sentiment_score"]) == "LOW"


class TestCategory:
    def test_economic_beats_markets_and_tech(self):
        text = "Fed warns of inflation, stock market reacts, tech sector down"
        assert refine_category(text) == "ECONOMIC"


class TestThreat:
    def test_ransomware_cyber_high(self):
        text = (
            "Breaking: Ransomware attack locks down municipal IT systems, "
            "group demands payment"
        )
        result = classify_threat(text, "BEARISH")
        assert result["threat_cat"] == "cyber"
        assert result["threat_level"] == "HIGH"
        assert result["threat_conf"] == 0.80

    def test_antitrust_regulatory_medium(self):
        text = (
            "Justice Department launches antitrust probe into "
            "tech giant's search dominance"
        )
        result = classify_threat(text, "NEUTRAL")
        assert result["threat_cat"] == "regulatory"
        assert result["threat_level"] == "MEDIUM"
        assert result["threat_conf"] == 0.60

    def test_bearish_fallback_low_threat(self):
        text = "Automaker reports disappointing delivery numbers as stock drops"
        sent = score_sentiment(text)
        result = classify_threat(text, sent["sentiment"])
        assert sent["sentiment"] == "BEARISH"
        assert result["threat_level"] == "LOW"
        assert result["threat_cat"] == "general"
        assert result["threat_conf"] == 0.40


class TestSourceCredibility:
    def test_zerohedge_caution_flag(self):
        assert check_source_flag("ZEROHEDGE") == 2

    def test_reuters_none_flag(self):
        assert check_source_flag("REUTERS") == 0


class TestTickerDominance:
    def test_dominance_sums_to_one(self):
        headline = "AAPL surges as AAPL beats estimates, TSLA follows"
        summary = "Apple reported strong results while Tesla lagged."
        tickers = extract_tickers(headline, summary)
        dominance = compute_dominance(tickers, headline, summary)
        assert abs(sum(dominance.values()) - 1.0) < 0.001
        assert dominance["AAPL"] > dominance["TSLA"]


class TestPipeline:
    def test_full_enrichment(self):
        raw = {
            "headline": "AAPL and TSLA rally as tech stocks surge",
            "summary": "<p>Apple and Tesla shares gained on strong earnings.</p>",
            "link": "https://example.com/test-article",
            "pubDate": "Sun, 14 Jun 2026 12:00:00 GMT",
            "source": "REUTERS",
            "region": "US",
            "tier": 1,
        }
        enriched = enrich_article(raw)
        assert enriched.article.sentiment in ("BULLISH", "NEUTRAL", "BEARISH")
        assert len(enriched.article.summary) <= 300
        assert "<p>" not in enriched.article.summary
        assert len(enriched.mentions) >= 1

    def test_process_batch_with_post_enrichment(self):
        raw = {
            "headline": "Powell warns on inflation in Washington",
            "summary": "Federal Reserve chair speaks on rates.",
            "link": "https://example.com/fed-1",
            "pubDate": "Sun, 14 Jun 2026 12:00:00 GMT",
            "source": "REUTERS",
            "region": "US",
            "tier": 1,
        }
        result = process_batch([raw])
        assert result.post_process_applied is True
        assert len(result.articles) == 1
        entities = result.articles[0].article.entities()
        assert "Jerome Powell" in entities["people"]
        assert "US" in entities["countries"]


class TestRepository:
    def test_upsert_and_query_by_ticker(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            raw = {
                "headline": "AAPL beats earnings estimates",
                "summary": "Apple reported strong quarterly results.",
                "link": "https://example.com/aapl-earnings",
                "pubDate": "Sun, 14 Jun 2026 12:00:00 GMT",
                "source": "REUTERS",
                "region": "US",
                "tier": 1,
            }
            enriched = enrich_article(raw)

            repo = NewsRepository(db_path)
            try:
                assert repo.upsert_article(enriched) is True
                assert repo.upsert_article(enriched) is False

                rows = repo.get_news_for_ticker("AAPL")
                assert len(rows) == 1
                assert rows[0]["headline"] == raw["headline"]

                high = repo.get_high_impact(since_ts=0)
                assert isinstance(high, list)

                daily = repo.get_news_for_date("2026-06-14")
                assert len(daily) >= 1
            finally:
                repo.close()
