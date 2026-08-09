"""Backtesting Metrics — Sharpe, Sortino, MaxDD, WinRate, CAGR, VaR, CVaR, tail ratio, skew, kurtosis"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Any

from vinu_initial_analysis.angles._helpers import periods_per_year, ann_factor


def _core_metrics(rets: np.ndarray, time_format: str | None) -> dict[str, Any]:
    """The 11 "core" (time-sliceable) metrics plus ann_vol, computed over
    whatever window of returns is passed in. Shared by compute() (whole
    history) and the rolling walk-forward backtest (backtest.py, a
    trailing window per step) so both compute identically -- no formula
    duplicated between them.
    """
    n = len(rets)
    af = ann_factor(time_format)
    ppy = periods_per_year(time_format)

    total_return = float((1 + rets).prod() - 1)
    cagr = float((1 + total_return) ** (ppy / n) - 1) if n > 0 else 0.0
    ann_vol = float(rets.std() * af)
    sharpe = cagr / ann_vol if ann_vol > 0 else 0.0
    sortino_ratio = cagr / (rets[rets < 0].std() * af) if (rets[rets < 0].std() * af) > 0 else 0.0

    cum = (1 + rets).cumprod()
    running_max = np.maximum.accumulate(cum)
    drawdowns = (cum - running_max) / running_max
    max_dd = float(drawdowns.min())

    win_rate = float((rets > 0).mean())
    avg_win = float(rets[rets > 0].mean()) if (rets > 0).any() else 0.0
    avg_loss = float(rets[rets < 0].mean()) if (rets < 0).any() else 0.0
    win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else None
    profit_factor = float(rets[rets > 0].sum() / abs(rets[rets < 0].sum())) if rets[rets < 0].sum() != 0 else None

    calmar = cagr / abs(max_dd) if max_dd != 0 else 0.0

    return {
        "n_observations": n,
        "total_return": round(total_return, 6),
        "cagr": round(cagr, 6),
        "ann_vol": round(ann_vol, 6),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino_ratio, 4),
        "max_drawdown": round(max_dd, 6),
        "calmar_ratio": round(calmar, 4),
        "win_rate": round(win_rate, 4),
        "avg_win": round(avg_win, 6),
        "avg_loss": round(avg_loss, 6),
        "win_loss_ratio": round(win_loss_ratio, 4) if win_loss_ratio is not None else None,
        "profit_factor": round(profit_factor, 4) if profit_factor is not None else None,
    }


def _whole_history_metrics(rets: np.ndarray) -> dict[str, Any]:
    """The 6 tail-risk/distribution-shape metrics -- always computed over
    the entire history, never sliced (see 04-enhancement-of-each-angle/
    02-backtesting_44_metrics.md SS3/SS7 for why). Shared by compute() and
    backtest.py's run_whole_history_metrics().
    """
    var_95 = float(np.percentile(rets, 5))
    var_99 = float(np.percentile(rets, 1))
    cvar_95 = float(rets[rets <= var_95].mean()) if (rets <= var_95).any() else var_95
    tail_ratio = float(abs(np.percentile(rets, 95) / np.percentile(rets, 5))) if np.percentile(rets, 5) != 0 else None
    skewness = float(pd.Series(rets).skew())
    kurtosis = float(pd.Series(rets).kurtosis())

    return {
        "n_observations": len(rets),
        "var_95": round(var_95, 6),
        "var_99": round(var_99, 6),
        "cvar_95": round(cvar_95, 6),
        "tail_ratio": round(tail_ratio, 4) if tail_ratio is not None else None,
        "skewness": round(skewness, 4),
        "kurtosis": round(kurtosis, 4),
    }


def compute(
    symbol: str,
    bars: pd.DataFrame | None = None,
    news: list[dict] | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    time_format: str | None = None,
) -> pd.DataFrame:
    if bars is None:
        bars = pd.DataFrame()
    if bars.empty:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": datetime.now(timezone.utc).isoformat(),
            "angle": "backtesting_44_metrics",
            "status": "no_data",
        }])

    close = bars["close"].astype(float)
    returns = close.pct_change().dropna()
    rets = returns.values
    analysis_at = datetime.now(timezone.utc).isoformat()

    if len(rets) < 5:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "backtesting_44_metrics",
            "status": "insufficient_data",
            "n_observations": len(rets),
        }])

    result: dict[str, Any] = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": "backtesting_44_metrics",
    }
    result.update(_core_metrics(rets, time_format))
    result.update(_whole_history_metrics(rets))
    return pd.DataFrame([result])
