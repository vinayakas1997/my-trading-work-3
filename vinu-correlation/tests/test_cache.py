import time

from vinu_correlation.cache import CorrelationCache


def test_cache_get_set():
    cache = CorrelationCache(maxsize=128, ttl=60)
    cache.set_impact("AAPL", None, None, {"events": [1, 2, 3]})
    result = cache.get_impact("AAPL", None, None)
    assert result == {"events": [1, 2, 3]}


def test_cache_miss():
    cache = CorrelationCache(maxsize=128, ttl=60)
    result = cache.get_correlation("AAPL", None, None)
    assert result is None


def test_cache_ttl_expiry():
    cache = CorrelationCache(maxsize=128, ttl=1)
    cache.set_impact("AAPL", None, None, {"events": []})
    time.sleep(1.1)
    result = cache.get_impact("AAPL", None, None)
    assert result is None


def test_cache_invalidate_symbol():
    cache = CorrelationCache(maxsize=128, ttl=60)
    cache.set_impact("AAPL", None, None, {"events": []})
    cache.set_correlation("MSFT", None, None, {"corr": 0.5})
    cache.invalidate("AAPL")
    assert cache.get_impact("AAPL", None, None) is None
    assert cache.get_correlation("MSFT", None, None) is not None


def test_cache_invalidate_all():
    cache = CorrelationCache(maxsize=128, ttl=60)
    cache.set_impact("AAPL", None, None, {"events": []})
    cache.set_correlation("MSFT", None, None, {"corr": 0.5})
    cache.invalidate()
    assert cache.get_impact("AAPL", None, None) is None
    assert cache.get_correlation("MSFT", None, None) is None
