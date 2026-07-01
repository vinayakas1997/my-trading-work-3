"""Tests for price reaction tagging (TASK-N03)."""

from vinu_news.analysis.post_enrichment.price_reaction import compute_price_changes


def test_compute_price_changes():
    base_ts = 1_700_000_000
    candles = [
        {"bar_ts": base_ts, "close": 100.0},
        {"bar_ts": base_ts + 3600, "close": 105.0},
        {"bar_ts": base_ts + 86400, "close": 110.0},
    ]
    ch_1h, ch_1d = compute_price_changes(candles, base_ts)
    assert ch_1h == 5.0
    assert ch_1d == 10.0
