"""Stage A (A1, A2 — research-discussion-v1/complete-plan/02-stage-a-quick-wins.md).
Direct unit tests for vinu_portfolio.risk_utils, independent of
PortfolioService's callers (see test_service.py's TestComputeCorrelationMatrix
and TestBuildPortfolio for the integration-level checks)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_portfolio.risk_utils import (
    cap_concentration,
    fix_nonpositive_semidefinite,
    robust_correlation_matrix,
)


def _is_psd(corr: pd.DataFrame) -> bool:
    eigenvalues = np.linalg.eigvalsh(corr.to_numpy())
    return bool(np.all(eigenvalues >= -1e-8))


class TestFixNonpositiveSemidefinite:
    def test_already_psd_matrix_is_returned_unchanged(self) -> None:
        corr = pd.DataFrame(
            [[1.0, 0.3], [0.3, 1.0]], index=["a", "b"], columns=["a", "b"],
        )
        result = fix_nonpositive_semidefinite(corr)
        pd.testing.assert_frame_equal(result, corr)

    def test_non_psd_matrix_is_repaired_to_psd(self) -> None:
        # A classic non-PSD "correlation-like" matrix: pairwise-inconsistent
        # off-diagonal entries (a-b=0.9, b-c=0.9, a-c=-0.9 is not achievable
        # by any real correlation structure).
        corr = pd.DataFrame(
            [
                [1.0, 0.9, -0.9],
                [0.9, 1.0, 0.9],
                [-0.9, 0.9, 1.0],
            ],
            index=["a", "b", "c"], columns=["a", "b", "c"],
        )
        assert not _is_psd(corr)
        fixed = fix_nonpositive_semidefinite(corr)
        assert _is_psd(fixed)

    def test_repaired_matrix_keeps_unit_diagonal(self) -> None:
        corr = pd.DataFrame(
            [[1.0, 0.9, -0.9], [0.9, 1.0, 0.9], [-0.9, 0.9, 1.0]],
            index=["a", "b", "c"], columns=["a", "b", "c"],
        )
        fixed = fix_nonpositive_semidefinite(corr)
        assert np.allclose(np.diag(fixed.to_numpy()), 1.0)

    def test_empty_dataframe_passes_through(self) -> None:
        empty = pd.DataFrame()
        assert fix_nonpositive_semidefinite(empty).empty


class TestRobustCorrelationMatrix:
    def test_none_input_returns_none(self) -> None:
        assert robust_correlation_matrix(None) is None

    def test_single_column_returns_none(self) -> None:
        df = pd.DataFrame({"a": [0.01, 0.02, 0.03]})
        assert robust_correlation_matrix(df) is None

    def test_result_is_always_psd_even_when_shrinkage_fails(self, monkeypatch) -> None:
        import vinu_portfolio.risk_utils as ru
        monkeypatch.setattr(ru, "_shrunk_correlation", lambda returns_df: None)

        rng = np.random.default_rng(1)
        dates = pd.date_range("2024-01-01", periods=10)
        df = pd.DataFrame(
            {"a": rng.normal(size=10), "b": rng.normal(size=10), "c": rng.normal(size=10)},
            index=dates,
        )
        result = robust_correlation_matrix(df)
        assert result is not None
        assert _is_psd(result)

    def test_result_has_unit_diagonal(self) -> None:
        dates = pd.date_range("2024-01-01", periods=20)
        rng = np.random.default_rng(2)
        df = pd.DataFrame(
            {"a": rng.normal(size=20), "b": rng.normal(size=20)}, index=dates,
        )
        result = robust_correlation_matrix(df)
        assert result is not None
        assert np.allclose(np.diag(result.to_numpy()), 1.0)


class TestCapConcentration:
    def test_already_under_cap_is_unchanged(self) -> None:
        w = {"a": 0.25, "b": 0.25, "c": 0.25, "d": 0.25}
        assert cap_concentration(w, 0.30) == w

    def test_over_cap_weight_is_pulled_down_and_excess_redistributed(self) -> None:
        # 4 names, cap 0.30 is feasible (4 * 0.30 = 1.20 >= 1).
        w = {"a": 0.60, "b": 0.20, "c": 0.15, "d": 0.05}
        result = cap_concentration(w, 0.30)
        assert result["a"] == pytest.approx(0.30)
        assert max(result.values()) <= 0.30 + 1e-9
        assert sum(result.values()) == pytest.approx(1.0)

    def test_the_renormalization_undo_bug_it_exists_to_fix(self) -> None:
        # The exact shape from the docstring: pre-normalization min(w, cap)
        # then renormalize used to yield 0.30 / 0.40 = 0.75. cap_concentration
        # applied AFTER normalization must actually hold the cap.
        w = {"a": 0.75, "b": 0.15, "c": 0.10}  # already summed to 1, a way over 0.30
        result = cap_concentration(w, 0.30)
        # 3 names -> effective cap floors at 1/3 (0.30 is infeasible for 3),
        # so 'a' lands at 1/3, not 0.30 -- still a real reduction from 0.75.
        assert result["a"] == pytest.approx(1 / 3)
        assert sum(result.values()) == pytest.approx(1.0)

    def test_infeasible_cap_for_too_few_names_is_a_noop(self) -> None:
        # 2 names, cap 0.30: 2 * 0.30 = 0.60 < 1, impossible. Effective cap
        # floors at 0.5, and 0.5 == 0.5 so nothing is touched.
        w = {"a": 0.5, "b": 0.5}
        assert cap_concentration(w, 0.30) == pytest.approx(w)

    def test_empty_weights(self) -> None:
        assert cap_concentration({}, 0.30) == {}

    def test_cap_of_one_or_more_is_a_noop(self) -> None:
        w = {"a": 0.9, "b": 0.1}
        assert cap_concentration(w, 1.0) == w
