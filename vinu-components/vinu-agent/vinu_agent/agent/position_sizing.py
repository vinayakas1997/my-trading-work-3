"""Deterministic position-sizing math for risk_gatekeeper (implementation-
plan task 05, shortcoming #7). Previously risk_gatekeeper checked portfolio
*fit* (correlation, exposure vs. account, via get_portfolio /
get_portfolio_concentration) and reported a concentration-limit headroom
as approved_size -- but had NO formula deciding how much of that headroom
an approved candidate's own backtested edge justifies. This module is
that formula: pure, testable math, never an LLM computation (same category
as the sweep engine and Live+Shadow bookkeeping).

Methods (ported from ../personal-important/other-reference-repos/
jarvis-trading-bot/risk_manager.py -- the math, not the surrounding
Telegram/broker app; the fixed-fractional fallback is the "1-2% rule"
from Jarvis/core/risk_manager.py):

- fractional_kelly: classic Kelly fraction f* = (p*b - q)/b (p = win rate,
  q = 1-p, b = payoff ratio = avg win / avg loss), clamped to >= 0, then
  scaled by a conservative fraction of Kelly (default 0.25, i.e. quarter
  Kelly). Zero/negative edge (p <= 0, p >= 1, or b <= 0) yields exactly 0
  -- no positive Kelly size ever comes from a no-edge estimate.
- fixed_fractional: capital * risk_pct (the "1-2% rule").
- atr_stop: fixed-fractional risk budget per unit computed from an ATR-
  based stop (risk_per_unit = atr * atr_stop_multiple, reference default
  2 * ATR), size = units * entry_price. Requires entry_price > 0 and
  atr > 0; otherwise falls back to fixed_fractional (documented, not
  silent).

Every method returns a dict with the same shape so callers (the
compute_position_size tool, the risk_gatekeeper hook) can record exactly
which inputs produced the number -- the traceability discipline every
other gate in this pipeline uses.
"""

from __future__ import annotations

from typing import Any

# Fraction of the full Kelly stake actually deployed. The design doc's own
# "Open questions" leaves Kelly-vs-fixed-fractional undecided; the
# reference analysis (02-reference-repos-core-logic.md) recommends 25-50%.
# Configurable via AgentConfig.kelly_fraction / VINU_AGENT_KELLY_FRACTION,
# injected at tool-build time -- never hardcoded in a caller.
DEFAULT_KELLY_FRACTION = 0.25
# "1-2% rule" fixed-fractional risk per trade.
DEFAULT_RISK_PER_TRADE_PCT = 0.02
# ATR stop multiple for atr_stop sizing (reference default: 2 * ATR).
DEFAULT_ATR_STOP_MULTIPLE = 2.0
DEFAULT_METHOD = "fractional_kelly"
# Tail + vol (13 Now 1+2): CVaR 95% gate + dynamic vol targeting 15% 21d.
# Env only, no code change to flip. Disabled by default until wired in hook.
import os as _os
DEFAULT_CVAR_ENABLED = _os.environ.get("VINU_RISK_CVAR_ENABLED", "false").lower() in ("1", "true", "yes")
DEFAULT_CVAR_THRESHOLD = float(_os.environ.get("VINU_RISK_CVAR_THRESHOLD", "0.03"))
DEFAULT_VOL_TARGET_ENABLED = _os.environ.get("VINU_RISK_VOL_TARGET_ENABLED", "false").lower() in ("1", "true", "yes")
DEFAULT_VOL_TARGET = float(_os.environ.get("VINU_RISK_VOL_TARGET", "0.15"))
# Stage 2 (how-to-make-it-live.md #24): TradePlan.forecast.confidence existed
# on every trade plan but was never read by anything that sizes a position --
# a 0.52 (barely-better-than-coin-flip) forecast and a 0.85 (high-conviction)
# forecast got identical size. Unlike CVaR/vol-target above (which shipped
# disabled and stayed that way until Stage 1 flipped them), this defaults ON
# -- the whole point of this fix is to close a silent "the data exists but
# nothing reads it" gap, not add another one. Floor at 0.5 so a real, if
# modest, forecast can never be scaled to a no-op-sized order; a genuinely
# missing/zero confidence is treated as "no information" (fail-open, no
# scaling) rather than as a rejection -- that is what promotion-time PBO/
# holdout checks are for, not size-time.
DEFAULT_FORECAST_SCALING_ENABLED = _os.environ.get(
    "VINU_RISK_FORECAST_SCALING_ENABLED", "true"
).lower() in ("1", "true", "yes")
DEFAULT_FORECAST_SCALING_FLOOR = float(_os.environ.get("VINU_RISK_FORECAST_SCALING_FLOOR", "0.5"))

_METHODS = ("fractional_kelly", "fixed_fractional", "atr_stop")


def cvar_exceeds(cvar_95: float, threshold: float = DEFAULT_CVAR_THRESHOLD) -> bool:
    """True if tail risk blocks sizing. cvar_95 as positive loss fraction (0.04 = 4% daily)."""
    try:
        return float(cvar_95) > float(threshold)
    except (TypeError, ValueError):
        return False


def vol_target_scale(current_vol: float, target_vol: float = DEFAULT_VOL_TARGET) -> float:
    """position = target / current, capped 0.25x to 1x. High vol halves size auto.
    Non-positive current_vol = 1.0 (no scaling, fail-open)."""
    try:
        cur = float(current_vol)
        tgt = float(target_vol)
    except (TypeError, ValueError):
        return 1.0
    if cur <= 0.0 or tgt <= 0.0:
        return 1.0
    scale = tgt / cur
    return max(0.25, min(1.0, scale))


def forecast_confidence_scale(
    confidence: float | None, floor: float = DEFAULT_FORECAST_SCALING_FLOOR,
) -> float:
    """confidence as a direct fraction of the caller's requested size,
    floored so a real forecast is dampened, never zeroed, by conviction
    alone. None/non-positive confidence = 1.0 (no scaling, fail-open --
    the caller didn't supply a forecast, not evidence the forecast is bad)."""
    try:
        c = float(confidence)
    except (TypeError, ValueError):
        return 1.0
    if c <= 0.0:
        return 1.0
    return max(float(floor), min(1.0, c))


def full_kelly_fraction(win_rate: float, payoff_ratio: float) -> float:
    """Full Kelly fraction f* = (p*b - q) / b, clamped to >= 0.

    Ported from jarvis-trading-bot/risk_manager.py's kelly_criterion
    (same guards: avg_loss == 0 or win_rate <= 0 or win_rate >= 1 -> 0).
    Returns a fraction of capital (0..1), NOT a percentage.
    """
    if win_rate <= 0.0 or win_rate >= 1.0 or payoff_ratio <= 0.0:
        return 0.0
    p = win_rate
    q = 1.0 - p
    b = payoff_ratio
    return max(0.0, (p * b - q) / b)


def fractional_kelly_size(
    account_equity: float,
    win_rate: float,
    payoff_ratio: float,
    kelly_fraction: float = DEFAULT_KELLY_FRACTION,
) -> float:
    """equity * full-Kelly * fraction-of-Kelly. No edge (kelly_fraction
    returns 0) -> 0. Non-positive equity -> 0."""
    if account_equity <= 0.0:
        return 0.0
    full_kelly = full_kelly_fraction(win_rate, payoff_ratio)
    if full_kelly <= 0.0:
        return 0.0
    return account_equity * full_kelly * kelly_fraction


def fixed_fractional_size(
    account_equity: float,
    risk_pct: float = DEFAULT_RISK_PER_TRADE_PCT,
) -> float:
    """capital * risk_pct -- the "1-2% rule" fixed-fractional size."""
    if account_equity <= 0.0 or risk_pct <= 0.0:
        return 0.0
    return account_equity * risk_pct


def atr_stop_size(
    account_equity: float,
    entry_price: float,
    atr: float,
    risk_pct: float = DEFAULT_RISK_PER_TRADE_PCT,
    atr_stop_multiple: float = DEFAULT_ATR_STOP_MULTIPLE,
) -> float:
    """Risk-budget-per-unit sized off an ATR stop (reference:
    stop = entry - 2*ATR, so risk_per_unit = atr * atr_stop_multiple).
    Requires entry_price > 0 and atr > 0; falls back to the plain
    fixed-fractional dollar size when either is missing (documented, not
    silent -- the caller records the method actually used)."""
    if account_equity <= 0.0 or risk_pct <= 0.0:
        return 0.0
    risk_per_unit = atr * atr_stop_multiple
    if entry_price <= 0.0 or atr <= 0.0 or risk_per_unit <= 0.0:
        return fixed_fractional_size(account_equity, risk_pct)
    units = (account_equity * risk_pct) / risk_per_unit
    return units * entry_price


def compute_position_size(
    *,
    account_equity: float,
    method: str = DEFAULT_METHOD,
    win_rate: float = 0.0,
    payoff_ratio: float = 0.0,
    kelly_fraction: float = DEFAULT_KELLY_FRACTION,
    risk_pct: float = DEFAULT_RISK_PER_TRADE_PCT,
    entry_price: float = 0.0,
    atr: float = 0.0,
    atr_stop_multiple: float = DEFAULT_ATR_STOP_MULTIPLE,
    cvar_95: float | None = None,
    cvar_threshold: float = DEFAULT_CVAR_THRESHOLD,
    cvar_enabled: bool = DEFAULT_CVAR_ENABLED,
    current_vol: float | None = None,
    vol_target: float = DEFAULT_VOL_TARGET,
    vol_target_enabled: bool = DEFAULT_VOL_TARGET_ENABLED,
    forecast_confidence: float | None = None,
    forecast_scaling_floor: float = DEFAULT_FORECAST_SCALING_FLOOR,
    forecast_scaling_enabled: bool = DEFAULT_FORECAST_SCALING_ENABLED,
) -> dict[str, Any]:
    """The configurable entry point risk_gatekeeper calls. Returns a dict
    recording both the size AND every input that produced it, so the
    verdict path can store the decision traceably:

        {"status": "ok", "size": 12500.0, "method": "fractional_kelly",
         "kelly_pct": 50.0, "inputs": {...}}

    A non-positive account_equity returns size 0 (fail-safe); an unknown
    method returns {"status": "error", ...} and callers fall back to the
    documented default method."""
    if method not in _METHODS:
        return {"status": "error", "error": f"unknown sizing method {method!r}", "size": 0.0}
    if account_equity <= 0.0:
        return {
            "status": "ok", "size": 0.0, "method": method,
            "reason": "non-positive account equity",
            "inputs": {"account_equity": round(account_equity, 2), "method": method},
        }

    inputs: dict[str, Any] = {
        "account_equity": round(account_equity, 2),
        "method": method,
        "kelly_fraction": kelly_fraction,
        "risk_pct": risk_pct,
        "win_rate": win_rate,
        "payoff_ratio": payoff_ratio,
        "entry_price": entry_price,
        "atr": atr,
        "atr_stop_multiple": atr_stop_multiple,
        "cvar_95": cvar_95,
        "current_vol": current_vol,
        "forecast_confidence": forecast_confidence,
    }

    # Tail gate (13 step1): block when CVaR 95% exceeds threshold. Fail-closed when enabled.
    if cvar_enabled and cvar_95 is not None and cvar_exceeds(cvar_95, cvar_threshold):
        return {
            "status": "ok", "size": 0.0, "method": method,
            "reason": f"CVaR 95% {cvar_95} exceeds {cvar_threshold}, blocked",
            "inputs": inputs,
        }

    def _apply_vol(size: float) -> float:
        adjusted = size
        if vol_target_enabled and current_vol is not None:
            adjusted *= vol_target_scale(current_vol, vol_target)
        if forecast_scaling_enabled and forecast_confidence is not None:
            adjusted *= forecast_confidence_scale(forecast_confidence, forecast_scaling_floor)
        return round(adjusted, 2)

    if method == "fractional_kelly":
        full_kelly = full_kelly_fraction(win_rate, payoff_ratio)
        size = fractional_kelly_size(account_equity, win_rate, payoff_ratio, kelly_fraction)
        return {
            "status": "ok", "size": _apply_vol(size), "method": method,
            "kelly_pct": round(full_kelly * 100.0, 2), "inputs": inputs,
        }
    if method == "fixed_fractional":
        size = fixed_fractional_size(account_equity, risk_pct)
        return {
            "status": "ok", "size": _apply_vol(size), "method": method, "inputs": inputs,
        }
    # atr_stop
    size = atr_stop_size(account_equity, entry_price, atr, risk_pct, atr_stop_multiple)
    used_method = "atr_stop" if (entry_price > 0.0 and atr > 0.0) else "fixed_fractional"
    return {
        "status": "ok", "size": _apply_vol(size), "method": used_method, "inputs": inputs,
    }