"""Reference-value tests for the Sharpe-inference statistics that back the
BENCHING -> ACTIVE promotion gate (vinu_research.promotion reads
`artifact.deflated_sharpe`, produced by this module via
walk_forward.deflated_sharpe_ratio).

Stage A (A23): the deflated-Sharpe gate is safety-critical and had *zero*
direct test coverage. These pin each function against its published
closed form -- in particular deflated_sharpe_ratio against the explicit
Bailey & Lopez de Prado (2014) / VectorBT `nb_trials` expected-maximum
formula, recomputed independently here -- so a future refactor of the
multiple-testing math can't silently move the promotion bar.
"""

from __future__ import annotations

import math
from statistics import NormalDist

import pytest

from vinu_simulator.engine.inference import (
    deflated_sharpe_ratio,
    mertens_sharpe_se,
    probabilistic_sharpe_ratio,
)

_N = NormalDist()
_GAMMA = 0.5772156649015329


class TestMertensSharpeSE:
    def test_collapses_to_lo_2002_under_normality(self) -> None:
        # skew=0, excess_kurtosis=0  =>  SE = sqrt((1 + 0.5*SR^2) / (n-1))
        sr, n = 1.5, 250
        expected = math.sqrt((1.0 + 0.5 * sr**2) / (n - 1))
        assert mertens_sharpe_se(sr, n) == pytest.approx(expected, rel=1e-12)

    def test_non_normal_moments_widen_the_se(self) -> None:
        sr, n = 1.5, 250
        lo = mertens_sharpe_se(sr, n)
        # negative skew + fat tails -> the honest SE is larger
        widened = mertens_sharpe_se(sr, n, skew=-0.8, excess_kurtosis=4.0)
        assert widened > lo

    def test_degenerate_inputs_return_zero(self) -> None:
        assert mertens_sharpe_se(1.0, 1) == 0.0
        assert mertens_sharpe_se(None, 250) == 0.0  # type: ignore[arg-type]


class TestProbabilisticSharpeRatio:
    def test_sr_equal_to_benchmark_is_a_coin_flip(self) -> None:
        assert probabilistic_sharpe_ratio(1.0, 250, benchmark=1.0) == pytest.approx(0.5)

    def test_matches_phi_of_z(self) -> None:
        sr, n, bench = 1.2, 300, 0.0
        se = mertens_sharpe_se(sr, n)
        expected = _N.cdf((sr - bench) / se)
        assert probabilistic_sharpe_ratio(sr, n, benchmark=bench) == pytest.approx(expected, rel=1e-12)

    def test_higher_sr_gives_higher_psr(self) -> None:
        lo = probabilistic_sharpe_ratio(0.5, 250)
        hi = probabilistic_sharpe_ratio(2.5, 250)
        assert 0.0 <= lo < hi <= 1.0


def _reference_dsr(
    sharpe: float, n_trials: int, n_obs: int,
    skew: float = 0.0, excess_kurtosis: float = 0.0, periods_per_year: float = 252.0,
) -> float:
    """Independent recomputation of Bailey & Lopez de Prado (2014) DSR --
    the same closed form VectorBT documents for its `nb_trials` deflation."""
    if n_obs < 2 or n_trials < 1:
        return 0.5
    daily_sr = sharpe / math.sqrt(periods_per_year) if periods_per_year > 0 else sharpe
    kurt = excess_kurtosis + 3.0
    var_term = max(1 - skew * daily_sr + ((kurt - 1) / 4) * daily_sr**2, 1e-12)
    sr_std = math.sqrt(var_term / max(n_obs - 1, 1))
    if sr_std <= 0:
        return 0.5
    if n_trials <= 1:
        e_max = 0.0
    else:
        z_a = _N.inv_cdf(1 - 1.0 / n_trials)
        z_b = _N.inv_cdf(1 - 1.0 / (n_trials * math.e))
        e_max = sr_std * ((1 - _GAMMA) * z_a + _GAMMA * z_b)
    return float(_N.cdf((daily_sr - e_max) / sr_std))


class TestDeflatedSharpeRatio:
    @pytest.mark.parametrize(
        "sharpe,n_trials,n_obs,skew,kurt",
        [
            (2.0, 1, 500, 0.0, 0.0),
            (2.0, 50, 500, 0.0, 0.0),
            (2.0, 50, 500, -0.5, 2.0),
            (1.0, 200, 750, -1.2, 6.0),
            (3.5, 10, 252, 0.3, 1.0),
        ],
    )
    def test_matches_the_reference_closed_form(self, sharpe, n_trials, n_obs, skew, kurt) -> None:
        got = deflated_sharpe_ratio(sharpe, n_trials, n_obs, skew=skew, excess_kurtosis=kurt)
        want = _reference_dsr(sharpe, n_trials, n_obs, skew=skew, excess_kurtosis=kurt)
        assert got == pytest.approx(want, rel=1e-12)

    def test_one_trial_equals_psr_against_zero(self) -> None:
        # With n_trials=1 the expected-max deflation is 0, so DSR is just
        # PSR(benchmark=0). Cross-checks the two independent implementations
        # against each other (periods_per_year=1 so both use the same SR unit).
        sr, n = 1.4, 400
        dsr = deflated_sharpe_ratio(sr, 1, n, periods_per_year=1.0)
        psr = probabilistic_sharpe_ratio(sr, n, benchmark=0.0)
        assert dsr == pytest.approx(psr, rel=1e-12)

    def test_more_trials_strictly_lowers_the_probability(self) -> None:
        probs = [deflated_sharpe_ratio(2.0, k, 500) for k in (1, 5, 25, 100, 500)]
        assert probs == sorted(probs, reverse=True)
        assert all(0.0 <= p <= 1.0 for p in probs)

    def test_degenerate_inputs_return_half(self) -> None:
        assert deflated_sharpe_ratio(2.0, 10, 1) == 0.5
        assert deflated_sharpe_ratio(2.0, 0, 500) == 0.5

    def test_threshold_behaviour_at_the_gate(self) -> None:
        # A strong, lightly-selected strategy clears the 0.95 promotion bar;
        # the same Sharpe found as the best of very many trials does not.
        strong = deflated_sharpe_ratio(2.5, 3, 750)
        overfit = deflated_sharpe_ratio(2.5, 5000, 750)
        assert strong > 0.95
        assert overfit < 0.95
