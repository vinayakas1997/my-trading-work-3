"""Factor Backtesting — single-symbol time-series factor backtest"""

import pandas as pd
import numpy as np
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
            "angle": "factor_backtesting",
            "status": "no_data",
        }])

    close = bars["close"].astype(float)
    returns = close.pct_change().dropna()
    analysis_at = datetime.now(timezone.utc).isoformat()

    ret_series = returns.values
    n = len(ret_series)
    if n < 20:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "factor_backtesting",
            "status": "insufficient_data",
            "n_observations": n,
        }])

    cutoff = n // 2
    for label, period_rets in [("full", ret_series), ("first_half", ret_series[:cutoff]), ("second_half", ret_series[cutoff:])]:
        if len(period_rets) < 5:
            continue
        total_ret = float((1 + period_rets).prod() - 1)
        ann_ret = float((1 + total_ret) ** (252 / len(period_rets)) - 1) if len(period_rets) > 0 else 0.0
        ann_vol = float(period_rets.std() * np.sqrt(252))
        sharpe = ann_ret / ann_vol if ann_vol > 0 else 0.0
        win_rate = float((period_rets > 0).mean())
        max_dd = float(np.minimum.accumulate((1 + period_rets).cumprod()).min())

        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "factor_backtesting",
            "period": label,
            "total_return": round(total_ret, 6),
            "ann_return": round(ann_ret, 6),
            "ann_vol": round(ann_vol, 6),
            "sharpe": round(sharpe, 4),
            "win_rate": round(win_rate, 4),
            "max_drawdown": round(max_dd, 6),
            "n_observations": len(period_rets),
        })

    factor_features = {
        "momentum_1d": returns,
        "momentum_5d": returns.rolling(5).mean(),
        "momentum_21d": returns.rolling(21).mean(),
        "vol_20d": returns.rolling(20).std(),
        "volume_ratio": (bars["volume"].astype(float) / bars["volume"].astype(float).rolling(20).mean()),
    }

    fwd_ret = returns.shift(-1).dropna()
    for fname, fseries in factor_features.items():
        f_aligned = fseries.reindex(fwd_ret.index).dropna()
        common = f_aligned.index.intersection(fwd_ret.index)
        if len(common) < 10:
            continue
        fv = f_aligned.loc[common].values
        fr = fwd_ret.loc[common].values
        median_f = np.median(fv)
        long_mask = fv >= median_f
        short_mask = fv < median_f
        long_ret = fr[long_mask].mean() if long_mask.sum() > 0 else 0.0
        short_ret = fr[short_mask].mean() if short_mask.sum() > 0 else 0.0
        spread = long_ret - short_ret
        ic = np.corrcoef(fv, fr)[0, 1] if len(fv) > 2 else 0.0

        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "factor_backtesting",
            "period": f"factor_{fname}",
            "long_return": round(float(long_ret), 6),
            "short_return": round(float(short_ret), 6),
            "spread_return": round(float(spread), 6),
            "ic": round(float(ic), 4),
            "n_observations": len(common),
        })

    return pd.DataFrame(rows)
