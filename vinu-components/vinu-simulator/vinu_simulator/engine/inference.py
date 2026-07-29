from __future__ import annotations

import math
from statistics import NormalDist

_STANDARD_NORMAL = NormalDist()
_EULER_GAMMA = 0.5772156649015329


def mertens_sharpe_se(
    sharpe: float,
    n: int,
    skew: float = 0.0,
    excess_kurtosis: float = 0.0,
) -> float:
    """
    Mertens (2002) / Opdyke (2007) standard error of the Sharpe ratio.

    Why this matters:
        The classic Lo (2002) formula for Sharpe standard error assumes
        normally distributed returns.  For negatively skewed / fat-tailed
        strategies (common in finance), that SE is too small, making the
        Sharpe look more significant than it really is.  The Mertens
        correction widens the SE to account for non-normal higher moments,
        producing honest confidence intervals and p-values.

    Formula:
        SE = sqrt((1 + 0.5*SR^2 - g3*SR + (g4-3)/4 * SR^2) / (n-1))

    where:
        SR    = annualised Sharpe ratio
        g3    = skewness (0 for a normal distribution)
        g4    = kurtosis (3 for a normal distribution;
                so excess_kurtosis = g4 - 3 = 0 for normal)
        n     = number of return observations

    When skew=0 and excess_kurtosis=0 this collapses to the Lo formula.

    References:
        Mertens, E. (2002). "Comments on variance of the IID estimator in
            Lo (2002)." Working paper.
        Opdyke, J.D. (2007). "Comparing Sharpe ratios: so where are the
            p-values?" Journal of Asset Management, 8(5), 308-336.
        Lo, A.W. (2002). "The Statistics of Sharpe Ratios." Financial
            Analysts Journal, 58(4), 36-52.

    Parameters:
        sharpe: annualised Sharpe ratio.
        n: number of return observations.
        skew: sample skewness (0 for normal).
        excess_kurtosis: sample excess kurtosis (0 for normal).

    Returns:
        Standard error of the Sharpe ratio (same unit as input).
    """
    if n < 2 or sharpe is None:
        return 0.0

    kurt = excess_kurtosis + 3.0
    variance_term = max(1 - skew * sharpe + ((kurt - 1) / 4) * sharpe**2, 1e-12)
    return math.sqrt(variance_term / max(n - 1, 1))


def probabilistic_sharpe_ratio(
    sharpe: float,
    n: int,
    skew: float = 0.0,
    excess_kurtosis: float = 0.0,
    benchmark: float = 0.0,
) -> float:
    """
    Bailey & Lopez de Prado (2012) Probabilistic Sharpe Ratio (PSR).

    The probability that the true (unobserved) Sharpe ratio exceeds a
    given benchmark level, after adjusting for skewness and kurtosis in
    the return distribution.

    Interpretation:
        PSR > 0.95  → strong confidence the true SR exceeds the benchmark.
        PSR ~ 0.50  → coin flip; the observed SR is right on the benchmark.
        PSR < 0.05  → strong confidence the true SR is *below* the benchmark.

    A common benchmark is 0.0 (is the strategy any good at all?).  For
    comparison against a naive buy-and-hold, set benchmark to the
    buy-and-hold Sharpe ratio.

    Formula:
        PSR = Phi((SR - SR_bench) / SE_Mertens)

    where Phi is the standard normal CDF and SE_Mertens is computed via
    ``mertens_sharpe_se``.

    References:
        Bailey, D.H. & Lopez de Prado, M. (2012). "The Sharpe Ratio
            Efficient Frontier." Journal of Risk, 15(2), 3-44.

    Parameters:
        sharpe: annualised Sharpe ratio of the strategy.
        n: number of return observations.
        skew: sample skewness (0 for normal).
        excess_kurtosis: sample excess kurtosis (0 for normal).
        benchmark: reference Sharpe ratio to test against (default 0.0).

    Returns:
        Probability in [0, 1] that the true SR exceeds the benchmark.
    """
    se = mertens_sharpe_se(sharpe, n, skew, excess_kurtosis)
    if se <= 0:
        return 0.5
    z = (sharpe - benchmark) / se
    return float(_STANDARD_NORMAL.cdf(z))


def deflated_sharpe_ratio(
    sharpe: float,
    n_trials: int,
    n_obs: int,
    skew: float = 0.0,
    excess_kurtosis: float = 0.0,
    periods_per_year: float = 252.0,
) -> float:
    """
    Bailey & Lopez de Prado (2014) Deflated Sharpe Ratio (DSR).

    The probability that the observed Sharpe ratio reflects genuine skill
    after accounting for having been selected as the best of *n_trials*
    independent backtests run against the same data.

    Despite the name this returns a *probability* in [0, 1], not a Sharpe
    ratio.

    Interpretation:
        DSR > 0.95  → evidence of real skill under multiple-testing
                       correction (the strategy survived the selection
                       bias adjustment).
        DSR ~ 0.50  → indistinguishable from what pure luck would produce
                       by trying this many strategies.
        DSR < 0.05  → strategy is likely worse than the luck-adjusted
                       benchmark.

    The correction uses the expected maximum of n_trials i.i.d. standard
    normals via the Euler-Mascheroni approximation:

        E[max(Z_1..Z_n)] ~ (1- gamma)*Phi^{-1}(1-1/n)
                          + gamma*Phi^{-1}(1-1/(n*e))

    where gamma is the Euler-Mascheroni constant (~0.5772).

    References:
        Bailey, D.H. & Lopez de Prado, M. (2014). "The Deflated Sharpe
            Ratio: Correcting for Selection Bias, Backtest Overfitting,
            and Non-Normality." Journal of Portfolio Management, 40(5),
            94-107.

    Parameters:
        sharpe: annualised Sharpe ratio of the selected (best) strategy.
        n_trials: number of independent strategy trials / backtests.
        n_obs: number of return observations in the backtest.
        skew: sample skewness (0 for normal).
        excess_kurtosis: sample excess kurtosis (0 for normal).
        periods_per_year: annualisation factor (252 for daily data).

    Returns:
        Probability in [0, 1] that the true SR reflects skill after
        correcting for multiple testing.
    """
    if n_obs < 2 or n_trials < 1:
        return 0.5

    daily_sharpe = sharpe / math.sqrt(periods_per_year) if periods_per_year > 0 else sharpe

    kurt = excess_kurtosis + 3.0
    variance_term = max(1 - skew * daily_sharpe + ((kurt - 1) / 4) * daily_sharpe**2, 1e-12)
    sr_std = math.sqrt(variance_term / max(n_obs - 1, 1))
    if sr_std <= 0:
        return 0.5

    if n_trials <= 1:
        expected_max_sharpe = 0.0
    else:
        z_a = _STANDARD_NORMAL.inv_cdf(1 - 1.0 / n_trials)
        z_b = _STANDARD_NORMAL.inv_cdf(1 - 1.0 / (n_trials * math.e))
        expected_max_sharpe = sr_std * ((1 - _EULER_GAMMA) * z_a + _EULER_GAMMA * z_b)

    z = (daily_sharpe - expected_max_sharpe) / sr_std
    return float(_STANDARD_NORMAL.cdf(z))
