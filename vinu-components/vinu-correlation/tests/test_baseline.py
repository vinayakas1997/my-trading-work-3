from vinu_correlation.engine.baseline import _classify_deviation, compute_baseline


def test_classify_deviation():
    assert _classify_deviation(1.0) == "normal"
    assert _classify_deviation(2.5) == "elevated"
    assert _classify_deviation(3.5) == "high"
    assert _classify_deviation(5.0) == "critical"


def test_compute_baseline_empty():
    result = compute_baseline([], window_days=7)
    assert result == []


def test_compute_baseline_with_articles():
    articles = [
        {"sort_ts": 1700000000, "sentiment_score": 0},
        {"sort_ts": 1700003600, "sentiment_score": 0},
        {"sort_ts": 1700007200, "sentiment_score": 0},
    ]
    result = compute_baseline(articles, window_days=7)
    assert len(result) > 0
    for entry in result:
        assert "hour_ts" in entry
        assert "article_count" in entry
        assert "mean" in entry
        assert "stddev" in entry
        assert "session" in entry
