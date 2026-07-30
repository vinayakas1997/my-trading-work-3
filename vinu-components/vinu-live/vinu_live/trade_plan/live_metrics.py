from __future__ import annotations

import math
from typing import Any

from vinu_tools.compute.risk.volatility import realized_volatility

from vinu_live.book.schema import Position


def _forecast_volatility(risk_bands: dict[str, Any]) -> float:
    upper = risk_bands.get("volatility_band_upper", 0.0) or 0.0
    return upper / 1.5 if upper > 0 else 0.0


def _confidence_decay(
    initial_confidence: float,
    horizon_days: int,
    days_elapsed: int,
) -> float:
    if horizon_days <= 0 or days_elapsed <= 0:
        return initial_confidence
    half_life = max(horizon_days / 3.0, 1.0)
    lam = math.log(2) / half_life
    return initial_confidence * math.exp(-lam * days_elapsed)


def compute_live_metrics(
    position: Position,
    current_price: float,
    plan: dict[str, Any],
    recent_returns: list[float] | None = None,
    previous_close: float | None = None,
    shock_cluster_correlation: float | None = None,
    calibration_accuracy: float | None = None,
    days_elapsed: int = 0,
) -> dict[str, float]:
    pnl_pct = position.pnl_pct(current_price)
    metrics: dict[str, float] = {
        "unrealized_pnl_pct": pnl_pct,
        "drawdown_pct": max(0.0, -pnl_pct),
    }

    if previous_close is not None and previous_close > 0:
        gap = (current_price - previous_close) / previous_close
        adverse_gap = -gap if position.side == "long" else gap
        metrics["gap_against_position_pct"] = max(0.0, adverse_gap)

    if recent_returns:
        forecast_vol = _forecast_volatility(plan.get("risk_bands") or {})
        if forecast_vol > 0:
            import numpy as np

            live_vol_path = realized_volatility(np.array(recent_returns, dtype=float))
            valid = live_vol_path[~np.isnan(live_vol_path)]
            if len(valid) > 0:
                metrics["realized_vol_ratio"] = float(valid[-1]) / forecast_vol

    forecast = plan.get("forecast") or {}
    magnitude_std = forecast.get("magnitude_std", 0.0) or 0.0
    initial_confidence = forecast.get("confidence", 0.0) or 0.0
    horizon_days = forecast.get("horizon_days", 0) or 0

    realized_move_std = 0.0
    if magnitude_std > 0:
        realized_move_std = abs(pnl_pct) / magnitude_std
        metrics["realized_move_vs_forecast_std"] = realized_move_std

    decayed = _confidence_decay(initial_confidence, horizon_days, days_elapsed)

    cal = calibration_accuracy if calibration_accuracy is not None else 0.5

    w_cal, w_price, w_time = 0.4, 0.4, 0.2
    if realized_move_std > 1.0 and magnitude_std > 0:
        w_cal, w_price, w_time = 0.3, 0.6, 0.1

    p_failure = (
        w_cal * (1.0 - cal)
        + w_price * min(realized_move_std, 1.0)
        + w_time * (1.0 - decayed)
    )
    metrics["probability_of_failure"] = max(0.0, min(1.0, p_failure))

    if shock_cluster_correlation is not None:
        metrics["shock_cluster_correlation"] = shock_cluster_correlation

    return metrics
