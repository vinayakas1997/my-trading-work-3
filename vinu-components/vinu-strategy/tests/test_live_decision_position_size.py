"""Point 7 option 1 (missing-pieces-of-system/new-theory-of-trading/
system-wide-audit-and-design/reverse-engineering/
06-execution-handoff-and-architecture.md): the sizing field a live
EXECUTE decision needs to actually become an order via LiveScheduler.
"""

from vinu_strategy.api import StrategyAPI
from vinu_strategy.config import VinuStrategyConfig
from vinu_strategy.models.strategy import StrategyConfig


class TestLiveDecisionPositionSizeParsing:
    def test_defaults_to_zero_unsized_when_absent(self) -> None:
        cfg = StrategyConfig.from_dict({"name": "sma_cross", "description": "", "schedule": "15m"})
        assert cfg.live_decision_position_size == 0.0

    def test_parses_an_explicit_value(self) -> None:
        cfg = StrategyConfig.from_dict({
            "name": "sma_cross", "description": "", "schedule": "15m",
            "live_decision_position_size": 0.05,
        })
        assert cfg.live_decision_position_size == 0.05

    def test_not_flagged_as_an_unknown_key(self, caplog) -> None:
        import logging
        with caplog.at_level(logging.WARNING):
            StrategyConfig.from_dict({
                "name": "sma_cross", "description": "", "schedule": "15m",
                "live_decision_position_size": 0.05,
            })
        assert "live_decision_position_size" not in caplog.text


def _make_config(tmp_path, strategies_dir) -> VinuStrategyConfig:
    return VinuStrategyConfig(
        host="127.0.0.1", port=8084,
        data_root=tmp_path / "data", strategies_dir=strategies_dir,
        features_api_url="http://127.0.0.1:8082", correlation_api_url="http://127.0.0.1:8083",
        max_weight=0.25, cash_floor=0.10, rebalance_freq="daily",
        shared_watchlist_path=None,
    )


class TestStrategyAPIExposesPositionSize:
    def test_get_strategy_returns_the_configured_size(self, tmp_path) -> None:
        strategies_dir = tmp_path / "strategies"
        strategies_dir.mkdir()
        (strategies_dir / "sma_cross.yaml").write_text(
            "name: sma_cross\n"
            "description: test\n"
            "schedule: 15m\n"
            "live_decision_position_size: 0.05\n"
        )
        api = StrategyAPI(_make_config(tmp_path, strategies_dir))

        result = api.get_strategy("sma_cross")

        assert result["live_decision_position_size"] == 0.05

    def test_get_strategy_defaults_to_zero_when_not_set(self, tmp_path) -> None:
        strategies_dir = tmp_path / "strategies"
        strategies_dir.mkdir()
        (strategies_dir / "sma_cross.yaml").write_text(
            "name: sma_cross\ndescription: test\nschedule: 15m\n"
        )
        api = StrategyAPI(_make_config(tmp_path, strategies_dir))

        result = api.get_strategy("sma_cross")

        assert result["live_decision_position_size"] == 0.0
