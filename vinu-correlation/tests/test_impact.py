from vinu_correlation.engine.impact import _classify_impact, parse_tickers, aggregate_by_thread


def test_parse_tickers_string():
    primary, secondary = parse_tickers('["AAPL","MSFT","GOOGL"]')
    assert primary == "AAPL"
    assert secondary == ["MSFT", "GOOGL"]


def test_parse_tickers_list():
    primary, secondary = parse_tickers(["AAPL", "MSFT"])
    assert primary == "AAPL"
    assert secondary == ["MSFT"]


def test_parse_tickers_empty():
    primary, secondary = parse_tickers([])
    assert primary == ""
    assert secondary == []


def test_parse_tickers_single():
    primary, secondary = parse_tickers(["AAPL"])
    assert primary == "AAPL"
    assert secondary == []


def test_classify_impact_high_bearish():
    assert _classify_impact("BEARISH", -2.5, 2.0, 0.5) == "high_bearish"


def test_classify_impact_high_bullish():
    assert _classify_impact("BULLISH", 2.5, 2.0, 0.5) == "high_bullish"


def test_classify_impact_medium():
    assert _classify_impact("BEARISH", -1.0, 2.0, 0.5) == "medium"


def test_classify_impact_low():
    assert _classify_impact("NEUTRAL", 0.1, 2.0, 0.5) == "low"


def test_aggregate_by_thread():
    events = [
        {"thread_id": "t1", "headline": "First article", "sentiment_score": -5,
         "price_change_30m": -2.0, "ts": 1000},
        {"thread_id": "t1", "headline": "Second article", "sentiment_score": -4,
         "price_change_30m": -1.5, "ts": 2000},
        {"thread_id": "", "headline": "Standalone", "sentiment_score": 0,
         "price_change_30m": 0.5, "ts": 3000},
    ]
    result = aggregate_by_thread(events, min_thread_articles=2)
    assert len(result["threads"]) == 1
    assert result["threads"][0]["thread_id"] == "t1"
    assert result["threads"][0]["article_count"] == 2
