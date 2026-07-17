from vinu_initial_analysis.angles.drawdown_deep_dive.drawdown import attribute_drawdown, get_drawdowns


def test_get_drawdowns_no_drawdown():
    candles = [
        {"bar_ts": 100, "high": 100, "close": 100},
        {"bar_ts": 200, "high": 102, "close": 101},
        {"bar_ts": 300, "high": 103, "close": 102},
    ]
    result = get_drawdowns("AAPL", candles, drop_threshold_pct=-5.0)
    assert result == []


def test_get_drawdowns_detected():
    candles = [
        {"bar_ts": 100, "high": 100, "close": 100},
        {"bar_ts": 200, "high": 102, "close": 101},
        {"bar_ts": 300, "high": 105, "close": 104},
        {"bar_ts": 400, "high": 103, "close": 95},
        {"bar_ts": 500, "high": 96, "close": 94},
    ]
    result = get_drawdowns("AAPL", candles, drop_threshold_pct=-5.0, lookback_hours=24)
    assert len(result) >= 1
    assert result[0]["drop_pct"] <= -5.0


def test_get_drawdowns_threshold_bounds():
    candles = [
        {"bar_ts": 100, "high": 100, "close": 100},
        {"bar_ts": 200, "high": 100, "close": 99},
    ]
    result = get_drawdowns("AAPL", candles, drop_threshold_pct=-5.0)
    assert result == []


def test_attribute_drawdown_no_events():
    result = attribute_drawdown("AAPL", 1000, 2000, [])
    assert result["attribution"]["news_driven_pct"] == 0.0
    assert result["attribution"]["unexplained_pct"] == 1.0


def test_attribute_drawdown_with_events():
    events = [
        {"symbol": "AAPL", "ts": 500, "headline": "Bad news",
         "sentiment": "BEARISH", "impact_label": "high_bearish",
         "price_change_30m": -2.5},
        {"symbol": "AAPL", "ts": 600, "headline": "More bad news",
         "sentiment": "BEARISH", "impact_label": "medium",
         "price_change_30m": -1.0},
    ]
    result = attribute_drawdown("AAPL", 1000, 2000, events)
    assert result["attribution"]["news_driven_pct"] > 0
    assert len(result["attribution"]["contributing_events"]) == 2
