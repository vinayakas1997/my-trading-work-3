from __future__ import annotations

import numpy as np
import pandas as pd

from vinu_screener.conditions.schema import parse_condition
from vinu_screener.scan.cooldown import CooldownGate
from vinu_screener.scan.dry_run import run_dry_run
from vinu_screener.scan.monitor import ScanMonitor, ScanRule


def _ohlcv(close: list[float]) -> pd.DataFrame:
    c = np.array(close, dtype=float)
    return pd.DataFrame({"open": c, "high": c + 0.1, "low": c - 0.1, "close": c, "volume": np.full(len(c), 1000.0)})


class FakeDataSource:
    def __init__(self) -> None:
        self.frames: dict[str, pd.DataFrame] = {}

    def get_ohlcv(self, symbol: str):
        return self.frames.get(symbol)

    def get_snapshot(self, symbol: str):
        return None


def _rule(universe) -> ScanRule:
    return ScanRule(
        rule_id="r1",
        condition=parse_condition({"indicator": "close", "operator": ">", "value": 100.0}),
        universe=tuple(universe),
    )


class TestCategoryCounts:
    def test_triggered_and_not_triggered(self) -> None:
        ds = FakeDataSource()
        ds.frames["AAPL"] = _ohlcv([90, 95, 105])
        ds.frames["MSFT"] = _ohlcv([50, 55, 60])
        monitor = ScanMonitor(ds)
        report = run_dry_run(monitor, _rule(["AAPL", "MSFT"]))
        assert report.triggered == ["AAPL"]
        assert report.not_triggered == ["MSFT"]
        assert report.counts["triggered"] == 1
        assert report.counts["not_triggered"] == 1

    def test_insufficient_history_is_skipped(self) -> None:
        ds = FakeDataSource()
        ds.frames["AAPL"] = _ohlcv([105])
        monitor = ScanMonitor(ds)
        report = run_dry_run(monitor, _rule(["AAPL"]))
        assert report.skipped == ["AAPL"]

    def test_missing_symbol_is_skipped_not_an_error(self) -> None:
        ds = FakeDataSource()
        monitor = ScanMonitor(ds)
        report = run_dry_run(monitor, _rule(["GHOST"]))
        assert report.skipped == ["GHOST"]

    def test_universe_size_matches_total_symbols(self) -> None:
        ds = FakeDataSource()
        ds.frames["A"] = _ohlcv([90, 95, 105])
        ds.frames["B"] = _ohlcv([50, 55, 60])
        monitor = ScanMonitor(ds)
        report = run_dry_run(monitor, _rule(["A", "B"]))
        assert report.universe_size == 2


class TestDoesNotMutateLiveState:
    def test_real_cooldown_gate_untouched_by_a_dry_run(self) -> None:
        ds = FakeDataSource()
        ds.frames["AAPL"] = _ohlcv([90, 95, 105])
        gate = CooldownGate()
        monitor = ScanMonitor(ds, cooldown_gate=gate)

        run_dry_run(monitor, _rule(["AAPL"]), now=0.0)
        assert gate.state_of("r1", "AAPL") is None  # dry run never touched the real gate

        # A subsequent *real* cycle still sees this as a fresh edge.
        result = monitor.run_cycle(_rule(["AAPL"]), now=0.0)
        assert result.fired == ["AAPL"]

    def test_dry_run_returns_the_underlying_cycle(self) -> None:
        ds = FakeDataSource()
        ds.frames["AAPL"] = _ohlcv([90, 95, 105])
        monitor = ScanMonitor(ds)
        report = run_dry_run(monitor, _rule(["AAPL"]))
        assert report.cycle is not None
        assert report.cycle.fired == ["AAPL"]
