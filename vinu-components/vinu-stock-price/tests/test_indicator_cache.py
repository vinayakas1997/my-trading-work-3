"""item #19 finding #5: IndicatorCache had zero dedicated tests -- these
cover the TTL/eviction/staleness-reporting behavior directly, not just
through the route layer (see TestCandlesCacheAgeHeader in test_api.py for
the route-level wiring)."""

from __future__ import annotations

from vinu_stock.query.cache import IndicatorCache


def _rows() -> list[dict]:
    return [{"bar_ts": 0, "close": 100.0}]


def test_miss_returns_none():
    cache = IndicatorCache()
    assert cache.get("AAPL", "1m", None, None, frozenset(), True) is None


def test_hit_returns_data_and_a_real_age():
    cache = IndicatorCache()
    cache.set("AAPL", "1m", None, None, frozenset({"sma_5"}), True, _rows())
    result = cache.get("AAPL", "1m", None, None, frozenset({"sma_5"}), True)
    assert result is not None
    data, age = result
    assert data == _rows()
    assert age >= 0.0


def test_entry_expires_after_ttl():
    cache = IndicatorCache(ttl=0)
    cache.set("AAPL", "1m", None, None, frozenset({"sma_5"}), True, _rows())
    assert cache.get("AAPL", "1m", None, None, frozenset({"sma_5"}), True) is None


def test_evicts_least_recently_used_when_over_capacity():
    cache = IndicatorCache(maxsize=2)
    cache.set("AAPL", "1m", None, None, frozenset(), True, _rows())
    cache.set("MSFT", "1m", None, None, frozenset(), True, _rows())
    cache.set("GOOG", "1m", None, None, frozenset(), True, _rows())  # evicts AAPL
    assert cache.get("AAPL", "1m", None, None, frozenset(), True) is None
    assert cache.get("MSFT", "1m", None, None, frozenset(), True) is not None
    assert cache.get("GOOG", "1m", None, None, frozenset(), True) is not None


def test_different_indicator_sets_are_different_cache_keys():
    cache = IndicatorCache()
    cache.set("AAPL", "1m", None, None, frozenset({"sma_5"}), True, _rows())
    assert cache.get("AAPL", "1m", None, None, frozenset({"rsi_14"}), True) is None


def test_invalidate_by_symbol_only_clears_that_symbol():
    cache = IndicatorCache()
    cache.set("AAPL", "1m", None, None, frozenset(), True, _rows())
    cache.set("MSFT", "1m", None, None, frozenset(), True, _rows())
    cache.invalidate("AAPL")
    assert cache.get("AAPL", "1m", None, None, frozenset(), True) is None
    assert cache.get("MSFT", "1m", None, None, frozenset(), True) is not None


def test_invalidate_with_no_symbol_clears_everything():
    cache = IndicatorCache()
    cache.set("AAPL", "1m", None, None, frozenset(), True, _rows())
    cache.invalidate(None)
    assert cache.get("AAPL", "1m", None, None, frozenset(), True) is None
