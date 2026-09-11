from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_screener.audit.watch_history import WatchAuditStore
from vinu_screener.conditions.schema import parse_condition
from vinu_screener.rules.store import RuleStore
from vinu_screener.scan.monitor import ScanMonitor, ScanRule
from vinu_screener.scheduler import Scheduler


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


def _rule(rule_id="r1", universe=("AAPL",), mode="persistent") -> ScanRule:
    return ScanRule(
        rule_id=rule_id,
        condition=parse_condition({"indicator": "close", "operator": ">", "value": 100.0}),
        universe=universe,
        mode=mode,
    )


@pytest.fixture
def rule_store():
    return RuleStore(":memory:")


@pytest.fixture
def data_source():
    ds = FakeDataSource()
    ds.frames["AAPL"] = _ohlcv([90, 95, 105])
    return ds


class TestTickRunsDueActiveRules:
    def test_active_rule_runs_on_first_tick(self, rule_store, data_source) -> None:
        rule_store.upsert_rule(_rule())
        scheduler = Scheduler(rule_store, ScanMonitor(data_source))
        results = scheduler.tick(now=0.0)
        assert len(results) == 1
        assert results[0].fired == ["AAPL"]

    def test_inactive_rule_is_skipped(self, rule_store, data_source) -> None:
        rule_store.upsert_rule(_rule(), active=False)
        scheduler = Scheduler(rule_store, ScanMonitor(data_source))
        assert scheduler.tick(now=0.0) == []

    def test_rule_not_yet_due_is_skipped_on_a_second_tick(self, rule_store, data_source) -> None:
        rule_store.upsert_rule(_rule(), interval_sec=60.0)
        scheduler = Scheduler(rule_store, ScanMonitor(data_source))
        scheduler.tick(now=0.0)
        results = scheduler.tick(now=10.0)  # only 10s later, interval is 60s
        assert results == []

    def test_rule_runs_again_once_its_interval_elapses(self, rule_store, data_source) -> None:
        rule_store.upsert_rule(_rule(), interval_sec=60.0)
        scheduler = Scheduler(rule_store, ScanMonitor(data_source))
        scheduler.tick(now=0.0)
        results = scheduler.tick(now=61.0)
        assert len(results) == 1

    def test_multiple_rules_run_independently(self, rule_store, data_source) -> None:
        rule_store.upsert_rule(_rule("r1"), interval_sec=30.0)
        rule_store.upsert_rule(_rule("r2"), interval_sec=600.0)
        scheduler = Scheduler(rule_store, ScanMonitor(data_source))
        scheduler.tick(now=0.0)
        results = scheduler.tick(now=31.0)  # r1 due again, r2 not
        assert len(results) == 1
        assert results[0].rule_id == "r1"


class TestAuditIntegration:
    def test_fires_are_recorded_in_the_audit_store(self, rule_store, data_source) -> None:
        rule_store.upsert_rule(_rule())
        audit = WatchAuditStore(":memory:")
        scheduler = Scheduler(rule_store, ScanMonitor(data_source), audit_store=audit)
        scheduler.tick(now=100.0)
        history = audit.history(rule_id="r1")
        assert len(history) == 1
        assert history[0].symbol == "AAPL"
        assert history[0].fired_at == 100.0

    def test_no_audit_store_is_fine(self, rule_store, data_source) -> None:
        rule_store.upsert_rule(_rule())
        scheduler = Scheduler(rule_store, ScanMonitor(data_source))
        results = scheduler.tick(now=0.0)
        assert results[0].fired == ["AAPL"]  # no error despite no audit store


class TestOnFireCallback:
    def test_on_fire_called_once_per_fired_symbol(self, rule_store, data_source) -> None:
        calls = []
        rule_store.upsert_rule(_rule())
        scheduler = Scheduler(rule_store, ScanMonitor(data_source), on_fire=lambda stored, sym: calls.append((stored.rule.rule_id, sym)))
        scheduler.tick(now=0.0)
        assert calls == [("r1", "AAPL")]

    def test_on_fire_not_called_when_nothing_fires(self, rule_store, data_source) -> None:
        data_source.frames["AAPL"] = _ohlcv([10, 20, 30])  # never above 100
        calls = []
        rule_store.upsert_rule(_rule())
        scheduler = Scheduler(rule_store, ScanMonitor(data_source), on_fire=lambda stored, sym: calls.append(sym))
        scheduler.tick(now=0.0)
        assert calls == []

    def test_a_broken_on_fire_callback_does_not_crash_the_tick(self, rule_store, data_source) -> None:
        rule_store.upsert_rule(_rule())

        def broken(stored, sym):
            raise RuntimeError("boom")

        scheduler = Scheduler(rule_store, ScanMonitor(data_source), on_fire=broken)
        results = scheduler.tick(now=0.0)
        assert results[0].fired == ["AAPL"]


class TestOneShotDeactivation:
    def test_one_shot_rule_is_deactivated_after_firing(self, rule_store, data_source) -> None:
        rule_store.upsert_rule(_rule(mode="one_shot"))
        scheduler = Scheduler(rule_store, ScanMonitor(data_source))
        scheduler.tick(now=0.0)
        assert rule_store.get("r1").active is False

    def test_persistent_rule_stays_active_after_firing(self, rule_store, data_source) -> None:
        rule_store.upsert_rule(_rule(mode="persistent"))
        scheduler = Scheduler(rule_store, ScanMonitor(data_source))
        scheduler.tick(now=0.0)
        assert rule_store.get("r1").active is True

    def test_deactivated_one_shot_rule_does_not_run_again(self, rule_store, data_source) -> None:
        rule_store.upsert_rule(_rule(mode="one_shot"), interval_sec=30.0)
        scheduler = Scheduler(rule_store, ScanMonitor(data_source))
        scheduler.tick(now=0.0)
        results = scheduler.tick(now=100.0)
        assert results == []


class TestErrorIsolation:
    def test_one_rule_raising_does_not_stop_the_others(self, rule_store, data_source) -> None:
        rule_store.upsert_rule(_rule("bad"))
        rule_store.upsert_rule(_rule("good"))

        class BoomMonitor(ScanMonitor):
            def run_cycle(self, rule, *, now=None):
                if rule.rule_id == "bad":
                    raise RuntimeError("boom")
                return super().run_cycle(rule, now=now)

        scheduler = Scheduler(rule_store, BoomMonitor(data_source))
        results = scheduler.tick(now=0.0)
        assert [r.rule_id for r in results] == ["good"]
