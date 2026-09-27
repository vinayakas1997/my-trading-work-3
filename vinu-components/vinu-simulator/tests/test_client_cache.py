from __future__ import annotations

from vinu_simulator.clients._cache import LRUCache


def test_get_miss_returns_none():
    cache = LRUCache(maxsize=2)
    assert cache.get("a") is None


def test_set_then_get_round_trips():
    cache = LRUCache(maxsize=2)
    cache.set("a", 1)
    assert cache.get("a") == 1


def test_evicts_least_recently_used_when_over_capacity():
    cache = LRUCache(maxsize=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)  # "a" is least recently used, should be evicted
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_get_refreshes_recency():
    cache = LRUCache(maxsize=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")  # "a" is now more recently used than "b"
    cache.set("c", 3)  # should evict "b", not "a"
    assert cache.get("a") == 1
    assert cache.get("b") is None
    assert cache.get("c") == 3


def test_clear_empties_the_cache():
    cache = LRUCache(maxsize=2)
    cache.set("a", 1)
    cache.clear()
    assert cache.get("a") is None
    assert len(cache) == 0
