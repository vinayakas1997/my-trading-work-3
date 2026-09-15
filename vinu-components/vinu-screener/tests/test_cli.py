from __future__ import annotations

from vinu_screener.cli import _parse_args, seed_default_main
from vinu_screener.rankers.seed import CORE_STARTER_RANKER_ID
from vinu_screener.rankers.store import RankerStore


class TestSeedDefaultCli:
    def test_parses_seed_default_subcommand(self) -> None:
        args = _parse_args(["seed-default"])
        assert args.func is seed_default_main

    def test_seed_default_main_creates_ranker(self, tmp_path) -> None:
        db_path = tmp_path / "rankers.db"
        args = _parse_args(["seed-default", "--ranker-db", str(db_path)])

        args.func(args)

        store = RankerStore(db_path)
        assert store.get(CORE_STARTER_RANKER_ID) is not None

    def test_seed_default_main_is_idempotent(self, tmp_path) -> None:
        db_path = tmp_path / "rankers.db"
        args = _parse_args(["seed-default", "--ranker-db", str(db_path)])

        args.func(args)
        first_created_at = RankerStore(db_path).get(CORE_STARTER_RANKER_ID).created_at

        args.func(args)
        second_created_at = RankerStore(db_path).get(CORE_STARTER_RANKER_ID).created_at

        assert first_created_at == second_created_at
