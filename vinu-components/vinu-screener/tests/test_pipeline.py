from __future__ import annotations

from vinu_screener.pipeline.concentration import ConcentrationConfig
from vinu_screener.pipeline.hard_filter import HardFilterConfig
from vinu_screener.pipeline.pipeline import PipelineConfig, ScreenPipeline
from vinu_screener.pipeline.risk_overlay import RiskOverlayConfig
from vinu_screener.pipeline.turnover import TurnoverConfig, TurnoverState


def _score_by_momentum(fields: dict[str, float]) -> float:
    return fields.get("momentum", 0.0)


class TestBasicRun:
    def test_hard_filter_removes_candidates_before_scoring(self) -> None:
        snapshots = {
            "A": {"price": 5.0, "momentum": 10.0},   # fails min_price
            "B": {"price": 50.0, "momentum": 8.0},
        }
        cfg = PipelineConfig(top_n=5, hard_filter=HardFilterConfig(min_price=10.0))
        result = ScreenPipeline(_score_by_momentum, cfg).run(snapshots)
        assert [c.symbol for c in result.ranked] == ["B"]

    def test_ranked_is_sorted_by_final_score_descending(self) -> None:
        snapshots = {"A": {"price": 10.0, "momentum": 5.0}, "B": {"price": 10.0, "momentum": 9.0}}
        result = ScreenPipeline(_score_by_momentum, PipelineConfig(top_n=5)).run(snapshots)
        assert [c.symbol for c in result.ranked] == ["B", "A"]

    def test_top_is_capped_at_top_n(self) -> None:
        snapshots = {f"S{i}": {"price": 10.0, "momentum": float(i)} for i in range(10)}
        result = ScreenPipeline(_score_by_momentum, PipelineConfig(top_n=3)).run(snapshots)
        assert len(result.top) == 3

    def test_trace_reflects_both_chain_stages(self) -> None:
        result = ScreenPipeline(_score_by_momentum, PipelineConfig(top_n=5)).run(
            {"A": {"price": 10.0, "momentum": 1.0}}
        )
        assert [t.stage for t in result.trace] == ["hard_filter", "risk_veto"]


class TestRiskAndConcentration:
    def test_risk_veto_removes_candidate_from_ranked(self) -> None:
        cfg = PipelineConfig(top_n=5, risk=RiskOverlayConfig(veto_penalty_threshold=3.0))
        snapshots = {"A": {"price": 10.0, "momentum": 10.0, "pe": -1.0}, "B": {"price": 10.0, "momentum": 1.0}}
        result = ScreenPipeline(_score_by_momentum, cfg).run(snapshots)
        assert "A" not in [c.symbol for c in result.ranked]

    def test_concentration_penalty_can_flip_the_order(self) -> None:
        cfg = PipelineConfig(
            top_n=5,
            concentration=ConcentrationConfig(penalty_per_repeat=10.0),
        )
        snapshots = {
            "A": {"price": 10.0, "momentum": 10.0},
            "B": {"price": 10.0, "momentum": 9.0},
            "C": {"price": 10.0, "momentum": 8.5},  # different sector, lower raw score
        }
        sectors = {"A": "tech", "B": "tech", "C": "energy"}
        result = ScreenPipeline(_score_by_momentum, cfg).run(snapshots, sectors=sectors)
        symbols = [c.symbol for c in result.ranked]
        # B (tech, 2nd pick) penalized 10 -> effective 9-10=-1, C (energy, 1st pick) unpenalized at 8.5
        assert symbols.index("C") < symbols.index("B")


class TestEnrichment:
    def test_enrich_fn_runs_only_on_top_candidates(self) -> None:
        calls: list[str] = []

        def enrich(symbol: str) -> str:
            calls.append(symbol)
            return f"detail-{symbol}"

        snapshots = {f"S{i}": {"price": 10.0, "momentum": float(i)} for i in range(5)}
        result = ScreenPipeline(_score_by_momentum, PipelineConfig(top_n=2)).run(snapshots, enrich_fn=enrich)
        assert len(calls) == 2
        assert set(calls) == {c.symbol for c in result.top}
        assert result.enrichment[result.top[0].symbol] == f"detail-{result.top[0].symbol}"

    def test_enrich_fn_failure_does_not_drop_candidate(self) -> None:
        def broken(symbol: str) -> str:
            raise RuntimeError("boom")

        snapshots = {"A": {"price": 10.0, "momentum": 1.0}}
        result = ScreenPipeline(_score_by_momentum, PipelineConfig(top_n=5)).run(snapshots, enrich_fn=broken)
        assert result.enrichment["A"] is None
        assert "A" in [c.symbol for c in result.top]


class TestTurnoverIntegration:
    def test_held_set_persists_across_runs(self) -> None:
        state = TurnoverState()
        cfg = PipelineConfig(top_n=2, turnover=TurnoverConfig(top_n=2, hold_thresh=5))
        pipeline = ScreenPipeline(_score_by_momentum, cfg, turnover_state=state)

        snapshots1 = {"A": {"price": 10.0, "momentum": 10.0}, "B": {"price": 10.0, "momentum": 9.0}}
        r1 = pipeline.run(snapshots1)
        assert set(r1.turnover_held) == {"A", "B"}

        # Next cycle: C/D would outrank A/B, but hold_thresh keeps A/B.
        snapshots2 = {
            "A": {"price": 10.0, "momentum": 1.0}, "B": {"price": 10.0, "momentum": 1.0},
            "C": {"price": 10.0, "momentum": 20.0}, "D": {"price": 10.0, "momentum": 19.0},
        }
        r2 = pipeline.run(snapshots2)
        assert set(r2.turnover_held) == {"A", "B"}

    def test_no_turnover_config_skips_the_gate(self) -> None:
        result = ScreenPipeline(_score_by_momentum, PipelineConfig(top_n=5)).run(
            {"A": {"price": 10.0, "momentum": 1.0}}
        )
        assert result.turnover_held is None
