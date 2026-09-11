from __future__ import annotations

from vinu_screener.pipeline.candidate import Candidate
from vinu_screener.pipeline.concentration import ConcentrationConfig, apply_concentration_overlay


def _c(symbol: str, score: float, sector: str | None) -> Candidate:
    c = Candidate(symbol=symbol, fields={}, sector=sector)
    c.factor_score = score
    return c


class TestConcentrationPenalty:
    def test_first_pick_in_a_sector_is_unpenalized(self) -> None:
        candidates = [_c("A", 10.0, "financial"), _c("B", 9.0, "financial")]
        apply_concentration_overlay(candidates, ConcentrationConfig())
        assert candidates[0].concentration_penalty == 0.0

    def test_second_pick_in_same_sector_is_penalized(self) -> None:
        candidates = [_c("A", 10.0, "financial"), _c("B", 9.0, "financial")]
        apply_concentration_overlay(candidates, ConcentrationConfig(penalty_per_repeat=3.0))
        assert candidates[1].concentration_penalty == 3.0

    def test_third_pick_penalized_more(self) -> None:
        candidates = [_c("A", 10.0, "financial"), _c("B", 9.0, "financial"), _c("C", 8.0, "financial")]
        apply_concentration_overlay(candidates, ConcentrationConfig(penalty_per_repeat=3.0))
        assert candidates[2].concentration_penalty == 6.0

    def test_penalty_capped_at_max_penalty(self) -> None:
        candidates = [_c(f"S{i}", 10.0 - i, "financial") for i in range(10)]
        apply_concentration_overlay(candidates, ConcentrationConfig(penalty_per_repeat=5.0, max_penalty=12.0))
        assert candidates[-1].concentration_penalty == 12.0

    def test_different_sectors_do_not_interact(self) -> None:
        candidates = [_c("A", 10.0, "financial"), _c("B", 9.0, "tech")]
        apply_concentration_overlay(candidates, ConcentrationConfig())
        assert candidates[0].concentration_penalty == 0.0
        assert candidates[1].concentration_penalty == 0.0

    def test_bucket_map_canonicalizes_aliases(self) -> None:
        cfg = ConcentrationConfig(bucket_map={"banks": "financial", "insurance": "financial"})
        candidates = [_c("A", 10.0, "banks"), _c("B", 9.0, "insurance")]
        apply_concentration_overlay(candidates, cfg)
        assert candidates[1].concentration_penalty > 0.0

    def test_no_sector_never_penalized(self) -> None:
        candidates = [_c("A", 10.0, None), _c("B", 9.0, None)]
        apply_concentration_overlay(candidates, ConcentrationConfig())
        assert candidates[0].concentration_penalty == 0.0
        assert candidates[1].concentration_penalty == 0.0

    def test_ranked_by_current_final_score_not_input_order(self) -> None:
        # B is listed first but scores lower -- A (scores higher) must be
        # treated as the "first" pick in the sector, not penalized.
        candidates = [_c("B", 5.0, "financial"), _c("A", 10.0, "financial")]
        apply_concentration_overlay(candidates, ConcentrationConfig())
        by_symbol = {c.symbol: c for c in candidates}
        assert by_symbol["A"].concentration_penalty == 0.0
        assert by_symbol["B"].concentration_penalty > 0.0

    def test_dropped_candidates_are_skipped(self) -> None:
        a = _c("A", 10.0, "financial")
        b = _c("B", 9.0, "financial")
        b.dropped_at = "hard_filter"
        apply_concentration_overlay([a, b], ConcentrationConfig())
        assert b.concentration_penalty == 0.0  # never even considered
