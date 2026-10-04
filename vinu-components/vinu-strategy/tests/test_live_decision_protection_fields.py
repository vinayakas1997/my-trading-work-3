"""logic-audit-2026-10-02 A3 (the-inconsistencies-v2, plan item 2.3): the two
optional per-strategy protection fields for a live-decision position --
`live_decision_stop_pct` and `live_decision_max_hold_bars`. Both default to 0
(off), like `live_decision_position_size`."""

from __future__ import annotations

import logging

from vinu_strategy.api import StrategyAPI
from vinu_strategy.config import VinuStrategyConfig
from vinu_strategy.models.strategy import StrategyConfig


def _cfg(**extra) -> StrategyConfig:
    return StrategyConfig.from_dict({"name": "sma_cross", "description": "", "schedule": "15m", **extra})


class TestParsing:
    def test_both_default_to_off(self) -> None:
        cfg = _cfg()
        assert cfg.live_decision_stop_pct == 0.0 and cfg.live_decision_max_hold_bars == 0

    def test_parses_explicit_values(self) -> None:
        cfg = _cfg(live_decision_stop_pct=0.05, live_decision_max_hold_bars=40)
        assert cfg.live_decision_stop_pct == 0.05 and cfg.live_decision_max_hold_bars == 40

    def test_null_in_yaml_means_off_not_a_crash(self) -> None:
        cfg = _cfg(live_decision_stop_pct=None, live_decision_max_hold_bars=None)
        assert cfg.live_decision_stop_pct == 0.0 and cfg.live_decision_max_hold_bars == 0

    def test_not_flagged_as_unknown_keys(self, caplog) -> None:
        with caplog.at_level(logging.WARNING):
            _cfg(live_decision_stop_pct=0.05, live_decision_max_hold_bars=40)
        assert "live_decision_stop_pct" not in caplog.text
        assert "live_decision_max_hold_bars" not in caplog.text


def _make_config(tmp_path, strategies_dir) -> VinuStrategyConfig:
    return VinuStrategyConfig(
        host="127.0.0.1", port=8084,
        data_root=tmp_path / "data", strategies_dir=strategies_dir,
        features_api_url="http://127.0.0.1:8082", correlation_api_url="http://127.0.0.1:8083",
        max_weight=0.25, cash_floor=0.10, rebalance_freq="daily",
        shared_watchlist_path=None,
    )


class TestApiExposure:
    def test_get_strategy_returns_the_configured_values(self, tmp_path) -> None:
        d = tmp_path / "strategies"
        d.mkdir()
        (d / "sma_cross.yaml").write_text(
            "name: sma_cross\ndescription: test\nschedule: 15m\n"
            "live_decision_stop_pct: 0.04\nlive_decision_max_hold_bars: 30\n"
        )
        result = StrategyAPI(_make_config(tmp_path, d)).get_strategy("sma_cross")
        assert result["live_decision_stop_pct"] == 0.04
        assert result["live_decision_max_hold_bars"] == 30

    def test_get_strategy_defaults_to_off(self, tmp_path) -> None:
        d = tmp_path / "strategies"
        d.mkdir()
        (d / "sma_cross.yaml").write_text("name: sma_cross\ndescription: test\nschedule: 15m\n")
        result = StrategyAPI(_make_config(tmp_path, d)).get_strategy("sma_cross")
        assert result["live_decision_stop_pct"] == 0.0
        assert result["live_decision_max_hold_bars"] == 0


class TestEdgeContracts:
    def test_get_strategy_matches_the_edge_contracts(self, tmp_path) -> None:
        """Layer B (producer side): the strategy answer validates against both contracts its consumers are checked with."""
        from vinu_infra.edge_contracts import check_payload

        d = tmp_path / "strategies"
        d.mkdir()
        (d / "sma_cross.yaml").write_text(
            "name: sma_cross\ndescription: test\nschedule: 15m\n"
            "live_decision_stop_pct: 0.04\nlive_decision_max_hold_bars: 30\n"
        )
        result = StrategyAPI(_make_config(tmp_path, d)).get_strategy("sma_cross")
        assert check_payload("strategy.config->live.scheduler", result) == []
        assert check_payload("strategy.stop_rules->live.poller", result) == []
