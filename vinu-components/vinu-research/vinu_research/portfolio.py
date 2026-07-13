from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class PortfolioAnalysisResult:
    symbols: list[str]
    correlation_matrix: dict[str, dict[str, float]]
    avg_pairwise_correlation: float
    raw_sharpe: float
    raw_max_drawdown: float
    raw_annual_vol: float
    hedged_sharpe: float
    hedged_max_drawdown: float
    hedged_annual_vol: float
    final_beta_estimate: float
    beta_hedge_lookback_days: int
    n_observations: int = 0


def compute_correlation_matrix(returns_by_symbol: dict[str, pd.Series]) -> pd.DataFrame:
    """Pairwise correlation of daily returns across a traded universe."""
    return pd.DataFrame(returns_by_symbol).corr()


def compute_rolling_beta(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    lookback_days: int = 60,
) -> pd.Series:
    """
    Rolling beta of the portfolio to the benchmark, estimated causally: the beta
    used to size a hedge on day t is computed from data through day t-1 only,
    never day t's own return. This mirrors the same shift(1) causality pattern
    used in the T+1 execution fix and the position sizers — a hedge ratio that
    "knew" today's return before sizing today's hedge would just be a different
    flavor of look-ahead bias.
    """
    aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1).dropna()
    aligned.columns = ["portfolio", "benchmark"]

    cov = aligned["portfolio"].rolling(lookback_days).cov(aligned["benchmark"])
    var = aligned["benchmark"].rolling(lookback_days).var()
    beta = (cov / var.replace(0.0, np.nan)).fillna(0.0)
    return beta.shift(1).fillna(0.0)


def compute_beta_hedged_returns(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    lookback_days: int = 60,
    max_hedge_ratio: float = 1.5,
) -> tuple[pd.Series, pd.Series]:
    """
    Analytically overlays a beta-neutral hedge on the portfolio's own realized
    returns: hedged_return[t] = portfolio_return[t] - beta[t] * benchmark_return[t],
    where beta[t] is estimated using only data through t-1. This is mathematically
    equivalent to actually shorting `beta[t] * portfolio_value` worth of the
    benchmark on day t-1 and holding it through day t — a linear hedge overlay's
    P&L can be computed directly from the return series without re-running the
    trade-by-trade simulation engine.

    Returns (hedged_returns, beta_series_used).
    """
    aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1).dropna()
    aligned.columns = ["portfolio", "benchmark"]

    beta = compute_rolling_beta(aligned["portfolio"], aligned["benchmark"], lookback_days)
    beta_clipped = beta.clip(-max_hedge_ratio, max_hedge_ratio)

    hedged = aligned["portfolio"] - beta_clipped * aligned["benchmark"]
    return hedged, beta_clipped


def _sharpe(returns: pd.Series) -> float:
    if len(returns) < 2 or returns.std() == 0:
        return 0.0
    return float(returns.mean() / returns.std() * np.sqrt(252))


def _max_drawdown(returns: pd.Series) -> float:
    if len(returns) < 2:
        return 0.0
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    return float(drawdown.min())


def analyze_portfolio(
    returns_by_symbol: dict[str, pd.Series],
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    lookback_days: int = 60,
    max_hedge_ratio: float = 1.5,
) -> PortfolioAnalysisResult | None:
    """
    Universe correlation + a raw-vs-beta-hedged comparison of the portfolio's own
    realized returns. Returns None if there isn't enough data to say anything
    meaningful (fewer than 2 symbols, or too short a history for the rolling
    beta window to ever populate) rather than reporting a number computed from
    an unreliable sample.
    """
    if len(returns_by_symbol) < 2:
        return None
    if len(portfolio_returns) < lookback_days + 5 or len(benchmark_returns) < lookback_days + 5:
        return None

    corr_df = compute_correlation_matrix(returns_by_symbol)
    n = len(corr_df)
    if n > 1:
        off_diag_sum = float(corr_df.values.sum() - np.trace(corr_df.values))
        avg_corr = off_diag_sum / (n * (n - 1))
    else:
        avg_corr = 0.0

    hedged_returns, beta_series = compute_beta_hedged_returns(
        portfolio_returns, benchmark_returns, lookback_days, max_hedge_ratio,
    )
    if len(hedged_returns) < lookback_days + 5:
        return None

    raw_aligned = portfolio_returns.reindex(hedged_returns.index).dropna()
    hedged_aligned = hedged_returns.reindex(raw_aligned.index)

    return PortfolioAnalysisResult(
        symbols=sorted(returns_by_symbol.keys()),
        correlation_matrix=corr_df.round(4).to_dict(),
        avg_pairwise_correlation=avg_corr,
        raw_sharpe=_sharpe(raw_aligned),
        raw_max_drawdown=_max_drawdown(raw_aligned),
        raw_annual_vol=float(raw_aligned.std() * np.sqrt(252)),
        hedged_sharpe=_sharpe(hedged_aligned),
        hedged_max_drawdown=_max_drawdown(hedged_aligned),
        hedged_annual_vol=float(hedged_aligned.std() * np.sqrt(252)),
        final_beta_estimate=float(beta_series.iloc[-1]) if len(beta_series) else 0.0,
        beta_hedge_lookback_days=lookback_days,
        n_observations=len(raw_aligned),
    )
