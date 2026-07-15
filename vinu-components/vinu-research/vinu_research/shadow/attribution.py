from __future__ import annotations

import numpy as np


def decompose_pnl(trades: list[dict[str, float]]) -> dict[str, float]:
    noise_pnl = 0.0
    early_exit_pnl = 0.0
    late_exit_pnl = 0.0
    overtrading_pnl = 0.0
    core_pnl = 0.0

    if not trades:
        return {
            "core_pnl": 0.0,
            "noise_trades_pnl": 0.0,
            "early_exit_pnl": 0.0,
            "late_exit_pnl": 0.0,
            "overtrading_pnl": 0.0,
            "total_pnl": 0.0,
        }

    pnls = np.array([t.get("pnl", 0.0) for t in trades])
    holding_days = np.array([t.get("holding_days", 0) for t in trades])
    total_pnl = float(np.sum(pnls))

    small_trades = pnls[np.abs(pnls) < np.percentile(np.abs(pnls), 25)] if len(pnls) > 3 else pnls
    noise_pnl = float(np.sum(small_trades))

    if len(holding_days) > 1:
        mean_hold = float(np.mean(holding_days))
        std_hold = float(np.std(holding_days))
        early = pnls[holding_days < (mean_hold - std_hold)]
        late = pnls[holding_days > (mean_hold + std_hold)]
        early_exit_pnl = float(np.sum(early))
        late_exit_pnl = float(np.sum(late))

    if len(trades) > 20:
        overtrading_pnl = total_pnl * 0.1
    else:
        overtrading_pnl = 0.0

    core_pnl = total_pnl - noise_pnl - early_exit_pnl - late_exit_pnl - overtrading_pnl

    return {
        "core_pnl": core_pnl,
        "noise_trades_pnl": noise_pnl,
        "early_exit_pnl": early_exit_pnl,
        "late_exit_pnl": late_exit_pnl,
        "overtrading_pnl": overtrading_pnl,
        "total_pnl": total_pnl,
    }
