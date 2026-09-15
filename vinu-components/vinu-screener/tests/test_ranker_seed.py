from __future__ import annotations

import json

import pytest

from vinu_screener.features.library import DEFAULT_REGISTRY
from vinu_screener.rankers.seed import (
    CORE_STARTER_RANKER_ID,
    build_core_starter_config,
    seed_default_ranker,
)
from vinu_screener.rankers.store import RankerStore


@pytest.fixture
def store():
    return RankerStore(":memory:")


class TestBuildCoreStarterConfig:
    def test_uses_only_real_registered_indicators(self) -> None:
        cfg = build_core_starter_config()
        for factor in cfg.factors:
            assert factor.indicator in DEFAULT_REGISTRY

    def test_round_trips_through_to_dict_from_dict(self) -> None:
        cfg = build_core_starter_config()
        from vinu_screener.rankers.config import RankerConfig

        round_tripped = RankerConfig.from_dict(cfg.to_dict())
        assert round_tripped == cfg

    def test_has_a_nonempty_universe_and_factors(self) -> None:
        cfg = build_core_starter_config()
        assert len(cfg.universe) > 0
        assert len(cfg.factors) > 0


class TestUniverseOverride:
    def test_falls_back_to_built_in_universe_when_no_override_file(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("VINU_SCREENER_SEED_CONFIG", str(tmp_path / "does_not_exist.json"))
        from vinu_screener.rankers.seed import CORE_STARTER_UNIVERSE

        cfg = build_core_starter_config()

        assert cfg.universe == CORE_STARTER_UNIVERSE

    def test_uses_override_file_when_present(self, monkeypatch, tmp_path) -> None:
        override_path = tmp_path / "seed_universe.json"
        override_path.write_text(json.dumps({"universe": ["snap", "ibm ", "GME"]}))
        monkeypatch.setenv("VINU_SCREENER_SEED_CONFIG", str(override_path))

        cfg = build_core_starter_config()

        assert cfg.universe == ("SNAP", "IBM", "GME")

    def test_empty_universe_key_falls_back_to_built_in(self, monkeypatch, tmp_path) -> None:
        override_path = tmp_path / "seed_universe.json"
        override_path.write_text(json.dumps({"universe": []}))
        monkeypatch.setenv("VINU_SCREENER_SEED_CONFIG", str(override_path))
        from vinu_screener.rankers.seed import CORE_STARTER_UNIVERSE

        cfg = build_core_starter_config()

        assert cfg.universe == CORE_STARTER_UNIVERSE

    def test_malformed_json_falls_back_to_built_in_without_raising(self, monkeypatch, tmp_path) -> None:
        override_path = tmp_path / "seed_universe.json"
        override_path.write_text("{not valid json")
        monkeypatch.setenv("VINU_SCREENER_SEED_CONFIG", str(override_path))
        from vinu_screener.rankers.seed import CORE_STARTER_UNIVERSE

        cfg = build_core_starter_config()

        assert cfg.universe == CORE_STARTER_UNIVERSE


class TestSeedDefaultRanker:
    def test_creates_ranker_when_absent(self, store) -> None:
        created = seed_default_ranker(store)
        assert created is True
        assert store.get(CORE_STARTER_RANKER_ID) is not None

    def test_idempotent_second_call_is_noop(self, store) -> None:
        seed_default_ranker(store)
        first = store.get(CORE_STARTER_RANKER_ID)

        created_again = seed_default_ranker(store)

        assert created_again is False
        second = store.get(CORE_STARTER_RANKER_ID)
        assert second.created_at == first.created_at

    def test_does_not_clobber_an_operators_own_edit(self, store) -> None:
        import dataclasses

        seed_default_ranker(store)
        edited = dataclasses.replace(build_core_starter_config(), top_n=99)
        store.upsert_ranker(edited)

        created_again = seed_default_ranker(store)

        assert created_again is False
        assert store.get(CORE_STARTER_RANKER_ID).ranker.top_n == 99
