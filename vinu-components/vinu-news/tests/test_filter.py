"""Tests for ticker-mode persist filter."""

from vinu_news.analysis.storage.models import ArticleRecord, EnrichedArticle, TickerMention

from vinu_news.collection.filter import article_matches_watchlist, filter_leads_for_mode


def _article(tickers: list[str], mention_tickers: list[str] | None = None) -> EnrichedArticle:
    record = ArticleRecord(
        id="a1",
        headline="Test",
        summary="Summary",
        source="TEST",
        link="https://example.com/1",
        sort_ts=1,
        region="US",
        tier=1,
        category="MARKETS",
        priority="NORMAL",
        sentiment="NEUTRAL",
        sentiment_score=0,
        impact="LOW",
        tickers='["' + '","'.join(tickers) + '"]' if tickers else "[]",
        lang="en",
        threat_level="NONE",
        threat_cat="",
        threat_conf=0.0,
        source_flag=0,
    )
    mentions = [
        TickerMention(
            id=f"m-{t}",
            article_id="a1",
            ticker=t,
            dominance=1.0,
            is_primary=1,
        )
        for t in (mention_tickers or [])
    ]
    return EnrichedArticle(article=record, mentions=mentions, norm_text="test")


def test_all_mode_passes_everything():
    leads = [_article(["AAPL"]), _article(["MSFT"])]
    result = filter_leads_for_mode(leads, "all", {"NVDA"})
    assert len(result) == 2


def test_ticker_mode_filters_by_mentions():
    leads = [_article([], ["AAPL"]), _article([], ["MSFT"])]
    result = filter_leads_for_mode(leads, "ticker", {"AAPL"})
    assert len(result) == 1
    assert result[0].mentions[0].ticker == "AAPL"


def test_ticker_mode_filters_by_article_tickers_json():
    leads = [_article(["NVDA"]), _article(["TSLA"])]
    result = filter_leads_for_mode(leads, "ticker", {"NVDA"})
    assert len(result) == 1


def test_ticker_mode_empty_watchlist_saves_nothing():
    leads = [_article(["AAPL"])]
    result = filter_leads_for_mode(leads, "ticker", set())
    assert result == []


def test_article_matches_watchlist():
    item = _article(["AAPL"], ["MSFT"])
    assert article_matches_watchlist(item, {"MSFT"})
    assert not article_matches_watchlist(item, {"NVDA"})
