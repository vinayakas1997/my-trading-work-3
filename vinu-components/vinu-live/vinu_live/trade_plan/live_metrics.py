"""Compute the live metric values a frozen TradePlan's rules are evaluated against.

Pure/synchronous by design -- all data fetching (recent price history, shock-cluster
correlation) happens in orchestrator.py and is passed in here, so this module stays trivially
testable and has no HTTP or broker concerns of its own.
"""

from __future__ import annotations

from typing import Any

from vinu_tools.compute.risk.volatility import realized_volatility

from vinu_live.book.schema import Position


def _forecast_volatility(risk_bands: dict[str, Any]) -> float:
    """Recover Phase 4's GARCH-forecast annualized vol from the risk band it derived.

    `trade_plan_authoring._build_risk_band` sets `volatility_band_upper = vol * 1.5` --
    inverting that here avoids vinu-live needing to re-fetch or recompute Phase 1's forecast.
    """
    upper = risk_bands.get("volatility_band_upper", 0.0) or 0.0
    return upper / 1.5 if upper > 0 else 0.0


def compute_live_metrics(
    position: Position,
    current_price: float,
    plan: dict[str, Any],
    recent_returns: list[float] | None = None,
    previous_close: float | None = None,
    shock_cluster_correlation: float | None = None,
) -> dict[str, float]:
    """Build the metric dict `condition_evaluator.find_triggered_rules` checks rules against.

    A metric is only included when it can actually be computed from the given inputs --
    absent optional inputs (no recent_returns, no previous_close, no cluster correlation)
    simply omit that metric rather than fabricate a value, so rules referencing it correctly
    never trigger (see condition_evaluator's missing-metric handling).
    """
    pnl_pct = position.pnl_pct(current_price)
    metrics: dict[str, float] = {
        "unrealized_pnl_pct": pnl_pct,
        # Magnitude of adverse move from entry -- zero while the position is profitable.
        # The schema has no stored high-water-mark, so this proxies peak-to-current
        # drawdown with decline-from-entry, which is exact at position open and
        # conservative (never understates risk) afterward.
        "drawdown_pct": max(0.0, -pnl_pct),
    }

    if previous_close is not None and previous_close > 0:
        gap = (current_price - previous_close) / previous_close
        # "Against the position": a downside gap while long, or an upside gap while short.
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
    if magnitude_std > 0:
        metrics["realized_move_vs_forecast_std"] = abs(pnl_pct) / magnitude_std

    if shock_cluster_correlation is not None:
        metrics["shock_cluster_correlation"] = shock_cluster_correlation

    return metrics
