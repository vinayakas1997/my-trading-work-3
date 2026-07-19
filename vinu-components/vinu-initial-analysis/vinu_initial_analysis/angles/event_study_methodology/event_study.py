from __future__ import annotations

from typing import Any

import numpy as np
from scipy import stats


def compute_abnormal_return(
    candles: list[dict],
    event_ts: int,
    window_sec: int = 1800,
    estimation_window_sec: int = 604800,
) -> dict[str, Any]:
    pre_candles = [
        c for c in candles
        if event_ts - estimation_window_sec <= c.get("bar_ts", 0) < event_ts
    ]
    event_candles = [
        c for c in candles
        if event_ts <= c.get("bar_ts", 0) <= event_ts + window_sec
    ]

    if len(pre_candles) < 10 or len(event_candles) < 2:
        return {
            "abnormal_return": 0.0,
            "car": 0.0,
            "ar_p_value": 1.0,
            "significant": False,
            "expected_return": 0.0,
        }

    pre_returns = _compute_returns_series(pre_candles)
    event_returns = _compute_returns_series(event_candles)

    expected_return = np.mean(pre_returns) if len(pre_returns) > 0 else 0.0
    abnormal_returns = [r - expected_return for r in event_returns]
    car = sum(abnormal_returns)

    pre_abnormal = [r - expected_return for r in pre_returns]
    estimation_std = float(np.std(pre_abnormal)) if len(pre_abnormal) > 1 else 0.0
    n_event = len(abnormal_returns)

    if n_event > 0 and estimation_std > 0:
        car_std = estimation_std * np.sqrt(n_event)
        t_stat = car / car_std
        p_value = float(2 * stats.t.sf(abs(t_stat), df=len(pre_abnormal) - 1))
    else:
        t_stat, p_value = 0.0, 1.0

    return {
        "abnormal_return": round(abnormal_returns[0], 6) if abnormal_returns else 0.0,
        "car": round(car, 6),
        "ar_p_value": round(float(p_value), 6),
        "significant": bool(p_value < 0.05),
        "expected_return": round(expected_return, 6),
    }


def classify_significance(ar_p_value: float) -> str:
    if ar_p_value < 0.01:
        return "highly_significant"
    elif ar_p_value < 0.05:
        return "significant"
    elif ar_p_value < 0.10:
        return "marginally_significant"
    return "insignificant"


def _compute_returns_series(candles: list[dict]) -> list[float]:
    sorted_c = sorted(candles, key=lambda x: x.get("bar_ts", 0))
    returns = []
    for i in range(1, len(sorted_c)):
        prev_close = sorted_c[i - 1].get("close", 0)
        curr_close = sorted_c[i].get("close", 0)
        if prev_close:
            returns.append((curr_close - prev_close) / prev_close)
    return returns
