from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_screener.pipeline.hard_filter import HardFilterConfig
from vinu_screener.pipeline.scorer import FactorSpec
from vinu_screener.rankers.config import RankerConfig
from vinu_screener.rankers.runner import RankerRunner


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


class FakeBatchDataSource(FakeDataSource):
    def __init__(self) -> None:
        super().__init__()
        self.batch_calls = 0

    def get_ohlcv_batch(self, symbols: list[str]) -> dict[str, pd.DataFrame | None]:
        self.batch_calls += 1
        return {s: self.frames.get(s) for s in symbols}


def _cfg(universe, factors, **overrides) -> RankerConfig:
    defaults = dict(ranker_id="r1", universe=universe, factors=factors)
    defaults.update(overrides)
    return RankerConfig(**defaults)


class TestBasicRanking:
    def test_uptrend_outranks_downtrend(self) -> None:
        ds = FakeDataSource()
        ds.frames["UP"] = _trend(100, 110)
        ds.frames["DOWN"] = _trend(100, 95)
        factors = (FactorSpec("momentum", "pct_change", weight=100.0, params={"period": 10}),)
        result = RankerRunner(ds).run(_cfg(("UP", "DOWN"), factors))
        assert [c.symbol for c in result.ranked] == ["UP", "DOWN"]

    def test_negative_weight_flips_the_order(self) -> None:
        ds = FakeDataSource()
        ds.frames["UP"] = _trend(100, 110)
        ds.frames["DOWN"] = _trend(100, 95)
        factors = (FactorSpec("momentum", "pct_change", weight=-100.0, params={"period": 10}),)
        result = RankerRunner(ds).run(_cfg(("UP", "DOWN"), factors))
        assert [c.symbol for c in result.ranked] == ["DOWN", "UP"]

    def test_top_n_is_respected(self) -> None:
        ds = FakeDataSource()
        for i in range(5):
            ds.frames[f"S{i}"] = _trend(100, 100 + i)
        factors = (FactorSpec("momentum", "pct_change", weight=1.0, params={"period": 10}),)
        result = RankerRunner(ds).run(_cfg(tuple(f"S{i}" for i in range(5)), factors, top_n=2))
        assert len(result.top) == 2


class TestMissingData:
    def test_symbol_with_no_data_is_excluded(self) -> None:
        ds = FakeDataSource()
        ds.frames["AAPL"] = _trend(100, 110)
        factors = (FactorSpec("momentum", "pct_change", weight=1.0),)
        result = RankerRunner(ds).run(_cfg(("AAPL", "GHOST"), factors))
        assert [c.symbol for c in result.ranked] == ["AAPL"]

    def test_all_missing_data_yields_empty_ranking(self) -> None:
        ds = FakeDataSource()
        factors = (FactorSpec("momentum", "pct_change", weight=1.0),)
        result = RankerRunner(ds).run(_cfg(("GHOST1", "GHOST2"), factors))
        assert result.ranked == []


class TestHardFilterIntegration:
    def test_hard_filter_removes_low_price_symbols(self) -> None:
        ds = FakeDataSource()
        ds.frames["PENNY"] = _trend(1.0, 1.1)
        ds.frames["BLUECHIP"] = _trend(100.0, 105.0)
        factors = (FactorSpec("momentum", "pct_change", weight=1.0),)
        result = RankerRunner(ds).run(_cfg(("PENNY", "BLUECHIP"), factors, hard_filter=HardFilterConfig(min_price=10.0)))
        assert [c.symbol for c in result.ranked] == ["BLUECHIP"]


class TestBatchFetchPreferred:
    def test_uses_batch_when_available(self) -> None:
        ds = FakeBatchDataSource()
        ds.frames["AAPL"] = _trend(100, 110)
        factors = (FactorSpec("momentum", "pct_change", weight=1.0),)
        RankerRunner(ds).run(_cfg(("AAPL",), factors))
        assert ds.batch_calls == 1


class TestAlwaysCarriesPriceFields:
    def test_price_volume_dollar_volume_present_even_without_a_matching_factor(self) -> None:
        ds = FakeDataSource()
        ds.frames["AAPL"] = _trend(100, 110)
        factors = (FactorSpec("momentum", "pct_change", weight=1.0),)
        result = RankerRunner(ds).run(_cfg(("AAPL",), factors))
        candidate = result.ranked[0]
        assert candidate.fields["price"] == pytest.approx(110.0)
        assert candidate.fields["volume"] == pytest.approx(1000.0)
        assert candidate.fields["dollar_volume"] == pytest.approx(110.0 * 1000.0)
