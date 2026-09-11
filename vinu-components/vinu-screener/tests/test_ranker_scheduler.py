from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_screener.pipeline.scorer import FactorSpec
from vinu_screener.rankers.churn import RankerChurnStore
from vinu_screener.rankers.config import RankerConfig
from vinu_screener.rankers.runner import RankerRunner
from vinu_screener.rankers.scheduler import RankerScheduler
from vinu_screener.rankers.snapshot_store import RankedSnapshotStore
from vinu_screener.rankers.store import RankerStore


def _trend(start: float, end: float, n: int = 30) -> pd.DataFrame:
    c = np.linspace(start, end, n)
    return pd.DataFrame({"open": c, "high": c + 0.5, "low": c - 0.5, "close": c, "volume": np.full(n, 1000.0)})


class FakeDataSource:
    def __init__(self) -> None:
        self.frames: dict[str, pd.DataFrame] = {}

    def get_ohlcv(self, symbol: str):
        return self.frames.get(symbol)

    def get_snapshot(self, symbol: str):
        return None


def _cfg(ranker_id="r1") -> RankerConfig:
    return RankerConfig(
        ranker_id=ranker_id,
        universe=("AAPL",),
        factors=(FactorSpec("momentum", "pct_change", weight=1.0),),
    )


@pytest.fixture
def ranker_store():
    return RankerStore(":memory:")


@pytest.fixture
def data_source():
    ds = FakeDataSource()
    ds.frames["AAPL"] = _trend(100, 110)
    return ds


class TestTickRunsDueActiveRankers:
    def test_active_ranker_runs_on_first_tick(self, ranker_store, data_source) -> None:
        ranker_store.upsert_ranker(_cfg())
        scheduler = RankerScheduler(ranker_store, RankerRunner(data_source))
        ran = scheduler.tick(now=0.0)
        assert ran == ["r1"]

    def test_inactive_ranker_is_skipped(self, ranker_store, data_source) -> None:
        ranker_store.upsert_ranker(_cfg(), active=False)
        scheduler = RankerScheduler(ranker_store, RankerRunner(data_source))
        assert scheduler.tick(now=0.0) == []

    def test_not_yet_due_is_skipped(self, ranker_store, data_source) -> None:
        ranker_store.upsert_ranker(_cfg(), interval_sec=86400.0)
        scheduler = RankerScheduler(ranker_store, RankerRunner(data_source))
        scheduler.tick(now=0.0)
        assert scheduler.tick(now=100.0) == []  # far short of a day later

    def test_due_again_once_interval_elapses(self, ranker_store, data_source) -> None:
        ranker_store.upsert_ranker(_cfg(), interval_sec=300.0)
        scheduler = RankerScheduler(ranker_store, RankerRunner(data_source))
        scheduler.tick(now=0.0)
        assert scheduler.tick(now=301.0) == ["r1"]


class TestSnapshotPersistence:
    def test_tick_persists_a_snapshot(self, ranker_store, data_source) -> None:
        ranker_store.upsert_ranker(_cfg())
        snapshots = RankedSnapshotStore(":memory:")
        scheduler = RankerScheduler(ranker_store, RankerRunner(data_source), snapshot_store=snapshots)
        scheduler.tick(now=42.0)
        snap = snapshots.get_latest("r1")
        assert snap is not None
        assert snap.generated_at == 42.0
        assert [c.symbol for c in snap.top] == ["AAPL"]

    def test_no_snapshot_store_is_fine(self, ranker_store, data_source) -> None:
        ranker_store.upsert_ranker(_cfg())
        scheduler = RankerScheduler(ranker_store, RankerRunner(data_source))
        assert scheduler.tick(now=0.0) == ["r1"]  # no error despite no snapshot store


class TestErrorIsolation:
    def test_one_ranker_raising_does_not_stop_others(self, ranker_store, data_source) -> None:
        ranker_store.upsert_ranker(_cfg("bad"))
        ranker_store.upsert_ranker(_cfg("good"))

        class BoomRunner(RankerRunner):
            def run(self, cfg, **kwargs):
                if cfg.ranker_id == "bad":
                    raise RuntimeError("boom")
                return super().run(cfg, **kwargs)

        scheduler = RankerScheduler(ranker_store, BoomRunner(data_source))
        assert scheduler.tick(now=0.0) == ["good"]


class TestChurnIntegration:
    def test_second_tick_records_churn_against_the_first(self, ranker_store) -> None:
        ds = FakeDataSource()
        ds.frames["AAPL"] = _trend(100, 110)
        cfg = RankerConfig(
            ranker_id="r1", universe=("AAPL", "MSFT"),
            factors=(FactorSpec("momentum", "pct_change", weight=1.0),), top_n=1,
        )
        ranker_store.upsert_ranker(cfg, interval_sec=300.0)
        snapshots = RankedSnapshotStore(":memory:")
        churn = RankerChurnStore(":memory:")
        scheduler = RankerScheduler(ranker_store, RankerRunner(ds), snapshot_store=snapshots, churn_store=churn)

        scheduler.tick(now=0.0)  # only AAPL has data -- AAPL ranks #1
        ds.frames["MSFT"] = _trend(100, 130)  # MSFT now has stronger momentum than AAPL
        scheduler.tick(now=300.0)

        history = churn.history("r1")
        assert {(h.symbol, h.kind) for h in history} == {("AAPL", "exited"), ("MSFT", "entered")}

    def test_first_tick_ever_records_no_churn(self, ranker_store, data_source) -> None:
        ranker_store.upsert_ranker(_cfg())
        churn = RankerChurnStore(":memory:")
        scheduler = RankerScheduler(
            ranker_store, RankerRunner(data_source),
            snapshot_store=RankedSnapshotStore(":memory:"), churn_store=churn,
        )
        scheduler.tick(now=0.0)
        assert churn.history("r1") == []

    def test_no_churn_store_does_not_break_the_tick(self, ranker_store, data_source) -> None:
        ranker_store.upsert_ranker(_cfg())
        scheduler = RankerScheduler(
            ranker_store, RankerRunner(data_source), snapshot_store=RankedSnapshotStore(":memory:"),
        )
        assert scheduler.tick(now=0.0) == ["r1"]
