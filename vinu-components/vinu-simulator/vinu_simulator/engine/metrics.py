from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from vinu_simulator.engine.inference import (
    mertens_sharpe_se,
    probabilistic_sharpe_ratio,
)

# Trading day = 6.5h (390min) on US equities. periods_per_year is "how many bars
# of this size occur in a 252-trading-day year" — the annualization factor for
# CAGR/vol/Sharpe/etc. Wrong for non-equity calendars, but this is what the rest
# of the pipeline (session filters, market-hours-only correlation) assumes too.
_BARS_PER_DAY = {
    "1m": 390.0,
    "5m": 78.0,
    "15m": 26.0,
    "30m": 13.0,
    "1h": 6.5,
    "4h": 1.625,
    "1d": 1.0,
}


def periods_per_year_for_interval(interval: str) -> float:
    bars_per_day = _BARS_PER_DAY.get((interval or "1d").strip().lower(), 1.0)
    return bars_per_day * 252.0


def compute_performance_metrics(
    portfolio_values: pd.Series,
    daily_returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: float = 252.0,
) -> dict[str, float]:
    if len(portfolio_values) < 2 or len(daily_returns) < 1:
        return _empty_metrics()

    initial_value = portfolio_values.iloc[0]
    total_return = (portfolio_values.iloc[-1] / initial_value - 1) if initial_value > 0 else 0.0
    num_days = len(daily_returns)
    cagr = (1 + total_return) ** (periods_per_year / max(num_days, 1)) - 1

    daily_vol = float(daily_returns.std()) if len(daily_returns) > 1 else 0.0
    annual_vol = daily_vol * np.sqrt(periods_per_year)

    rf_daily = (1 + risk_free_rate) ** (1 / periods_per_year) - 1
    excess_daily = daily_returns - rf_daily
    excess_mean = float(excess_daily.mean()) if len(excess_daily) > 1 else 0.0
    sharpe = (
        (excess_mean / daily_vol * np.sqrt(periods_per_year) if daily_vol > 0 else 0.0)
        if len(daily_returns) > 1
        else 0.0
    )

    downside = daily_returns[daily_returns < 0]
    downside_std = float(downside.std()) if len(downside) > 1 else 0.0
    annual_downside = downside_std * np.sqrt(periods_per_year)
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


def compute_extended_metrics(
    portfolio_values: pd.Series,
    daily_returns: pd.Series,
    trades: list | None = None,
    benchmark_returns: pd.Series | None = None,
    risk_free_rate: float = 0.0,
    periods_per_year: float = 252.0,
) -> dict[str, float]:
    if len(portfolio_values) < 2 or len(daily_returns) < 1:
        return {}

    extended = {}

    sorted_rets = daily_returns.sort_values()
    var_95 = float(sorted_rets.quantile(0.05))
    var_99 = float(sorted_rets.quantile(0.01))
    cvar_95 = float(sorted_rets[sorted_rets <= var_95].mean()) if (sorted_rets <= var_95).any() else var_95
    tail_ratio = float(sorted_rets.quantile(0.95) / abs(sorted_rets.quantile(0.05))) if abs(sorted_rets.quantile(0.05)) > 0 else 0.0

    extended["var_95"] = var_95
    extended["var_99"] = var_99
    extended["cvar_95"] = cvar_95
    extended["tail_ratio"] = tail_ratio

    cumulative = portfolio_values / portfolio_values.iloc[0]
    running_max = cumulative.expanding().max()
    drawdown_series = (cumulative - running_max) / running_max

    in_drawdown = drawdown_series < 0
    dd_streaks = (in_drawdown != in_drawdown.shift()).cumsum()
    dd_durations = in_drawdown.groupby(dd_streaks).sum()
    max_dd_duration = int(dd_durations.max()) if len(dd_durations) > 0 else 0

    avg_dd = float(drawdown_series[drawdown_series < 0].mean()) if (drawdown_series < 0).any() else 0.0

    max_dd_iloc = int(drawdown_series.idxmin()) if hasattr(drawdown_series.idxmin(), "__int__") else 0
    post_dd_values = drawdown_series.iloc[max_dd_iloc:]
    recovery_iloc = None
    for i, val in enumerate(post_dd_values):
        if val >= 0:
            recovery_iloc = max_dd_iloc + i
            break
    recovery_days = (recovery_iloc - max_dd_iloc) if recovery_iloc is not None else None

    extended["max_dd_duration_days"] = max_dd_duration
    extended["avg_drawdown"] = avg_dd
    extended["recovery_time_days"] = recovery_days if recovery_days is not None else len(daily_returns)

    wins = daily_returns[daily_returns > 0]
    losses = daily_returns[daily_returns < 0]

    # Capped rather than literal inf when there are no losing days — inf is not
    # valid JSON and would fail to serialize at the API boundary.
    _NO_LOSSES_SENTINEL = 999.0
    profit_factor = float(wins.sum() / abs(losses.sum())) if abs(losses.sum()) > 0 else _NO_LOSSES_SENTINEL
    avg_win_pct = float(wins.mean()) if len(wins) > 0 else 0.0
    avg_loss_pct = float(losses.mean()) if len(losses) > 0 else 0.0
    win_loss_ratio = abs(avg_win_pct / avg_loss_pct) if avg_loss_pct != 0 else _NO_LOSSES_SENTINEL
    hit_rate = len(wins) / len(daily_returns) if len(daily_returns) > 0 else 0.0

    extended["profit_factor"] = profit_factor
    extended["avg_win_pct"] = avg_win_pct
    extended["avg_loss_pct"] = avg_loss_pct
    extended["win_loss_ratio"] = win_loss_ratio
    extended["hit_rate"] = hit_rate

    if benchmark_returns is not None:
        aligned = pd.concat([daily_returns, benchmark_returns], axis=1).dropna()
        if len(aligned) > 20:
            strat_rets = aligned.iloc[:, 0]
            bench_rets = aligned.iloc[:, 1]

            beta = float(strat_rets.cov(bench_rets) / bench_rets.var()) if bench_rets.var() > 0 else 0.0
            annual_factor = periods_per_year
            rf_daily = (1 + risk_free_rate) ** (1 / annual_factor) - 1
            excess_strat = strat_rets.mean() - rf_daily
            excess_bench = bench_rets.mean() - rf_daily
            alpha_daily = excess_strat - beta * excess_bench
            alpha = alpha_daily * annual_factor

            excess_ret = strat_rets - bench_rets
            tracking_error = float(excess_ret.std() * np.sqrt(annual_factor))
            info_ratio = float((strat_rets.mean() - bench_rets.mean()) / excess_ret.std() * np.sqrt(annual_factor)) if excess_ret.std() > 0 else 0.0
            correlation = float(strat_rets.corr(bench_rets))

            extended["beta"] = beta
            extended["alpha"] = alpha
            extended["tracking_error"] = tracking_error
            extended["information_ratio"] = info_ratio
            extended["market_correlation"] = correlation

            up_capture = float(strat_rets[bench_rets > 0].mean() / bench_rets[bench_rets > 0].mean()) if (bench_rets > 0).any() and bench_rets[bench_rets > 0].mean() != 0 else 0.0
            down_capture = float(strat_rets[bench_rets <= 0].mean() / bench_rets[bench_rets <= 0].mean()) if (bench_rets <= 0).any() and bench_rets[bench_rets <= 0].mean() != 0 else 0.0
            extended["up_capture"] = up_capture
            extended["down_capture"] = down_capture

    n = len(daily_returns)
    skewness = float(daily_returns.skew()) if len(daily_returns) > 2 else 0.0
    kurtosis = float(daily_returns.kurtosis()) if len(daily_returns) > 2 else 0.0

    extended["sharpe_standard_error"] = 0.0
    extended["sharpe_p_value"] = 1.0
    extended["sharpe_ci_95_low"] = 0.0
    extended["sharpe_ci_95_high"] = 0.0
    extended["probabilistic_sharpe_ratio"] = 0.5

    basic_sharpe = _get_basic_sharpe(portfolio_values, daily_returns, risk_free_rate, periods_per_year) if n > 1 else None
    if basic_sharpe is not None:
        sharpe_se = mertens_sharpe_se(basic_sharpe, n, skewness, kurtosis)
        extended["sharpe_standard_error"] = sharpe_se
        if sharpe_se > 0:
            z = abs(basic_sharpe / sharpe_se)
            sharpe_p_value = float(2 * scipy_stats.norm.sf(z))
            extended["sharpe_p_value"] = max(min(sharpe_p_value, 1.0), 1e-300)
            extended["sharpe_ci_95_low"] = basic_sharpe - 1.96 * sharpe_se
            extended["sharpe_ci_95_high"] = basic_sharpe + 1.96 * sharpe_se
            extended["probabilistic_sharpe_ratio"] = probabilistic_sharpe_ratio(
                basic_sharpe, n, skewness, kurtosis, benchmark=0.0,
            )

    if trades is not None and len(trades) > 0:
        first = trades[0]
        if isinstance(first, dict):
            total_traded_value = sum(abs(t.get("shares", 0) * t.get("price", 0)) for t in trades if isinstance(t, dict))
        else:
            total_traded_value = sum(abs(t.shares) * t.price for t in trades if hasattr(t, "shares") and hasattr(t, "price"))

        avg_portfolio_value = float(portfolio_values.mean())
        num_days = len(daily_returns)
        annual_turnover = (total_traded_value / avg_portfolio_value) * (periods_per_year / num_days) if avg_portfolio_value > 0 and num_days > 0 else 0.0
        extended["annual_turnover"] = annual_turnover
    else:
        extended["annual_turnover"] = 0.0

    return extended


def compute_full_metrics(
    portfolio_values: pd.Series,
    daily_returns: pd.Series,
    trades: list | None = None,
    benchmark_returns: pd.Series | None = None,
    risk_free_rate: float = 0.0,
    periods_per_year: float = 252.0,
    full: bool = True,
) -> dict[str, float]:
    basic = compute_performance_metrics(portfolio_values, daily_returns, risk_free_rate, periods_per_year)
    if not full:
        return {
            k: (0.0 if isinstance(v, float) and not np.isfinite(v) else v)
            for k, v in basic.items()
        }
    extended = compute_extended_metrics(portfolio_values, daily_returns, trades, benchmark_returns, risk_free_rate, periods_per_year)
    merged = {**basic, **extended}
    # inf/-inf/nan are not valid JSON and would break API responses (profit_factor,
    # win_loss_ratio, and others can hit a zero denominator on a flat/no-trade run) —
    # sanitize at this single choke point rather than auditing every formula above.
    return {
        k: (0.0 if isinstance(v, float) and not np.isfinite(v) else v)
        for k, v in merged.items()
    }


def _get_basic_sharpe(
    portfolio_values: pd.Series,
    daily_returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: float = 252.0,
) -> float | None:
    if len(daily_returns) < 2:
        return None
    rf_daily = (1 + risk_free_rate) ** (1 / periods_per_year) - 1
    excess = daily_returns - rf_daily
    if excess.std() > 0:
        return float(excess.mean() / excess.std() * np.sqrt(periods_per_year))
    return 0.0


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
