from vinu_strategy.engine.pipeline import WeightPipeline
from vinu_strategy.models.strategy import StrategyConfig, PipelineConfig, PipelineStage


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
