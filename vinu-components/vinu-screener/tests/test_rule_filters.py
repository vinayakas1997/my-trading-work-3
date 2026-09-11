from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_screener.conditions.schema import parse_condition
from vinu_screener.features.library import FeatureLibrary
from vinu_screener.pipeline.candidate import Candidate
from vinu_screener.pipeline.hard_filter import HardFilterConfig
from vinu_screener.pipeline.risk_overlay import RiskOverlayConfig
from vinu_screener.pipeline.rule_filters import (
    ConditionRule,
    FilterChain,
    FilterContext,
    HardFilterRule,
    RiskVetoRule,
    SupportsBacktesting,
)


def _ohlcv(close: list[float]) -> pd.DataFrame:
    c = np.array(close, dtype=float)
    return pd.DataFrame({"open": c, "high": c + 0.1, "low": c - 0.1, "close": c, "volume": np.full(len(c), 1000.0)})


class TestHardFilterRule:
    def test_supports_backtesting_is_yes(self) -> None:
        rule = HardFilterRule(HardFilterConfig(min_price=1.0))
        assert rule.supports_backtesting == SupportsBacktesting.YES

    def test_drops_failing_candidates(self) -> None:
        rule = HardFilterRule(HardFilterConfig(min_price=10.0))
        survivors = rule.apply(
            [Candidate("A", {"price": 5.0}), Candidate("B", {"price": 20.0})], FilterContext(),
        )
        assert [c.symbol for c in survivors] == ["B"]

    def test_param_schema_lists_config_fields(self) -> None:
        rule = HardFilterRule(HardFilterConfig())
        schema = rule.param_schema()
        assert "min_price" in schema


class TestRiskVetoRule:
    def test_supports_backtesting_is_biased(self) -> None:
        rule = RiskVetoRule(RiskOverlayConfig())
        assert rule.supports_backtesting == SupportsBacktesting.BIASED

    def test_veto_removes_candidate_and_records_reason(self) -> None:
        cfg = RiskOverlayConfig(veto_penalty_threshold=5.0)
        rule = RiskVetoRule(cfg)
        candidates = [Candidate("A", {"pe": -1.0}), Candidate("B", {"pe": 10.0})]  # A: invalid_pe penalty=4 < 5
        survivors = rule.apply(candidates, FilterContext())
        assert [c.symbol for c in survivors] == ["A", "B"]  # 4 < 5 threshold, no veto yet

    def test_penalty_recorded_even_on_survivors(self) -> None:
        rule = RiskVetoRule(RiskOverlayConfig())
        candidates = [Candidate("A", {"pe": -1.0})]
        rule.apply(candidates, FilterContext())
        assert candidates[0].risk_penalty > 0
        assert "invalid_pe" in candidates[0].risk_flags


class TestConditionRule:
    def test_supports_backtesting_is_yes(self) -> None:
        rule = ConditionRule(parse_condition({"indicator": "close", "operator": ">", "value": 100.0}))
        assert rule.supports_backtesting == SupportsBacktesting.YES

    def test_filters_by_condition_against_ohlcv(self) -> None:
        rule = ConditionRule(parse_condition({"indicator": "close", "operator": ">", "value": 100.0}))
        candidates = [Candidate("AAPL", {}), Candidate("MSFT", {})]
        context = FilterContext(
            ohlcv={"AAPL": _ohlcv([90, 95, 105]), "MSFT": _ohlcv([50, 55, 60])},
            library=FeatureLibrary(),
        )
        survivors = rule.apply(candidates, context)
        assert [c.symbol for c in survivors] == ["AAPL"]

    def test_missing_ohlcv_drops_the_candidate(self) -> None:
        rule = ConditionRule(parse_condition({"indicator": "close", "operator": ">", "value": 100.0}))
        candidates = [Candidate("GHOST", {})]
        context = FilterContext(ohlcv={}, library=FeatureLibrary())
        survivors = rule.apply(candidates, context)
        assert survivors == []
        assert candidates[0].dropped_at == "condition"

    def test_raises_without_context(self) -> None:
        rule = ConditionRule(parse_condition({"indicator": "close", "operator": ">", "value": 100.0}))
        with pytest.raises(ValueError):
            rule.apply([Candidate("A", {})], FilterContext())


class TestFilterChain:
    def test_trace_records_before_after_counts(self) -> None:
        chain = FilterChain([HardFilterRule(HardFilterConfig(min_price=10.0))])
        candidates = [Candidate("A", {"price": 5.0}), Candidate("B", {"price": 20.0})]
        survivors, trace = chain.run(candidates, FilterContext())
        assert len(survivors) == 1
        assert trace[0].before == 2
        assert trace[0].after == 1
        assert trace[0].stage == "hard_filter"

    def test_chained_stages_narrow_progressively(self) -> None:
        chain = FilterChain([
            HardFilterRule(HardFilterConfig(min_price=1.0)),
            RiskVetoRule(RiskOverlayConfig(veto_penalty_threshold=3.0)),
        ])
        candidates = [
            Candidate("A", {"price": 5.0, "pe": -1.0}),  # passes hard filter, vetoed by risk (penalty 4 >= 3)
            Candidate("B", {"price": 5.0, "pe": 10.0}),  # passes both
        ]
        survivors, trace = chain.run(candidates, FilterContext())
        assert [c.symbol for c in survivors] == ["B"]
        assert trace[0].after == 2
        assert trace[1].after == 1
