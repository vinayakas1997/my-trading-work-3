from __future__ import annotations

import numpy as np
import pandas as pd


def _geometric_cagr(daily_returns: pd.Series, periods_per_year: int = 252) -> float:
    """
    Compound the actual sequence of daily returns, not their arithmetic mean.
    Compounding a mean return ignores volatility drag and systematically overstates
    CAGR for any series with meaningful variance — the higher the volatility, the
    bigger the overstatement, which makes it especially misleading for the
    single-stock, filter-laden strategies this system tends to produce.
    """
    n = len(daily_returns)
    if n == 0:
        return 0.0
    cumulative = float((1 + daily_returns).prod())
    if cumulative <= 0:
        return -1.0
    return cumulative ** (periods_per_year / n) - 1


def compute_benchmark_returns_metrics(daily_returns: pd.Series) -> dict[str, float]:
    """Compute standard metrics from a benchmark returns series."""
    if len(daily_returns) < 2:
        return {}
    n = len(daily_returns)
    total_return = float((1 + daily_returns).prod() - 1)
    cagr = _geometric_cagr(daily_returns)
    vol = float(daily_returns.std() * np.sqrt(252))
    sharpe = float(daily_returns.mean() / daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0.0
    cumulative = (1 + daily_returns).cumprod()
    running_max = cumulative.expanding().max()
    dd = (cumulative - running_max) / running_max
    max_dd = float(dd.min())
    win_rate = float((daily_returns > 0).sum() / n) if n > 0 else 0.0
    downside = daily_returns[daily_returns < 0]
    downside_vol = float(downside.std() * np.sqrt(252)) if len(downside) > 1 else 0.0
    sortino = float(cagr / downside_vol) if downside_vol > 0 else 0.0

    return {
        "total_return": total_return,
        "cagr": cagr,
        "annual_volatility": vol,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown": max_dd,
        "win_rate": win_rate,
    }


def compute_benchmark_comparison(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> dict[str, float]:
    """Compute alpha, beta, tracking error, information ratio, up/down capture."""
    aligned = pd.concat([strategy_returns, benchmark_returns], axis=1).dropna()
    if len(aligned) < 20:
        return {}

    strat = aligned.iloc[:, 0]
    bench = aligned.iloc[:, 1]
    result: dict[str, float] = {}

    cov_matrix = np.cov(strat, bench)
    bench_var = cov_matrix[1, 1]
    beta = float(cov_matrix[0, 1] / bench_var) if bench_var > 1e-12 else 0.0
    result["beta"] = beta

    rf_daily = (1 + 0.0) ** (1 / 252) - 1
    excess_strat = strat.mean() - rf_daily
    excess_bench = bench.mean() - rf_daily
    alpha_daily = excess_strat - beta * excess_bench
    alpha = float(alpha_daily * 252)
    result["alpha"] = alpha

    excess_returns = strat - bench
    te = float(excess_returns.std() * np.sqrt(252))
    result["tracking_error"] = te
    ir = float((excess_returns.mean() / excess_returns.std() * np.sqrt(252))) if te > 0 else 0.0
    result["information_ratio"] = ir

    bench_up = bench > 0
    bench_down = bench <= 0
    up_cap = float(strat[bench_up].mean() / bench[bench_up].mean()) if bench_up.any() and bench[bench_up].mean() != 0 else 0.0
    down_cap = float(strat[bench_down].mean() / bench[bench_down].mean()) if bench_down.any() and bench[bench_down].mean() != 0 else 0.0
    result["up_capture"] = up_cap
    result["down_capture"] = down_cap
    result["market_correlation"] = float(strat.corr(bench))

    strat_cum = (1 + strat).cumprod()
    bench_cum = (1 + bench).cumprod()
    relative_cum = strat_cum / bench_cum
    running_max = relative_cum.expanding().max()
    relative_dd = (relative_cum - running_max) / running_max
    result["relative_max_drawdown"] = float(relative_dd.min())

    strat_cagr = _geometric_cagr(strat)
    bench_cagr = _geometric_cagr(bench)
    result["excess_cagr"] = strat_cagr - bench_cagr

    return result
