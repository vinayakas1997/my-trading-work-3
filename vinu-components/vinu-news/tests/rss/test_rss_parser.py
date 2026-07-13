"""Tests for rss_parser."""

from pathlib import Path

from vinu_news.rss.config.feed_loader import FeedConfig
from vinu_news.rss.parse.rss_parser import parse_feed_body

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_sample_rss():
    body = (FIXTURES / "sample_rss.xml").read_bytes()
    feed = FeedConfig(
        id="test_feed",
        url="https://example.com/feed",
        source="REUTERS",
        region="US",
        tier=2,
        category="MARKETS",
    )
    articles = parse_feed_body(body, feed)
    assert len(articles) == 2
    assert articles[0]["headline"] == "AAPL beats earnings estimates"
    assert articles[0]["source"] == "REUTERS"
    assert articles[0]["link"] == "https://example.com/aapl-earnings"
    assert articles[1]["headline"] == "Fed holds rates steady"


def test_skips_entries_without_link():
    body = b"""<?xml version="1.0"?><rss version="2.0"><channel>
    <item><title>No link article</title></item>
    <item><title>Has link</title><link>https://example.com/x</link></item>
    </channel></rss>"""
    feed = FeedConfig(
        id="test",
        url="https://example.com",
        source="TEST",
        region="US",
        tier=2,
        category="MARKETS",
    )
    articles = parse_feed_body(body, feed)
    assert len(articles) == 1
    assert articles[0]["headline"] == "Has link"
