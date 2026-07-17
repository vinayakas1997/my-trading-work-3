"""Validation & Overfitting — MC permutation test, bootstrap CI, walk-forward, overfitting verdict"""

import pandas as pd
import numpy as np
from scipy import stats as scipy_stats
from datetime import datetime, timezone


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
            "time_format": time_format,
            "angle": "validation_overfitting",
            "status": "no_data",
        }])

    close = bars["close"].astype(float)
    rets = close.pct_change().dropna().values
    analysis_at = datetime.now(timezone.utc).isoformat()

    if len(rets) < 20:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "validation_overfitting",
            "status": "insufficient_data",
            "n_observations": len(rets),
        }])

    n = len(rets)
    obs_sr = float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0.0

    rows.append({
        "symbol": symbol,
        "analysis_at": analysis_at,
        "time_format": time_format,
        "angle": "validation_overfitting",
        "test": "observed_sharpe",
        "value": round(obs_sr, 4),
        "n_observations": n,
    })

    np.random.seed(42)
    n_perm = 1000
    perm_srs = []
    for _ in range(n_perm):
        p = np.random.permutation(rets)
        sr = p.mean() / p.std() * np.sqrt(252) if p.std() > 0 else 0.0
        perm_srs.append(sr)
    p_value = float((sum(1 for s in perm_srs if s >= obs_sr) + 1) / (n_perm + 1))
    perm_mean = float(np.mean(perm_srs))
    perm_std = float(np.std(perm_srs))

    rows.append({
        "symbol": symbol,
        "analysis_at": analysis_at,
        "time_format": time_format,
        "angle": "validation_overfitting",
        "test": "mc_permutation",
        "n_permutations": n_perm,
        "obs_sharpe": round(obs_sr, 4),
        "perm_mean_sharpe": round(perm_mean, 4),
        "perm_std_sharpe": round(perm_std, 4),
        "p_value": round(p_value, 4),
    })

    n_bs = 1000
    bs_srs = []
    for _ in range(n_bs):
        b = np.random.choice(rets, n)
        sr = b.mean() / b.std() * np.sqrt(252) if b.std() > 0 else 0.0
        bs_srs.append(sr)
    ci_low = float(np.percentile(bs_srs, 2.5))
    ci_high = float(np.percentile(bs_srs, 97.5))
    bs_mean = float(np.mean(bs_srs))

    rows.append({
        "symbol": symbol,
        "analysis_at": analysis_at,
        "time_format": time_format,
        "angle": "validation_overfitting",
        "test": "bootstrap_ci",
        "n_bootstrap": n_bs,
        "mean_sharpe": round(bs_mean, 4),
        "ci_lower_95": round(ci_low, 4),
        "ci_upper_95": round(ci_high, 4),
    })

    n_windows = 4
    window_size = n // n_windows
    wf_srs = []
    for i in range(n_windows):
        start = i * window_size
        end = min((i + 1) * window_size, n)
        w = rets[start:end]
        sr = float(w.mean() / w.std() * np.sqrt(252)) if w.std() > 0 else 0.0
        wf_srs.append(sr)
        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "validation_overfitting",
            "test": "walk_forward",
            "window": i + 1,
            "sharpe": round(sr, 4),
            "n_observations": len(w),
        })

    gap = max(wf_srs) - min(wf_srs)
    if gap <= 0.3:
        verdict = "LOW"
    elif gap <= 0.5:
        verdict = "MODERATE"
    else:
        verdict = "HIGH"

    rows.append({
        "symbol": symbol,
        "analysis_at": analysis_at,
        "time_format": time_format,
        "angle": "validation_overfitting",
        "test": "overfitting_verdict",
        "sharpe_gap": round(gap, 4),
        "verdict": f"{verdict}_risk",
        "mean_wf_sharpe": round(float(np.mean(wf_srs)), 4),
        "std_wf_sharpe": round(float(np.std(wf_srs)), 4),
    })

    for n_trials in [1, 5, 10, 30, 50, 100]:
        if n_trials <= 1:
            e_max = 0
        else:
            euler = 0.5772156649
            e_max = (1 - euler) * scipy_stats.norm.ppf(1 - 1 / n_trials) + euler * scipy_stats.norm.ppf(1 - 1 / n_trials * np.exp(-1))
        dsr = float(scipy_stats.norm.cdf((obs_sr - e_max) * np.sqrt(n - 1)))
        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "validation_overfitting",
            "test": "deflated_sharpe",
            "n_trials": n_trials,
            "e_max": round(e_max, 4),
            "dsr": round(dsr, 4),
        })

    return pd.DataFrame(rows)
