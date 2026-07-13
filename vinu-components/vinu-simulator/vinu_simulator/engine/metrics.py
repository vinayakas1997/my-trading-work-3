from __future__ import annotations

import numpy as np
import pandas as pd


def compute_performance_metrics(
    portfolio_values: pd.Series,
    daily_returns: pd.Series,
    risk_free_rate: float = 0.0,
) -> dict[str, float]:
    if len(portfolio_values) < 2 or len(daily_returns) < 1:
        return _empty_metrics()

    initial_value = portfolio_values.iloc[0]
    total_return = (portfolio_values.iloc[-1] / initial_value - 1) if initial_value > 0 else 0.0
    num_days = len(daily_returns)
    cagr = (1 + total_return) ** (252 / max(num_days, 1)) - 1

    daily_vol = float(daily_returns.std()) if len(daily_returns) > 1 else 0.0
    annual_vol = daily_vol * np.sqrt(252)

    rf_daily = (1 + risk_free_rate) ** (1 / 252) - 1
    excess_daily = daily_returns - rf_daily
    excess_mean = float(excess_daily.mean()) if len(excess_daily) > 1 else 0.0
    sharpe = (
        (excess_mean / daily_vol * np.sqrt(252) if daily_vol > 0 else 0.0)
        if len(daily_returns) > 1
        else 0.0
    )

    downside = daily_returns[daily_returns < 0]
    downside_std = float(downside.std()) if len(downside) > 1 else 0.0
    annual_downside = downside_std * np.sqrt(252)
    sortino = (cagr / annual_downside) if annual_downside > 0 else 0.0

    cumulative = (
        portfolio_values / initial_value if initial_value > 0
        else pd.Series(0.0, index=portfolio_values.index)
    )
    running_max = cumulative.expanding().max()
    drawdown_series = (cumulative - running_max) / running_max
    max_dd = float(drawdown_series.min())

    calmar = (cagr / abs(max_dd)) if max_dd < 0 else 0.0

    up_days = (daily_returns > 0).sum()
    win_rate = up_days / len(daily_returns) if len(daily_returns) > 0 else 0.0

    skewness = float(daily_returns.skew()) if len(daily_returns) > 2 else 0.0
    kurtosis = float(daily_returns.kurtosis()) if len(daily_returns) > 2 else 0.0

    return {
        "total_return": total_return,
        "cagr": cagr,
        "annual_volatility": annual_vol,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown": max_dd,
        "calmar_ratio": calmar,
        "win_rate": win_rate,
        "skewness": skewness,
        "kurtosis": kurtosis,
    }


def _empty_metrics() -> dict[str, float]:
    return {
        "total_return": 0.0,
        "cagr": 0.0,
        "annual_volatility": 0.0,
        "sharpe_ratio": 0.0,
        "sortino_ratio": 0.0,
        "max_drawdown": 0.0,
        "calmar_ratio": 0.0,
        "win_rate": 0.0,
        "skewness": 0.0,
        "kurtosis": 0.0,
    }
