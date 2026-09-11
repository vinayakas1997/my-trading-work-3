from __future__ import annotations

from vinu_screener.pipeline.scorer import FactorSpec, make_weighted_scorer, weighted_score


class TestWeightedScore:
    def test_single_positive_factor(self) -> None:
        factors = (FactorSpec("momentum", "pct_change", weight=10.0),)
        assert weighted_score({"momentum": 0.05}, factors) == 0.5

    def test_negative_weight_penalizes(self) -> None:
        factors = (FactorSpec("rsi", "rsi", weight=-1.0),)
        assert weighted_score({"rsi": 80.0}, factors) == -80.0

    def test_multiple_factors_sum(self) -> None:
        factors = (
            FactorSpec("momentum", "pct_change", weight=10.0),
            FactorSpec("rsi", "rsi", weight=-1.0),
        )
        assert weighted_score({"momentum": 0.1, "rsi": 50.0}, factors) == 1.0 - 50.0

    def test_missing_field_contributes_zero(self) -> None:
        factors = (FactorSpec("momentum", "pct_change", weight=10.0),)
        assert weighted_score({}, factors) == 0.0

    def test_non_finite_field_contributes_zero(self) -> None:
        factors = (FactorSpec("momentum", "pct_change", weight=10.0),)
        assert weighted_score({"momentum": float("nan")}, factors) == 0.0
        assert weighted_score({"momentum": float("inf")}, factors) == 0.0

    def test_no_factors_is_zero(self) -> None:
        assert weighted_score({"anything": 5.0}, ()) == 0.0


class TestFactorSpecRoundTrip:
    def test_from_dict_and_back(self) -> None:
        raw = {"name": "sma_gap", "indicator": "sma", "weight": 2.0, "params": {"period": 20}, "output_field": "value", "offset": 0}
        spec = FactorSpec.from_dict(raw)
        assert spec.to_dict() == raw

    def test_from_dict_defaults(self) -> None:
        spec = FactorSpec.from_dict({"name": "x", "indicator": "close", "weight": 1.0})
        assert spec.params == {}
        assert spec.output_field == "value"
        assert spec.offset == 0


class TestMakeWeightedScorer:
    def test_returns_a_callable_matching_screenpipeline_scorerfn(self) -> None:
        factors = (FactorSpec("momentum", "pct_change", weight=10.0),)
        scorer = make_weighted_scorer(factors)
        assert scorer({"momentum": 0.2}) == 2.0

    def test_scorer_is_independent_per_call(self) -> None:
        factors = (FactorSpec("m", "pct_change", weight=1.0),)
        scorer = make_weighted_scorer(factors)
        assert scorer({"m": 1.0}) == 1.0
        assert scorer({"m": 2.0}) == 2.0
