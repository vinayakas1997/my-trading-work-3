"""Benchmark Comparison — single-symbol rolling alpha, beta, tracking error, IR, up/down capture"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone

from vinu_initial_analysis.angles._helpers import periods_per_year


def compute(
    symbol: str,
    bars: pd.DataFrame | None = None,
    news: list[dict] | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    time_format: str | None = None,
) -> pd.DataFrame:
    rows = []
    if bars is None:
        bars = pd.DataFrame()
    if bars.empty:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": datetime.now(timezone.utc).isoformat(),
            "angle": "benchmark_comparison",
            "status": "no_data",
        }])

    close = bars["close"].astype(float)
    returns = close.pct_change().dropna()
    analysis_at = datetime.now(timezone.utc).isoformat()

    if len(returns) < 10:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "benchmark_comparison",
            "status": "insufficient_data",
            "n_observations": len(returns),
        }])

    rets = returns.values
    n = len(rets)

    eq_wt_bench = returns.rolling(min(21, len(returns) // 2)).mean().dropna()

    common = returns.loc[eq_wt_bench.index].dropna()
    bench = eq_wt_bench.dropna()
    combined = pd.DataFrame({"strat": common, "bench": bench}).dropna()

    if len(combined) < 5:
        r_b = returns.mean()
        r_s = returns - r_b
        r_s_flat = r_s.values if hasattr(r_s, 'values') else np.array(r_s)
        r_b_flat = np.full_like(r_s_flat, r_b)
        beta = 0.0
        alpha = float(returns.mean())
        te = float(returns.std())
        ir = alpha / te if te > 0 else 0.0
        excess_cagr = 0.0
        up_days = returns > r_b
        down_days = returns < r_b
        up_capture = float(returns[up_days].mean() / r_b) if up_days.any() and r_b != 0 else np.nan
        down_capture = float(returns[down_days].mean() / r_b) if down_days.any() and r_b != 0 else np.nan
        market_corr = 0.0
    else:
        r_s = combined["strat"].values
        r_b = combined["bench"].values
        r_s_flat = r_s
        r_b_flat = r_b
        beta = float(np.cov(r_s, r_b)[0, 1] / np.var(r_b)) if np.var(r_b) > 0 else 0.0
        alpha = float(np.mean(r_s) - beta * np.mean(r_b))
        te = float(np.std(r_s - beta * r_b))
        ir = alpha / te if te > 0 else 0.0
        ppy = periods_per_year(time_format)
        excess_cagr = float((1 + r_s).prod() ** (ppy / len(r_s)) - 1 - ((1 + r_b).prod() ** (ppy / len(r_b)) - 1))
        up_days = r_b > 0
        down_days = r_b < 0
        up_capture = float(np.mean(r_s[up_days]) / np.mean(r_b[up_days])) if up_days.any() and np.mean(r_b[up_days]) != 0 else np.nan
        down_capture = float(np.mean(r_s[down_days]) / np.mean(r_b[down_days])) if down_days.any() and np.mean(r_b[down_days]) != 0 else np.nan
        market_corr = float(np.corrcoef(r_s, r_b)[0, 1])

    equity_ratio = (1 + pd.Series(r_s)).cumprod() / (1 + pd.Series(r_b)).cumprod()
    running_max_ratio = equity_ratio.cummax()
    rel_max_dd = float((equity_ratio - running_max_ratio).div(running_max_ratio).min())

    rows.append({
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": "benchmark_comparison",
        "metric": "benchmark_relative",
        "benchmark": "trailing_mean",
        "beta": round(beta, 4),
        "alpha": round(alpha, 6),
        "tracking_error": round(te, 4),
        "information_ratio": round(ir, 4),
        "excess_cagr": round(excess_cagr, 6),
        "up_capture": round(up_capture, 4) if not np.isnan(up_capture) else None,
        "down_capture": round(down_capture, 4) if not np.isnan(down_capture) else None,
        "market_corr": round(market_corr, 4),
        "relative_max_drawdown": round(rel_max_dd, 6),
        "n_observations": len(combined) if len(combined) >= 5 else min(len(r_s_flat), len(r_b_flat)),
    })

    for window in [21, 63, 126]:
        roll_beta = returns.rolling(window).cov(eq_wt_bench) / eq_wt_bench.rolling(window).var()
        roll_alpha = returns - roll_beta * eq_wt_bench
        row = {
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "benchmark_comparison",
            "metric": f"rolling_{window}d",
            "benchmark": "trailing_mean",
            "rolling_beta_mean": float(roll_beta.mean()),
            "rolling_beta_std": float(roll_beta.std()),
            "rolling_alpha_mean": float(roll_alpha.mean()),
            "rolling_alpha_std": float(roll_alpha.std()),
        }
        rows.append(row)

    return pd.DataFrame(rows)
