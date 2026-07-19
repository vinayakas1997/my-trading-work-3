"""Deflated Sharpe Ratio — Bailey & López de Prado DSR with skew/kurt adjustment, variable trials"""

import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime, timezone

from vinu_initial_analysis.angles._helpers import ann_factor


def deflated_sharpe(obs_sharpe: float, n_trials: int, n_obs: int, skew: float = 0, kurt: float = 0):
    if n_trials <= 1:
        e_max = 0.0
    else:
        euler = 0.5772156649
        term1 = (1 - euler) * stats.norm.ppf(1 - 1 / n_trials)
        term2 = euler * stats.norm.ppf(1 - 1 / n_trials * np.exp(-1))
        e_max = term1 + term2

    var_sr = (1 + 0.5 * obs_sharpe**2) / (n_obs - 1)
    if skew != 0 or kurt != 0:
        var_sr = (1 + 0.5 * obs_sharpe**2 - skew * obs_sharpe + (kurt - 3) / 4 * obs_sharpe**2) / (n_obs - 1)

    dsr = float(stats.norm.cdf(obs_sharpe / np.sqrt(max(var_sr, 1e-10)) - e_max))
    return dsr, e_max


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
            "angle": "deflated_sharpe_ratio",
            "status": "no_data",
        }])

    close = bars["close"].astype(float)
    rets_np = close.pct_change().dropna().values
    analysis_at = datetime.now(timezone.utc).isoformat()

    if len(rets_np) < 5:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "deflated_sharpe_ratio",
            "status": "insufficient_data",
            "n_observations": len(rets_np),
        }])

    obs_sr = float(rets_np.mean() / rets_np.std() * ann_factor(time_format)) if rets_np.std() > 0 else 0.0
    n_obs = len(rets_np)
    skewness = float(pd.Series(rets_np).skew())
    kurtosis = float(pd.Series(rets_np).kurtosis())

    rows.append({
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": "deflated_sharpe_ratio",
        "metric": "observed_sharpe",
        "sharpe_ratio": round(obs_sr, 4),
        "n_observations": n_obs,
        "skewness": round(skewness, 4),
        "kurtosis": round(kurtosis, 4),
    })

    for n_trials in [1, 5, 10, 30, 50, 100, 200]:
        dsr, e_max = deflated_sharpe(obs_sr, n_trials, n_obs)
        if dsr > 0.95:
            verdict = "genuine_skill"
        elif dsr > 0.50:
            verdict = "uncertain"
        else:
            verdict = "likely_luck"
        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "deflated_sharpe_ratio",
            "metric": "basic_dsr",
            "n_trials": n_trials,
            "e_max_sharpe": round(e_max, 4),
            "dsr": round(dsr, 4),
            "verdict": verdict,
        })

    n_trials = 30
    for sr_input in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
        dsr, e_max = deflated_sharpe(sr_input, n_trials, n_obs)
        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "deflated_sharpe_ratio",
            "metric": "dsr_varying_sharpe",
            "hypothetical_sr": sr_input,
            "n_trials": n_trials,
            "e_max_sharpe": round(e_max, 4),
            "dsr": round(dsr, 4),
        })

    configs = [
        ("normal", 0, 0),
        ("positive_skew", 0.5, 0),
        ("negative_skew", -0.5, 0),
        ("fat_tails", 0, 3),
        ("skewed_fat", 0.5, 3),
    ]
    for name, sk, ku in configs:
        dsr, e_max = deflated_sharpe(obs_sr, n_trials, n_obs, skew=sk, kurt=ku)
        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "deflated_sharpe_ratio",
            "metric": "dsr_skew_kurt_adjusted",
            "config": name,
            "skew": sk,
            "kurt": ku,
            "n_trials": n_trials,
            "e_max_sharpe": round(e_max, 4),
            "dsr": round(dsr, 4),
        })

    for n in [50, 100, 250, 500, 1000]:
        dsr, e_max = deflated_sharpe(obs_sr, n_trials, n)
        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "deflated_sharpe_ratio",
            "metric": "dsr_varying_n",
            "hypothetical_n": n,
            "n_trials": n_trials,
            "e_max_sharpe": round(e_max, 4),
            "dsr": round(dsr, 4),
        })

    dsr_actual, _ = deflated_sharpe(obs_sr, n_trials, n_obs, skew=skewness, kurt=kurtosis)
    rows.append({
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": "deflated_sharpe_ratio",
        "metric": "dsr_actual_adjusted",
        "n_trials": n_trials,
        "dsr": round(dsr_actual, 4),
        "skew_used": round(skewness, 4),
        "kurt_used": round(kurtosis, 4),
    })

    return pd.DataFrame(rows)
