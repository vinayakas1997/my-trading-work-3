from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_screener.conditions.schema import parse_condition
from vinu_screener.scan.cooldown import CooldownGate
from vinu_screener.scan.monitor import MIN_INTERVAL_SEC, ScanMonitor, ScanRule
from vinu_screener.scan.universe import CoarseFilter


def _ohlcv(close: list[float]) -> pd.DataFrame:
    c = np.array(close, dtype=float)
    return pd.DataFrame({"open": c, "high": c + 0.1, "low": c - 0.1, "close": c, "volume": np.full(len(c), 1000.0)})


class FakeDataSource:
    """In-memory stand-in for SymbolDataSource -- no network, fully
    deterministic, and lets a test simulate a slow/hanging symbol."""

    def __init__(self) -> None:
        self.frames: dict[str, pd.DataFrame] = {}
        self.snapshots: dict[str, dict[str, float]] = {}
        self.slow_symbols: set[str] = set()

    def get_ohlcv(self, symbol: str):
        if symbol in self.slow_symbols:
            import time
            time.sleep(0.3)
        return self.frames.get(symbol)

    def get_snapshot(self, symbol: str):
        return self.snapshots.get(symbol)


class FakeBatchDataSource(FakeDataSource):
    """Same as FakeDataSource, plus get_ohlcv_batch -- exercises
    ScanMonitor's batch-prefetch path (used when a real HttpStockDataSource
    talks to vinu-stock-price's POST /candles/batch)."""

    def __init__(self) -> None:
        super().__init__()
        self.batch_calls: list[list[str]] = []
        self.batch_hangs: bool = False

    def get_ohlcv_batch(self, symbols: list[str]) -> dict[str, pd.DataFrame | None]:
        self.batch_calls.append(list(symbols))
        if self.batch_hangs:
            import time
            time.sleep(0.3)
        return {s: self.frames.get(s) for s in symbols}


def _above_100_rule(universe, cooldown_min=0.0, coarse_filter=None) -> ScanRule:
    return ScanRule(
        rule_id="r-above-100",
        condition=parse_condition({"indicator": "close", "operator": ">", "value": 100.0}),
        universe=tuple(universe),
        cooldown_min=cooldown_min,
        coarse_filter=coarse_filter or CoarseFilter(),
    )


class TestBasicCycle:
    def test_fires_for_symbols_above_the_threshold(self) -> None:
        ds = FakeDataSource()
        ds.frames["AAPL"] = _ohlcv([90, 95, 105])
        ds.frames["MSFT"] = _ohlcv([50, 55, 60])
        monitor = ScanMonitor(ds)
        rule = _above_100_rule(["AAPL", "MSFT"])
        result = monitor.run_cycle(rule)
        assert result.fired == ["AAPL"]

    def test_interval_is_floored_at_the_rate_limit_minimum(self) -> None:
        monitor = ScanMonitor(FakeDataSource(), interval_sec=1.0)
        assert monitor.interval_sec == MIN_INTERVAL_SEC

    def test_interval_above_the_floor_is_respected(self) -> None:
        monitor = ScanMonitor(FakeDataSource(), interval_sec=120.0)
        assert monitor.interval_sec == 120.0


class TestInsufficientHistory:
    def test_too_few_bars_is_marked_not_evaluated(self) -> None:
        ds = FakeDataSource()
        ds.frames["AAPL"] = _ohlcv([105])  # 1 bar, needs 3 for "close > value" (1+0+2)
        monitor = ScanMonitor(ds)
        rule = _above_100_rule(["AAPL"])
        result = monitor.run_cycle(rule)
        outcome = next(o for o in result.outcomes if o.symbol == "AAPL")
        assert outcome.status == "insufficient_history"
        assert result.fired == []

    def test_missing_symbol_is_insufficient_history_not_a_crash(self) -> None:
        monitor = ScanMonitor(FakeDataSource())
        rule = _above_100_rule(["GHOST"])
        result = monitor.run_cycle(rule)
        assert result.outcomes[0].status == "insufficient_history"


class TestTimeoutHandling:
    def test_a_hanging_symbol_times_out_without_blocking_the_cycle(self) -> None:
        ds = FakeDataSource()
        ds.frames["SLOW"] = _ohlcv([90, 95, 105])
        ds.slow_symbols.add("SLOW")
        ds.frames["FAST"] = _ohlcv([90, 95, 105])
        monitor = ScanMonitor(ds, fetch_timeout_sec=0.05)
        rule = _above_100_rule(["SLOW", "FAST"])
        result = monitor.run_cycle(rule)
        slow_outcome = next(o for o in result.outcomes if o.symbol == "SLOW")
        assert slow_outcome.status == "timeout"
        assert "FAST" in result.fired
        assert result.duration_sec < 0.25  # didn't wait out SLOW's 0.3s sleep


class TestCoarseFilterIntegration:
    def test_coarse_filtered_symbols_never_get_a_full_fetch(self) -> None:
        ds = FakeDataSource()
        ds.snapshots["PENNY"] = {"price": 0.50, "volume": 100.0, "dollar_volume": 50.0}
        ds.snapshots["AAPL"] = {"price": 150.0, "volume": 1_000_000.0, "dollar_volume": 150_000_000.0}
        ds.frames["AAPL"] = _ohlcv([90, 95, 105])
        ds.frames["PENNY"] = _ohlcv([90, 95, 105])  # would fire if evaluated -- must not be
        monitor = ScanMonitor(ds)
        rule = _above_100_rule(["AAPL", "PENNY"], coarse_filter=CoarseFilter(min_price=1.0))
        result = monitor.run_cycle(rule)
        assert result.fired == ["AAPL"]
        penny_outcome = next(o for o in result.outcomes if o.symbol == "PENNY")
        assert penny_outcome.status == "coarse_filtered"

    def test_no_coarse_filter_skips_the_snapshot_round_trip(self) -> None:
        ds = FakeDataSource()
        ds.frames["AAPL"] = _ohlcv([90, 95, 105])
        monitor = ScanMonitor(ds)
        rule = _above_100_rule(["AAPL"])  # default CoarseFilter() -- a no-op
        result = monitor.run_cycle(rule)
        assert ds.snapshots == {}  # get_snapshot never even called
        assert result.fired == ["AAPL"]


class TestCooldownIntegration:
    def test_second_consecutive_cycle_does_not_refire(self) -> None:
        ds = FakeDataSource()
        ds.frames["AAPL"] = _ohlcv([90, 95, 105])
        gate = CooldownGate()
        monitor = ScanMonitor(ds, cooldown_gate=gate)
        rule = _above_100_rule(["AAPL"])
        r1 = monitor.run_cycle(rule, now=0.0)
        r2 = monitor.run_cycle(rule, now=60.0)
        assert r1.fired == ["AAPL"]
        assert r2.fired == []

    def test_refires_after_dropping_below_and_back_above(self) -> None:
        ds = FakeDataSource()
        gate = CooldownGate()
        monitor = ScanMonitor(ds, cooldown_gate=gate)
        rule = _above_100_rule(["AAPL"])

        ds.frames["AAPL"] = _ohlcv([90, 95, 105])
        r1 = monitor.run_cycle(rule, now=0.0)
        ds.frames["AAPL"] = _ohlcv([90, 95, 50])
        r2 = monitor.run_cycle(rule, now=60.0)
        ds.frames["AAPL"] = _ohlcv([90, 95, 110])
        r3 = monitor.run_cycle(rule, now=120.0)

        assert r1.fired == ["AAPL"]
        assert r2.fired == []
        assert r3.fired == ["AAPL"]

    def test_cooldown_minutes_suppress_a_too_soon_refire(self) -> None:
        ds = FakeDataSource()
        gate = CooldownGate()
        monitor = ScanMonitor(ds, cooldown_gate=gate)
        rule = _above_100_rule(["AAPL"], cooldown_min=10.0)

        ds.frames["AAPL"] = _ohlcv([90, 95, 105])
        r1 = monitor.run_cycle(rule, now=0.0)
        ds.frames["AAPL"] = _ohlcv([90, 95, 50])
        monitor.run_cycle(rule, now=60.0)
        ds.frames["AAPL"] = _ohlcv([90, 95, 110])
        r3 = monitor.run_cycle(rule, now=120.0)  # only 2 min after r1, cooldown is 10 min

        assert r1.fired == ["AAPL"]
        assert r3.fired == []


class TestSharedCacheAcrossTheCycle:
    def test_feature_library_cache_is_cleared_between_cycles(self) -> None:
        ds = FakeDataSource()
        ds.frames["AAPL"] = _ohlcv([90, 95, 105])
        monitor = ScanMonitor(ds)
        rule = _above_100_rule(["AAPL"])
        monitor.run_cycle(rule, now=0.0)
        assert len(monitor._library._cache) > 0
        ds.frames["AAPL"] = _ohlcv([90, 95, 50])
        result = monitor.run_cycle(rule, now=60.0)
        # if the cache weren't cleared, this would still read the old (fired) value
        assert result.fired == []


class TestScanRuleFromDict:
    def test_parses_a_full_rule_dict(self) -> None:
        raw = {
            "rule_id": "r1",
            "condition": {"indicator": "close", "operator": ">", "value": 100.0},
            "universe": ["AAPL", "MSFT"],
            "cooldown_min": 15.0,
            "coarse_filter": {"min_price": 5.0},
        }
        rule = ScanRule.from_dict(raw)
        assert rule.rule_id == "r1"
        assert rule.universe == ("AAPL", "MSFT")
        assert rule.cooldown_min == 15.0
        assert rule.coarse_filter.min_price == 5.0

    def test_defaults_when_optional_fields_omitted(self) -> None:
        raw = {"rule_id": "r1", "condition": {"indicator": "close", "operator": ">", "value": 1}, "universe": ["A"]}
        rule = ScanRule.from_dict(raw)
        assert rule.cooldown_min == 0.0
        assert rule.coarse_filter == CoarseFilter()


class TestBatchFetch:
    """ScanMonitor prefers a data source's get_ohlcv_batch() when it has
    one -- one call for the whole cycle's universe instead of one per
    symbol -- and falls back cleanly when it doesn't, or when the batch
    call itself fails/times out."""

    def test_uses_one_batch_call_instead_of_per_symbol_calls(self) -> None:
        ds = FakeBatchDataSource()
        ds.frames["AAPL"] = _ohlcv([90, 95, 105])
        ds.frames["MSFT"] = _ohlcv([50, 55, 60])
        monitor = ScanMonitor(ds)
        rule = _above_100_rule(["AAPL", "MSFT"])
        result = monitor.run_cycle(rule)
        assert result.fired == ["AAPL"]
        assert len(ds.batch_calls) == 1
        assert set(ds.batch_calls[0]) == {"AAPL", "MSFT"}

    def test_coarse_filtered_symbols_are_excluded_from_the_batch_call(self) -> None:
        ds = FakeBatchDataSource()
        ds.snapshots["PENNY"] = {"price": 0.50, "volume": 100.0, "dollar_volume": 50.0}
        ds.snapshots["AAPL"] = {"price": 150.0, "volume": 1_000_000.0, "dollar_volume": 150_000_000.0}
        ds.frames["AAPL"] = _ohlcv([90, 95, 105])
        ds.frames["PENNY"] = _ohlcv([90, 95, 105])
        monitor = ScanMonitor(ds)
        rule = _above_100_rule(["AAPL", "PENNY"], coarse_filter=CoarseFilter(min_price=1.0))
        monitor.run_cycle(rule)
        assert ds.batch_calls == [["AAPL"]]

    def test_missing_symbol_in_batch_result_is_insufficient_history(self) -> None:
        ds = FakeBatchDataSource()  # GHOST never added to ds.frames
        monitor = ScanMonitor(ds)
        rule = _above_100_rule(["GHOST"])
        result = monitor.run_cycle(rule)
        assert result.outcomes[0].status == "insufficient_history"

    def test_a_hanging_batch_call_times_out_and_falls_back_per_symbol(self) -> None:
        ds = FakeBatchDataSource()
        ds.batch_hangs = True
        ds.frames["AAPL"] = _ohlcv([90, 95, 105])
        monitor = ScanMonitor(ds, batch_fetch_timeout_sec=0.05)
        rule = _above_100_rule(["AAPL"])
        result = monitor.run_cycle(rule)
        # The batch call timed out, but the per-symbol fallback still finds it.
        assert result.fired == ["AAPL"]

    def test_data_source_without_batch_support_is_unaffected(self) -> None:
        ds = FakeDataSource()  # no get_ohlcv_batch at all
        ds.frames["AAPL"] = _ohlcv([90, 95, 105])
        monitor = ScanMonitor(ds)
        rule = _above_100_rule(["AAPL"])
        result = monitor.run_cycle(rule)
        assert result.fired == ["AAPL"]

    def test_empty_universe_never_calls_batch(self) -> None:
        ds = FakeBatchDataSource()
        monitor = ScanMonitor(ds)
        rule = _above_100_rule([])
        monitor.run_cycle(rule)
        assert ds.batch_calls == []
