from __future__ import annotations

import pytest

from vinu_screener.serve.pairlist_cache import PairlistCache, check_bearer_token


class TestTTLCache:
    def test_first_call_refreshes(self) -> None:
        calls = []

        def refresh(rule_id: str) -> list[str]:
            calls.append(rule_id)
            return ["A", "B"]

        cache = PairlistCache(refresh_fn=refresh, ttl_sec=60.0)
        entry = cache.get("r1", now=0.0)
        assert entry.symbols == ["A", "B"]
        assert entry.stale is False
        assert calls == ["r1"]

    def test_within_ttl_serves_cached_without_refreshing(self) -> None:
        calls = []

        def refresh(rule_id: str) -> list[str]:
            calls.append(rule_id)
            return ["A"]

        cache = PairlistCache(refresh_fn=refresh, ttl_sec=60.0)
        cache.get("r1", now=0.0)
        cache.get("r1", now=30.0)
        assert calls == ["r1"]  # only refreshed once

    def test_past_ttl_refreshes_again(self) -> None:
        calls = []

        def refresh(rule_id: str) -> list[str]:
            calls.append(rule_id)
            return ["A"]

        cache = PairlistCache(refresh_fn=refresh, ttl_sec=60.0)
        cache.get("r1", now=0.0)
        cache.get("r1", now=61.0)
        assert calls == ["r1", "r1"]

    def test_different_rules_cached_independently(self) -> None:
        cache = PairlistCache(refresh_fn=lambda r: [r], ttl_sec=60.0)
        e1 = cache.get("r1", now=0.0)
        e2 = cache.get("r2", now=0.0)
        assert e1.symbols == ["r1"]
        assert e2.symbols == ["r2"]


class TestFailOpen:
    def test_refresh_failure_serves_last_good_as_stale(self) -> None:
        state = {"fail": False}

        def refresh(rule_id: str) -> list[str]:
            if state["fail"]:
                raise ConnectionError("upstream down")
            return ["A", "B"]

        cache = PairlistCache(refresh_fn=refresh, ttl_sec=10.0)
        cache.get("r1", now=0.0)
        state["fail"] = True
        entry = cache.get("r1", now=20.0)  # past TTL, refresh fails
        assert entry.symbols == ["A", "B"]
        assert entry.stale is True

    def test_no_prior_cache_and_refresh_fails_raises(self) -> None:
        def refresh(rule_id: str) -> list[str]:
            raise ConnectionError("upstream down")

        cache = PairlistCache(refresh_fn=refresh, ttl_sec=10.0)
        with pytest.raises(ConnectionError):
            cache.get("r1", now=0.0)

    def test_invalidate_clears_one_rule(self) -> None:
        calls = []

        def refresh(rule_id: str) -> list[str]:
            calls.append(rule_id)
            return ["A"]

        cache = PairlistCache(refresh_fn=refresh, ttl_sec=60.0)
        cache.get("r1", now=0.0)
        cache.invalidate("r1")
        cache.get("r1", now=1.0)
        assert calls == ["r1", "r1"]


class TestBearerToken:
    def test_correct_token_passes(self) -> None:
        assert check_bearer_token("Bearer secret123", "secret123") is True

    def test_wrong_token_fails(self) -> None:
        assert check_bearer_token("Bearer wrong", "secret123") is False

    def test_missing_header_fails(self) -> None:
        assert check_bearer_token(None, "secret123") is False

    def test_missing_bearer_prefix_fails(self) -> None:
        assert check_bearer_token("secret123", "secret123") is False
