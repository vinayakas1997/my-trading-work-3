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

_METHODS = ("fractional_kelly", "fixed_fractional", "atr_stop")


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
    }

    if method == "fractional_kelly":
        full_kelly = full_kelly_fraction(win_rate, payoff_ratio)
        size = fractional_kelly_size(account_equity, win_rate, payoff_ratio, kelly_fraction)
        return {
            "status": "ok", "size": round(size, 2), "method": method,
            "kelly_pct": round(full_kelly * 100.0, 2), "inputs": inputs,
        }
    if method == "fixed_fractional":
        size = fixed_fractional_size(account_equity, risk_pct)
        return {
            "status": "ok", "size": round(size, 2), "method": method, "inputs": inputs,
        }
    # atr_stop
    size = atr_stop_size(account_equity, entry_price, atr, risk_pct, atr_stop_multiple)
    used_method = "atr_stop" if (entry_price > 0.0 and atr > 0.0) else "fixed_fractional"
    return {
        "status": "ok", "size": round(size, 2), "method": used_method, "inputs": inputs,
    }