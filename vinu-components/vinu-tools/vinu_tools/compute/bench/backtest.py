from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd


WeightScheme = Literal["equal", "rank", "vol_parity", "top_quantile"]


@dataclass
class FactorBacktestResult:
    """Result of a factor backtest simulation."""

    portfolio_returns: pd.Series
    long_returns: pd.Series
    short_returns: pd.Series
    positions: pd.DataFrame
    metrics: dict[str, float]
    equity_curve: pd.Series
    drawdown_series: pd.Series
    turnover_series: pd.Series | None = None


def _annualization_factor(freq: str) -> float:
    return {
        "1d": 252,
        "1h": 252 * 6.5,
        "30min": 252 * 6.5 * 2,
        "5min": 252 * 6.5 * 12,
        "1w": 52,
        "1mo": 12,
    }.get(freq, 252)


def _compute_metrics(returns: pd.Series, freq: str = "1d") -> dict[str, float]:
    ann = _annualization_factor(freq)

    # Basic return stats
    total_return = float((1 + returns).prod() - 1) if len(returns) > 0 else 0.0
    mean_return = float(returns.mean())
    std_return = float(returns.std())

    # Risk-adjusted ratios
    sharpe = float(mean_return / std_return * np.sqrt(ann)) if std_return > 0 else 0.0

    downside = returns[returns < 0]
    downside_std = float(downside.std()) if len(downside) > 1 else 1e-6
    sortino = float(mean_return / downside_std * np.sqrt(ann)) if downside_std > 0 else 0.0

    # Drawdown
    eq = (1 + returns).cumprod()
    running_max = eq.cummax()
    dd = (eq - running_max) / running_max
    max_dd = float(dd.min()) if len(dd) > 0 else 0.0

    calmar = float(total_return / abs(max_dd)) if max_dd < 0 else 0.0

    # Win rate
    wins = (returns > 0).sum()
    total_trades = len(returns)
    win_rate = float(wins / total_trades) if total_trades > 0 else 0.0

    # Profit factor
    gross_profit = float(returns[returns > 0].sum())
    gross_loss = float(abs(returns[returns < 0].sum()))
    profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else float("inf")

    # Volatility (annualized)
    ann_vol = float(std_return * np.sqrt(ann))

    return {
        "total_return": round(total_return, 6),
        "annualized_return": round(total_return / (len(returns) / ann) if len(returns) > 0 else 0.0, 6),
        "annualized_vol": round(ann_vol, 6),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "max_drawdown": round(max_dd, 6),
        "calmar_ratio": round(calmar, 4),
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 4),
        "n_periods": len(returns),
    }


def backtest_factor(
    factor_values: pd.DataFrame,
    forward_returns: pd.DataFrame,
    weight_scheme: WeightScheme = "equal",
    long_quantile: float = 0.2,
    short_quantile: float = 0.2,
    top_n: int | None = None,
    freq: str = "1d",
    compute_turnover: bool = False,
) -> FactorBacktestResult:
    """Backtest a factor by simulating long/short portfolio returns.

    At each time step, the top quantile of stocks (by factor value) are
    held long and the bottom quantile are held short. Portfolio weights
    depend on ``weight_scheme``.

    Args:
        factor_values: T x N DataFrame of factor values.
        forward_returns: T x N DataFrame of period-ahead returns.
        weight_scheme: How to weight positions:
            - ``"equal"``: equal weight within long and short legs.
            - ``"rank"``: weight proportional to cross-sectional rank.
            - ``"vol_parity"``: inverse-vol weighted within each leg.
            - ``"top_quantile"``: long only (top quantile).
        long_quantile: Top fraction to go long (default 0.2 = top 20%).
        short_quantile: Bottom fraction to go short (default 0.2 = bottom 20%).
        top_n: If set, use top N stocks instead of quantile.
        freq: Frequency string for annualization (``"1d"``, ``"1h"``, etc.).
        compute_turnover: Whether to compute position turnover over time.

    Returns:
        ``FactorBacktestResult`` with return series, positions, and metrics.
    """
    common_idx = factor_values.index.intersection(forward_returns.index)
    if len(common_idx) == 0:
        raise ValueError("No overlapping dates between factor and forward returns")

    fv = factor_values.loc[common_idx]
    fr = forward_returns.loc[common_idx]

    ann = _annualization_factor(freq)
    n_assets = fv.shape[1]

    positions_list: list[pd.Series] = []
    portfolio_returns_list: list[float] = []
    long_returns_list: list[float] = []
    short_returns_list: list[float] = []

    for t in common_idx:
        f_t = fv.loc[t]
        r_t = fr.loc[t]

        valid = f_t.notna() & r_t.notna()
        f_valid = f_t[valid]
        r_valid = r_t[valid]

        if len(f_valid) < 10:
            portfolio_returns_list.append(0.0)
            long_returns_list.append(0.0)
            short_returns_list.append(0.0)
            positions_list.append(pd.Series(0.0, index=fr.columns))
            continue

        # Rank stocks by factor value
        ranks = f_valid.rank()
        n = len(ranks)

        if top_n is not None:
            long_mask = ranks >= (n - top_n + 1)
            short_mask = ranks <= top_n
        else:
            long_cut = int(n * (1 - long_quantile))
            short_cut = int(n * short_quantile)
            long_mask = ranks >= long_cut + 1 if long_cut < n else ranks > 0
            short_mask = ranks <= short_cut if long_cut > 0 else ranks < 0

        long_idx = ranks[long_mask].index
        short_idx = ranks[short_mask].index

        # Build weights
        weight = pd.Series(0.0, index=ranks.index)

        if weight_scheme == "equal" or weight_scheme == "top_quantile":
            if len(long_idx) > 0:
                weight[long_idx] = 1.0 / len(long_idx)
            if weight_scheme != "top_quantile" and len(short_idx) > 0:
                weight[short_idx] = -1.0 / len(short_idx)
        elif weight_scheme == "rank":
            long_weights = ranks[long_idx] - ranks[long_idx].min() + 1
            weight[long_idx] = long_weights / long_weights.sum()
            if weight_scheme != "top_quantile" and len(short_idx) > 0:
                short_weights = ranks[short_idx].max() + 1 - ranks[short_idx]
                weight[short_idx] = -short_weights / short_weights.sum()
        elif weight_scheme == "vol_parity":
            if len(long_idx) > 0:
                vol = r_valid[long_idx].std()
                weight[long_idx] = (1.0 / vol) if vol > 0 else 0.0
                weight_sum = weight[long_idx].sum()
                if weight_sum > 0:
                    weight[long_idx] /= weight_sum
            if len(short_idx) > 0:
                vol = r_valid[short_idx].std()
                w = (1.0 / vol) if vol > 0 else 0.0
                weight[short_idx] = -w / abs(weight[short_idx]).sum() if abs(weight[short_idx]).sum() > 0 else 0.0

        # Build full position vector (all assets, 0 for non-selected)
        pos = pd.Series(0.0, index=fr.columns)
        pos[weight.index] = weight
        positions_list.append(pos)

        period_return = float((pos * r_valid).sum())
        portfolio_returns_list.append(period_return)

        long_pos = pos.clip(lower=0)
        short_pos = -pos.clip(upper=0)
        long_ret = float((long_pos * r_valid).sum())
        short_ret = float((short_pos * r_valid).sum())
        long_returns_list.append(long_ret)
        short_returns_list.append(short_ret)

    portfolio_returns = pd.Series(portfolio_returns_list, index=common_idx, name="portfolio_returns")
    long_returns = pd.Series(long_returns_list, index=common_idx, name="long_returns")
    short_returns = pd.Series(short_returns_list, index=common_idx, name="short_returns")
    positions = pd.DataFrame(positions_list, index=common_idx)

    equity_curve = (1 + portfolio_returns).cumprod()
    running_max = equity_curve.cummax()
    drawdown_series = (equity_curve - running_max) / running_max

    metrics = _compute_metrics(portfolio_returns, freq)

    turnover_series = None
    if compute_turnover and len(positions) > 1:
        to = []
        for i in range(1, len(positions)):
            prev = positions.iloc[i - 1]
            curr = positions.iloc[i]
            changed = (prev.abs() > 0) | (curr.abs() > 0)
            to.append(float((prev[changed] - curr[changed]).abs().sum() / 2))
        turnover_series = pd.Series(to, index=positions.index[1:], name="turnover")
        metrics["mean_turnover"] = round(float(turnover_series.mean()), 4)

    return FactorBacktestResult(
        portfolio_returns=portfolio_returns,
        long_returns=long_returns,
        short_returns=short_returns,
        positions=positions,
        metrics=metrics,
        equity_curve=equity_curve,
        drawdown_series=drawdown_series,
        turnover_series=turnover_series,
    )


def compare_factors(
    factor_dict: dict[str, pd.DataFrame],
    forward_returns: pd.DataFrame,
    weight_scheme: WeightScheme = "equal",
    long_quantile: float = 0.2,
    freq: str = "1d",
) -> pd.DataFrame:
    """Run backtest for multiple factors and return a comparison table.

    Args:
        factor_dict: Dict mapping factor name to its T x N DataFrame.
        forward_returns: T x N DataFrame of forward returns.
        weight_scheme: Portfolio weighting scheme.
        long_quantile: Top/bottom quantile.
        freq: Frequency for annualization.

    Returns:
        DataFrame with one row per factor, columns = metric name.
    """
    rows: list[dict[str, Any]] = []
    for name, fv in factor_dict.items():
        try:
            result = backtest_factor(fv, forward_returns, weight_scheme=weight_scheme,
                                      long_quantile=long_quantile, freq=freq)
            rows.append({"factor": name, **result.metrics})
        except Exception as e:
            rows.append({"factor": name, "error": str(e)})
    return pd.DataFrame(rows).set_index("factor") if rows else pd.DataFrame()
