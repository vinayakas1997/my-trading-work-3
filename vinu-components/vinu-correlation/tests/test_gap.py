from unittest.mock import MagicMock

from vinu_correlation.api import CorrelationAPI
from vinu_correlation.engine.blocks import compute_premarket_gap


def _make_event(ts: int, session: str = "", headline: str = ""):
    return {
        "ts": ts,
        "sort_ts": ts,
        "session": session,
        "headline": headline,
        "symbol": "AAPL",
        "price_change_30m": 0.0,
        "sentiment": "NEUTRAL",
        "impact_label": "low",
        "article_id": f"a_{ts}",
        "computed_at": 1000000,
    }


def test_get_gap_no_articles():
    gap = compute_premarket_gap([])
    assert gap["gap_hours"] is None
    assert gap["last_article_ts"] is None


def test_get_gap_premarket_article():
    events = [_make_event(40000, "ny_premarket", "premarket news")]
    gap = compute_premarket_gap(events)
    assert gap["last_headline"] == "premarket news"


def test_get_gap_api_delegation():
    api = MagicMock(spec=CorrelationAPI)
    api.get_gap = CorrelationAPI.get_gap.__get__(api, CorrelationAPI)
    api._news_client = MagicMock()
    api._news_client.get_ticker_news = MagicMock(return_value=[])
    api._price_client = MagicMock()
    api._price_client.get_candles = MagicMock(return_value=[])
    gap = api.get_gap("AAPL", "2026-07-06")
    assert gap is not None
