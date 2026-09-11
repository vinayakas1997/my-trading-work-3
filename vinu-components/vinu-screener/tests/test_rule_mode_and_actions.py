from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_screener.conditions.schema import parse_condition
from vinu_screener.rules.actions import ActionsConfig
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


def _rule(**overrides) -> ScanRule:
    defaults = dict(
        rule_id="r1",
        condition=parse_condition({"indicator": "close", "operator": ">", "value": 100.0}),
        universe=("AAPL",),
    )
    defaults.update(overrides)
    return ScanRule(**defaults)


class TestScanRuleDefaults:
    def test_mode_defaults_to_persistent(self) -> None:
        assert _rule().mode == "persistent"

    def test_actions_default_to_toast_only(self) -> None:
        assert _rule().actions == ActionsConfig()

    def test_invalid_mode_rejected(self) -> None:
        with pytest.raises(ValueError):
            _rule(mode="whenever")


class TestFromDictB16B18:
    def test_parses_actions_and_mode(self) -> None:
        raw = {
            "rule_id": "r1",
            "condition": {"indicator": "close", "operator": ">", "value": 1},
            "universe": ["A"],
            "actions": {"toast": False, "providers": {"telegram": True}},
            "mode": "one_shot",
        }
        rule = ScanRule.from_dict(raw)
        assert rule.mode == "one_shot"
        assert rule.actions.providers == {"telegram": True}


class TestOneShotDeactivation:
    def test_persistent_rule_never_signals_deactivation(self) -> None:
        ds = FakeDataSource()
        ds.frames["AAPL"] = _ohlcv([90, 95, 105])
        monitor = ScanMonitor(ds)
        result = monitor.run_cycle(_rule(mode="persistent"))
        assert result.fired == ["AAPL"]
        assert result.deactivate_rule is False

    def test_one_shot_rule_signals_deactivation_when_it_fires(self) -> None:
        ds = FakeDataSource()
        ds.frames["AAPL"] = _ohlcv([90, 95, 105])
        monitor = ScanMonitor(ds)
        result = monitor.run_cycle(_rule(mode="one_shot"))
        assert result.fired == ["AAPL"]
        assert result.deactivate_rule is True

    def test_one_shot_rule_does_not_deactivate_when_it_does_not_fire(self) -> None:
        ds = FakeDataSource()
        ds.frames["AAPL"] = _ohlcv([90, 95, 50])  # never crosses 100
        monitor = ScanMonitor(ds)
        result = monitor.run_cycle(_rule(mode="one_shot"))
        assert result.fired == []
        assert result.deactivate_rule is False
