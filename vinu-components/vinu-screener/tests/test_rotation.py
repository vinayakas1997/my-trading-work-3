from __future__ import annotations

from vinu_screener.pipeline.candidate import Candidate
from vinu_screener.pipeline.rotation import RotationConfig, near_score_rotation


def _ranked(scores: list[float]) -> list[Candidate]:
    out = []
    for i, s in enumerate(scores):
        c = Candidate(symbol=f"S{i}", fields={})
        c.factor_score = s
        out.append(c)
    return out


class TestNoRotationNeeded:
    def test_fewer_candidates_than_top_n_is_a_no_op(self) -> None:
        ranked = _ranked([10, 9, 8])
        result = near_score_rotation(ranked, RotationConfig(top_n=5), seed=1)
        assert [c.symbol for c in result] == [c.symbol for c in ranked]

    def test_disabled_returns_alive_candidates_unchanged(self) -> None:
        ranked = _ranked([10, 9, 8, 7])
        result = near_score_rotation(ranked, RotationConfig(top_n=2, enabled=False), seed=1)
        assert [c.symbol for c in result] == [c.symbol for c in ranked]


class TestProtection:
    def test_top_half_is_never_reordered(self) -> None:
        # 10 candidates, tight scores throughout -- front half must be untouched.
        scores = [10.0 - 0.1 * i for i in range(10)]
        ranked = _ranked(scores)
        result = near_score_rotation(ranked, RotationConfig(top_n=8, band=1.5), seed=42)
        front_half_symbols = [c.symbol for c in ranked[:5]]
        result_front_half = [c.symbol for c in result[:5]]
        assert result_front_half == front_half_symbols

    def test_score_is_never_mutated_by_rotation(self) -> None:
        ranked = _ranked([10.0, 9.5, 9.0, 8.8, 8.5, 8.3])
        original_scores = {c.symbol: c.factor_score for c in ranked}
        result = near_score_rotation(ranked, RotationConfig(top_n=3, band=1.5), seed=7)
        for c in result:
            assert c.factor_score == original_scores[c.symbol]

    def test_far_below_cutoff_candidate_is_protected_from_perturbation(self) -> None:
        # Candidate way below the band should stay in its slot even though
        # it's in the "bottom half" positionally.
        scores = [10.0, 9.9, 9.8, 9.7, 9.6, 9.5, 1.0]
        ranked = _ranked(scores)
        result = near_score_rotation(ranked, RotationConfig(top_n=6, band=0.5), seed=3)
        assert result[-1].symbol == ranked[-1].symbol  # the 1.0-score outlier stays last


class TestDeterminism:
    def test_same_seed_gives_same_order(self) -> None:
        scores = [10.0 - 0.1 * i for i in range(12)]
        r1 = near_score_rotation(_ranked(scores), RotationConfig(top_n=8, band=1.5), seed=99)
        r2 = near_score_rotation(_ranked(scores), RotationConfig(top_n=8, band=1.5), seed=99)
        assert [c.symbol for c in r1] == [c.symbol for c in r2]

    def test_membership_is_preserved(self) -> None:
        scores = [10.0 - 0.1 * i for i in range(12)]
        ranked = _ranked(scores)
        result = near_score_rotation(ranked, RotationConfig(top_n=8, band=1.5), seed=5)
        assert {c.symbol for c in result} == {c.symbol for c in ranked}

    def test_dead_candidates_are_excluded(self) -> None:
        ranked = _ranked([10, 9, 8, 7, 6])
        ranked[2].vetoed = True
        result = near_score_rotation(ranked, RotationConfig(top_n=2, band=1.5), seed=1)
        assert ranked[2].symbol not in [c.symbol for c in result]
