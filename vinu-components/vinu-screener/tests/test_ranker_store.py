from __future__ import annotations

import pytest

from vinu_screener.pipeline.hard_filter import HardFilterConfig
from vinu_screener.pipeline.scorer import FactorSpec
from vinu_screener.rankers.config import RANKER_MIN_INTERVAL_SEC, RankerConfig
from vinu_screener.rankers.store import RankerStore


@pytest.fixture
def store():
    return RankerStore(":memory:")


def _cfg(ranker_id="r1", **overrides) -> RankerConfig:
    defaults = dict(
        ranker_id=ranker_id,
        universe=("AAPL", "MSFT"),
        factors=(FactorSpec("momentum", "pct_change", weight=1.0),),
    )
    defaults.update(overrides)
    return RankerConfig(**defaults)


class TestRoundTrip:
    def test_upsert_then_get(self, store) -> None:
        store.upsert_ranker(_cfg(top_n=10, hard_filter=HardFilterConfig(min_price=5.0)), interval_sec=3600.0)
        stored = store.get("r1")
        assert stored is not None
        assert stored.ranker.top_n == 10
        assert stored.ranker.hard_filter.min_price == 5.0
        assert stored.interval_sec == 3600.0

    def test_round_trips_factors(self, store) -> None:
        store.upsert_ranker(_cfg(factors=(FactorSpec("rsi_penalty", "rsi", weight=-1.0),)))
        stored = store.get("r1")
        assert stored.ranker.factors[0].name == "rsi_penalty"
        assert stored.ranker.factors[0].weight == -1.0

    def test_unknown_ranker_is_none(self, store) -> None:
        assert store.get("ghost") is None


class TestIntervalFloor:
    def test_below_floor_is_raised(self, store) -> None:
        stored = store.upsert_ranker(_cfg(), interval_sec=1.0)
        assert stored.interval_sec == RANKER_MIN_INTERVAL_SEC

    def test_above_floor_is_respected(self, store) -> None:
        stored = store.upsert_ranker(_cfg(), interval_sec=86400.0)
        assert stored.interval_sec == 86400.0


class TestListingAndActivation:
    def test_all_lists_every_ranker(self, store) -> None:
        store.upsert_ranker(_cfg("r1"))
        store.upsert_ranker(_cfg("r2"))
        assert {s.ranker.ranker_id for s in store.all()} == {"r1", "r2"}

    def test_active_only_excludes_disabled(self, store) -> None:
        store.upsert_ranker(_cfg("r1"), active=True)
        store.upsert_ranker(_cfg("r2"), active=False)
        assert [s.ranker.ranker_id for s in store.all(active_only=True)] == ["r1"]

    def test_set_active_toggles(self, store) -> None:
        store.upsert_ranker(_cfg("r1"))
        assert store.set_active("r1", False) is True
        assert store.get("r1").active is False


class TestDelete:
    def test_delete_removes(self, store) -> None:
        store.upsert_ranker(_cfg("r1"))
        assert store.delete("r1") is True
        assert store.get("r1") is None

    def test_delete_unknown_returns_false(self, store) -> None:
        assert store.delete("ghost") is False
