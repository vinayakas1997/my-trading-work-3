from __future__ import annotations

import math


def confidence_decay(
    initial_confidence: float,
    horizon_days: int,
    days_elapsed: int,
) -> float:
    if horizon_days <= 0 or days_elapsed <= 0:
        return initial_confidence
    half_life = max(horizon_days / 3.0, 1.0)
    lam = math.log(2) / half_life
    return initial_confidence * math.exp(-lam * days_elapsed)


def probability_of_failure(
    cal_accuracy: float | None = None,
    price_distance_std: float = 0.0,
    magnitude_std: float = 0.0,
    initial_confidence: float = 0.0,
    horizon_days: int = 0,
    days_elapsed: int = 0,
) -> float:
    cal = cal_accuracy if cal_accuracy is not None else 0.5

    w_cal = 0.4
    w_price = 0.4
    w_time = 0.2

    cal_term = 1.0 - cal

    if magnitude_std > 0:
        price_term = min(price_distance_std / magnitude_std, 1.0)
    else:
        price_term = 0.0

    if price_term > 1.0 and magnitude_std > 0:
        w_price = 0.6
        w_cal = 0.3
        w_time = 0.1

    decayed = confidence_decay(initial_confidence, horizon_days, days_elapsed)
    time_term = 1.0 - decayed

    total = w_cal * cal_term + w_price * price_term + w_time * time_term
    return max(0.0, min(1.0, total))


def get_exit_action(
    p_failure: float,
) -> dict:
    if p_failure >= 0.6:
        return {"action": "hard_exit", "reason": f"P_failure={p_failure:.2f} >= 0.6"}
    if p_failure >= 0.4:
        return {"action": "exit", "reason": f"P_failure={p_failure:.2f} >= 0.4"}
    if p_failure >= 0.3:
        return {"action": "trim", "reason": f"P_failure={p_failure:.2f} >= 0.3"}
    return {"action": "monitor", "reason": f"P_failure={p_failure:.2f} < 0.3"}
