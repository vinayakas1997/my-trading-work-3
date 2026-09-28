"""item #22 finding #3 (missing-pieces-of-system/new-theory-of-trading/
system-wide-audit-and-design/02-open-questions-strategy-and-simulation.md):
"point-in-time safety is fully delegated upstream, with no verification
at this layer." `FeaturesClient.get_features()` used to be called with
no `as_of` at all, so each symbol's HTTP call reflected whatever
vinu-tools considered "now" at the exact moment it happened to execute,
not one consistent instant for the whole run. Same
`StrategyService.__new__` lightweight-service pattern
test_data_quality.py's own end-to-end test already uses.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from vinu_strategy.config import VinuStrategyConfig
from vinu_strategy.models.strategy import StrategyConfig
from vinu_strategy.service import StrategyService


def _config(**overrides) -> StrategyConfig:
    return StrategyConfig(name="s", description="", schedule="daily", **overrides)


def _make_service(config) -> StrategyService:
    svc = StrategyService.__new__(StrategyService)
    svc._config = VinuStrategyConfig(
        host="127.0.0.1", port=8084, data_root=None, strategies_dir=None,
        features_api_url="", correlation_api_url="",
        max_weight=0.25, cash_floor=0.10, rebalance_freq="daily",
        shared_watchlist_path=None,
    )
    svc._registry = MagicMock()
    svc._registry.get.return_value = config
    svc._features_client = MagicMock()
    svc._features_client.get_features.return_value = {}
    svc._weight_storage = MagicMock()
    svc._meta_storage = MagicMock()
    svc._pipeline = MagicMock()
    svc._pipeline.run.return_value = ({"AAPL": 0.0, "MSFT": 0.0}, {"rule_trace": {}})
    return svc


class TestAsOfThreadedIntoFeatureFetches:
    def test_an_explicit_as_of_is_passed_through_unchanged(self) -> None:
        config = _config(features_required=["rsi_14"])
        svc = _make_service(config)

        svc.evaluate("s", symbols=["AAPL"], as_of=1_700_000_000)

        svc._features_client.get_features.assert_called_once_with(
            "AAPL", indicators=["rsi_14"], as_of=1_700_000_000,
        )

    def test_no_as_of_given_defaults_to_real_wall_clock_now(self) -> None:
        import time

        config = _config(features_required=["rsi_14"])
        svc = _make_service(config)

        before = int(time.time())
        svc.evaluate("s", symbols=["AAPL"])
        after = int(time.time())

        called_as_of = svc._features_client.get_features.call_args.kwargs["as_of"]
        assert before <= called_as_of <= after

    def test_every_symbol_in_one_run_shares_the_same_as_of(self) -> None:
        """The whole point of capturing it once at the top of evaluate() --
        every symbol's HTTP call in this run must see the same instant,
        not each landing at whatever "now" happens to be when its own
        call executes."""
        config = _config(features_required=["rsi_14"])
        svc = _make_service(config)

        svc.evaluate("s", symbols=["AAPL", "MSFT"])

        calls = svc._features_client.get_features.call_args_list
        assert len(calls) == 2
        as_of_values = {c.kwargs["as_of"] for c in calls}
        assert len(as_of_values) == 1

    def test_as_of_is_surfaced_on_the_result_metadata(self) -> None:
        config = _config(features_required=["rsi_14"])
        svc = _make_service(config)

        result = svc.evaluate("s", symbols=["AAPL"], as_of=1_700_000_000)

        assert result.metadata["as_of"] == 1_700_000_000

    def test_no_features_required_never_calls_features_client_at_all(self) -> None:
        """Nothing to thread as_of into if the strategy never asked for
        any features -- confirms this fix didn't introduce an
        unconditional call where none existed before."""
        config = _config(features_required=[])
        svc = _make_service(config)

        svc.evaluate("s", symbols=["AAPL"])

        svc._features_client.get_features.assert_not_called()
