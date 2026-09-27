import logging
import math
from unittest.mock import patch

from vinu_strategy.engine.pipeline import WeightPipeline
from vinu_strategy.models.strategy import StrategyConfig, PipelineConfig, PipelineStage


class TestSanitizeWeights:
    """item #22 finding #2: no stage anywhere validated weights for
    NaN/inf or the allow_short invariant, regardless of which risk
    method ran -- risk_none() in particular passes weights through
    completely unmodified."""

    def test_finite_weights_pass_through_unchanged(self) -> None:
        clean, issues = WeightPipeline._sanitize_weights(
            {"AAPL": 0.3, "MSFT": -0.1}, allow_short=True,
        )
        assert clean == {"AAPL": 0.3, "MSFT": -0.1}
        assert issues == {}

    def test_nan_weight_is_dropped(self) -> None:
        clean, issues = WeightPipeline._sanitize_weights(
            {"AAPL": 0.3, "BROKEN": float("nan")}, allow_short=True,
        )
        assert "BROKEN" not in clean
        assert clean == {"AAPL": 0.3}
        assert "BROKEN" in issues

    def test_infinite_weight_is_dropped(self) -> None:
        clean, issues = WeightPipeline._sanitize_weights(
            {"AAPL": 0.3, "BROKEN": float("inf")}, allow_short=True,
        )
        assert "BROKEN" not in clean
        assert "BROKEN" in issues

    def test_negative_weight_clamped_to_zero_when_shorts_disallowed(self) -> None:
        clean, issues = WeightPipeline._sanitize_weights(
            {"AAPL": 0.3, "MSFT": -0.1}, allow_short=False,
        )
        assert clean == {"AAPL": 0.3, "MSFT": 0.0}
        assert "MSFT" in issues

    def test_negative_weight_kept_when_shorts_allowed(self) -> None:
        clean, issues = WeightPipeline._sanitize_weights(
            {"AAPL": 0.3, "MSFT": -0.1}, allow_short=True,
        )
        assert clean == {"AAPL": 0.3, "MSFT": -0.1}
        assert issues == {}

    def test_empty_weights_is_a_no_op(self) -> None:
        clean, issues = WeightPipeline._sanitize_weights({}, allow_short=True)
        assert clean == {}
        assert issues == {}


class TestWeightPipelineAppliesTheSanityGateRegardlessOfRiskMethod:
    """Proves the gate runs inside the real run() call, not just in
    isolation -- and specifically that risk_none()'s own pass-through
    (which does nothing to validate its output) still gets caught."""

    def _config(self, method: str = "none") -> StrategyConfig:
        return StrategyConfig(
            name="test", description="", schedule="daily",
            pipeline=PipelineConfig(
                selection=PipelineStage("all"),
                allocation=PipelineStage("equal"),
                timing=PipelineStage("none"),
                risk=PipelineStage(method),
            ),
        )

    def test_a_nan_surviving_risk_none_is_dropped_by_the_pipeline(self) -> None:
        pipeline = WeightPipeline()
        with patch(
            "vinu_strategy.engine.pipeline.run_risk",
            return_value={"AAPL": 0.5, "BROKEN": float("nan")},
        ):
            result, meta = pipeline.run(self._config(), universe=["AAPL", "BROKEN"])

        assert "BROKEN" not in result
        assert result == {"AAPL": 0.5}
        assert "BROKEN" in meta["sanity_issues"]

    def test_a_healthy_run_reports_no_sanity_issues(self) -> None:
        pipeline = WeightPipeline()
        result, meta = pipeline.run(self._config(), universe=["AAPL", "MSFT"])
        assert meta["sanity_issues"] == {}
        assert all(math.isfinite(w) for w in result.values())


class TestSanityIssuesReachTheRealStrategyResult:
    """The pipeline computing sanity_issues into its own internal `meta`
    dict isn't the fix by itself -- StrategyService.evaluate() has to
    actually read it back out, or it's the same "computed, then
    discarded before it leaves the function" shape item #21.3 already
    names three other instances of. Proven through the real evaluate()
    call chain, not just pipeline.run() in isolation."""

    def test_sanity_issues_from_the_pipeline_land_on_strategy_result(self) -> None:
        from unittest.mock import MagicMock

        from vinu_strategy.config import VinuStrategyConfig
        from vinu_strategy.models.strategy import StrategyConfig
        from vinu_strategy.service import StrategyService

        svc = StrategyService.__new__(StrategyService)
        svc._config = VinuStrategyConfig(
            host="127.0.0.1", port=8084, data_root=None, strategies_dir=None,
            features_api_url="", correlation_api_url="",
            max_weight=0.25, cash_floor=0.10, rebalance_freq="daily",
            shared_watchlist_path=None,
        )
        config = StrategyConfig(name="s", description="", schedule="daily")
        svc._registry = MagicMock()
        svc._registry.get.return_value = config
        svc._features_client = MagicMock()
        svc._weight_storage = MagicMock()
        svc._meta_storage = MagicMock()
        svc._pipeline = MagicMock()
        svc._pipeline.run.return_value = (
            {"AAPL": 0.5},
            {"rule_trace": {}, "sanity_issues": {"BROKEN": "non-finite weight nan dropped"}},
        )

        result = svc.evaluate("s", symbols=["AAPL"])

        assert result.sanity_issues == {"BROKEN": "non-finite weight nan dropped"}


class TestShockAwareIsAKnownRiskMethod:
    """item #22 finding #5: engine/risk.py's RISK_METHODS has a working
    "shock_aware" entry, but models/strategy.py's _KNOWN_METHODS["risk"]
    didn't list it -- any strategy using it logged a false "unknown risk
    method" warning at load time despite working correctly at runtime."""

    def test_no_unknown_method_warning_for_shock_aware(self, caplog) -> None:
        with caplog.at_level(logging.WARNING):
            StrategyConfig.from_dict({
                "name": "s", "description": "", "schedule": "daily",
                "pipeline": {"risk": {"method": "shock_aware"}},
            })
        assert "unknown risk method" not in caplog.text.lower()

    def test_a_genuinely_unknown_method_still_warns(self, caplog) -> None:
        """Regression guard for the fix itself -- confirms the warning
        path still works for an actually-unknown method, not just that
        it was suppressed globally."""
        with caplog.at_level(logging.WARNING):
            StrategyConfig.from_dict({
                "name": "s", "description": "", "schedule": "daily",
                "pipeline": {"risk": {"method": "totally_made_up"}},
            })
        assert "unknown risk method" in caplog.text.lower()


class TestWeightPipeline:
    def test_pipeline_runs(self):
        config = StrategyConfig(
            name="test",
            description="test",
            schedule="daily",
            pipeline=PipelineConfig(
                selection=PipelineStage("all"),
                allocation=PipelineStage("equal"),
                timing=PipelineStage("none"),
                risk=PipelineStage("normalize", {"max_weight": 0.25}),
            ),
        )
        pipeline = WeightPipeline()
        result, meta = pipeline.run(config, universe=["AAPL", "MSFT", "GOOGL"])
        assert len(result) == 3
        assert all(w <= 0.25 for w in result.values())
        assert all(w > 0 for w in result.values())
        assert "selection" in meta
        assert "allocation" in meta
        assert "timing" in meta
        assert "risk" in meta

    def test_pipeline_with_signals(self):
        config = StrategyConfig(
            name="test_signal",
            description="test",
            schedule="daily",
            features_required=["MOM_20"],
            pipeline=PipelineConfig(
                selection=PipelineStage("threshold", {"on": "MOM_20", "min": 0.0}),
                allocation=PipelineStage("signal_scaled"),
                timing=PipelineStage("none"),
                risk=PipelineStage("normalize", {"max_weight": 0.5}),
            ),
        )
        pipeline = WeightPipeline()
        feature_signals = {
            "AAPL": {"MOM_20": 1.5, "signal": 1.5},
            "MSFT": {"MOM_20": -0.5, "signal": -0.5},
            "GOOGL": {"MOM_20": 0.0, "signal": 0.0},
        }
        result, meta = pipeline.run(config, universe=["AAPL", "MSFT", "GOOGL"], feature_signals=feature_signals)
        assert "AAPL" in result
        assert result["AAPL"] > 0
        assert result["AAPL"] <= 0.5
        assert "GOOGL" in result

    def test_empty_universe(self):
        config = StrategyConfig(name="empty", description="", schedule="daily")
        pipeline = WeightPipeline()
        result, meta = pipeline.run(config, universe=[])
        assert result == {}
        assert meta["selection"]["candidates"] == 0

    def test_params_missing_max_weight_falls_back_to_risk_stage_default(self):
        """A caller-supplied `params` dict missing max_weight/cash_floor must not
        clobber risk.py's own defaults with an explicit None (regression: this
        used to crash with TypeError comparing float to NoneType)."""
        config = StrategyConfig(
            name="test",
            description="test",
            schedule="daily",
            pipeline=PipelineConfig(
                selection=PipelineStage("all"),
                allocation=PipelineStage("equal"),
                timing=PipelineStage("none"),
                risk=PipelineStage("normalize"),
            ),
        )
        pipeline = WeightPipeline()
        result, meta = pipeline.run(
            config,
            universe=["AAPL", "MSFT"],
            params={"cash_floor": 0.1},
        )
        assert result == {"AAPL": 0.25, "MSFT": 0.25}

    def test_pipeline_with_timing_rules(self):
        config = StrategyConfig(
            name="test_rules",
            description="test",
            schedule="daily",
            pipeline=PipelineConfig(
                selection=PipelineStage("all"),
                allocation=PipelineStage("equal"),
                timing=PipelineStage("rules", {
                    "rules": [
                        {
                            "name": "boost",
                            "when": [{"source": "features", "key": "MOM_20", "gt": 0}],
                            "then": {"action": "weight_multiply", "value": 1.5},
                        }
                    ]
                }),
                risk=PipelineStage("none"),
            ),
        )
        pipeline = WeightPipeline()
        feature_signals = {
            "AAPL": {"MOM_20": 2.0, "signal": 2.0},
        }
        result, meta = pipeline.run(config, universe=["AAPL", "MSFT"], feature_signals=feature_signals)
        assert "rule_trace" in meta
        assert "AAPL" in result
        # AAPL with 2 symbols: equal = 0.5 each, then rule boost 1.5x = 0.75
        assert abs(result["AAPL"] - 0.75) < 0.01
