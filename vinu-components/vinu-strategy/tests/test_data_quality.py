"""item #22 finding #1 (missing-pieces-of-system/new-theory-of-trading/
system-wide-audit-and-design/02-open-questions-strategy-and-simulation.md):
BaseClient._request swallows every upstream failure and returns `{}`,
which service.py's feature/correlation/angle fetches used to silently
absorb into a 0.0 default -- nothing anywhere flagged the run as
degraded. `_compute_data_quality` is the fix: the concrete
`{symbol: {missing_sources, is_degraded}}` field this finding specified.
"""

from __future__ import annotations

from vinu_strategy.models.strategy import StrategyConfig
from vinu_strategy.service import StrategyService


def _config(**overrides) -> StrategyConfig:
    return StrategyConfig(name="s", description="", schedule="daily", **overrides)


def _compute_data_quality(*args, **kwargs):
    # Static method -- no instance/registry/storage construction needed,
    # same pattern test_reduce_angle.py already uses for _reduce_angle.
    return StrategyService._compute_data_quality(*args, **kwargs)


class TestComputeDataQuality:
    def test_all_sources_present_is_not_flagged(self) -> None:
        config = _config(features_required=["rsi_14"], correlation_required=["impact"])
        result = _compute_data_quality(
            ["AAPL"], config,
            feature_signals={"AAPL": {"rsi_14": 55.0, "signal": 0.1}},
            correlation_signals={"AAPL": {"impact": 0.3}},
            angle_signals={},
        )
        assert result == {}

    def test_missing_features_is_flagged(self) -> None:
        config = _config(features_required=["rsi_14"])
        result = _compute_data_quality(
            ["AAPL"], config,
            feature_signals={},  # AAPL never got an entry -- fetch failed/empty
            correlation_signals={}, angle_signals={},
        )
        assert result == {"AAPL": {"missing_sources": ["features"], "is_degraded": True}}

    def test_missing_correlation_is_flagged(self) -> None:
        config = _config(correlation_required=["impact"])
        result = _compute_data_quality(
            ["AAPL"], config,
            feature_signals={}, correlation_signals={"AAPL": {}},  # empty -- all fetches failed
            angle_signals={},
        )
        assert result == {"AAPL": {"missing_sources": ["correlation"], "is_degraded": True}}

    def test_missing_angles_is_flagged(self) -> None:
        config = _config(angles_required=["regime_analysis"])
        result = _compute_data_quality(
            ["AAPL"], config,
            feature_signals={}, correlation_signals={}, angle_signals={"AAPL": {}},
        )
        assert result == {"AAPL": {"missing_sources": ["angles"], "is_degraded": True}}

    def test_multiple_missing_sources_for_one_symbol(self) -> None:
        config = _config(features_required=["rsi_14"], angles_required=["regime_analysis"])
        result = _compute_data_quality(
            ["AAPL"], config,
            feature_signals={}, correlation_signals={}, angle_signals={"AAPL": {}},
        )
        assert result["AAPL"]["missing_sources"] == ["features", "angles"]

    def test_a_source_never_required_is_never_flagged_as_missing(self) -> None:
        """Only sources the strategy actually asked for count -- a source
        that was never requested was never expected to be there."""
        config = _config()  # nothing required
        result = _compute_data_quality(
            ["AAPL"], config,
            feature_signals={}, correlation_signals={}, angle_signals={},
        )
        assert result == {}

    def test_result_is_sparse_healthy_symbols_are_absent_not_marked_false(self) -> None:
        config = _config(features_required=["rsi_14"])
        result = _compute_data_quality(
            ["AAPL", "MSFT"], config,
            feature_signals={"AAPL": {"rsi_14": 55.0}},  # MSFT missing
            correlation_signals={}, angle_signals={},
        )
        assert "AAPL" not in result
        assert "MSFT" in result

    def test_evaluate_surfaces_data_quality_on_the_real_result(self) -> None:
        """End-to-end proof through the real evaluate() path, not just the
        static helper in isolation."""
        from unittest.mock import MagicMock

        from vinu_strategy.config import VinuStrategyConfig
        svc = StrategyService.__new__(StrategyService)
        svc._config = VinuStrategyConfig(
            host="127.0.0.1", port=8084, data_root=None, strategies_dir=None,
            features_api_url="", correlation_api_url="",
            max_weight=0.25, cash_floor=0.10, rebalance_freq="daily",
            shared_watchlist_path=None,
        )
        config = _config(features_required=["rsi_14"])
        svc._registry = MagicMock()
        svc._registry.get.return_value = config
        svc._features_client = MagicMock()
        svc._features_client.get_features.return_value = {}  # simulates the real failure mode
        svc._weight_storage = MagicMock()
        svc._meta_storage = MagicMock()
        svc._pipeline = MagicMock()
        svc._pipeline.run.return_value = ({"AAPL": 0.0}, {"rule_trace": {}})

        result = svc.evaluate("s", symbols=["AAPL"])

        assert result.data_quality == {"AAPL": {"missing_sources": ["features"], "is_degraded": True}}
