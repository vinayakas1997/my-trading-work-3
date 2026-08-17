"""Deterministic position-sizing tool for risk_gatekeeper (implementation-
plan task 05, shortcoming #7).

risk_gatekeeper's exposure_reviewer previously reported approved_size as a
concentration-limit headroom cap (get_portfolio / get_portfolio_
concentration) but had no formula turning the candidate's own backtested
edge into a recommended size. This tool is that formula: pure math from
agent/position_sizing.py, read-only, never an LLM arithmetic computation.
The LLM supplies the inputs (win rate / payoff ratio / account equity /
ATR / price it actually has in context) and the tool returns the size
plus the exact inputs that produced it -- so the manager can forward both
verbatim (approved_size AND sizing_inputs) and the risk_gatekeeper hook
can recompute/record them deterministically. Same "compute here, mutate
from the parsed final answer" split every other gate uses (pillar 8).
"""

from __future__ import annotations

import json
from typing import Any

from ..agent.position_sizing import (
    DEFAULT_ATR_STOP_MULTIPLE,
    DEFAULT_KELLY_FRACTION,
    DEFAULT_METHOD,
    DEFAULT_RISK_PER_TRADE_PCT,
    compute_position_size,
)
from ..agent.tools import BaseTool


_default_config: Any = None


def _load_default_config() -> Any:
    """Cached fallback for when build_registry injected no config (e.g. the
    chat-session path) -- the sizing knobs then come from the same env vars
    AgentConfig.load_config() reads, so they stay tunable rather than
    hardcoded."""
    global _default_config
    if _default_config is None:
        from ..config import load_config

        _default_config = load_config()
    return _default_config


class ComputePositionSizeTool(BaseTool):
    name = "compute_position_size"
    description = (
        "Deterministic position-sizing formula for an APPROVED risk_gatekeeper "
        "candidate. Inputs: account_equity (dollars), and the candidate's own "
        "backtested edge -- win_rate (0..1), payoff_ratio (avg win / avg loss), "
        "and optionally entry_price and atr for ATR-based sizing. Returns the "
        "recommended dollar size, the method used, and the exact inputs, so the "
        "decision is traceable. Never invent inputs you don't have -- record what "
        "you actually used."
    )
    parameters = {
        "type": "object",
        "properties": {
            "account_equity": {
                "type": "number",
                "description": "total account equity in dollars, from get_portfolio",
            },
            "method": {
                "type": "string",
                "enum": ["fractional_kelly", "fixed_fractional", "atr_stop"],
                "description": (
                    "fractional_kelly (default, edge-scaled, quarter Kelly), "
                    "fixed_fractional (1-2% rule), or atr_stop (risk budget "
                    "per unit off a 2*ATR stop)"
                ),
            },
            "win_rate": {
                "type": "number",
                "description": "candidate's backtested win rate, 0..1",
            },
            "payoff_ratio": {
                "type": "number",
                "description": "avg win / avg loss from the candidate's backtest",
            },
            "kelly_fraction": {
                "type": "number",
                "description": "fraction of full Kelly to deploy (default 0.25)",
            },
            "risk_pct": {
                "type": "number",
                "description": "fixed-fractional risk per trade, 0..1 (default 0.02)",
            },
            "entry_price": {
                "type": "number",
                "description": "current entry price, needed for atr_stop sizing",
            },
            "atr": {
                "type": "number",
                "description": "average true range, needed for atr_stop sizing",
            },
        },
        "required": ["account_equity"],
    }
    is_readonly = True
    _config: Any = None

    def execute(self, **kwargs: Any) -> str:
        cfg = self._config if self._config is not None else _load_default_config()
        account_equity = float(kwargs.get("account_equity", 0.0) or 0.0)
        method = str(kwargs.get("method") or getattr(cfg, "position_sizing_method", DEFAULT_METHOD))
        kelly_fraction = float(
            kwargs.get("kelly_fraction")
            or getattr(cfg, "kelly_fraction", DEFAULT_KELLY_FRACTION)
        )
        risk_pct = float(
            kwargs.get("risk_pct") or getattr(cfg, "risk_per_trade_pct", DEFAULT_RISK_PER_TRADE_PCT)
        )
        atr_stop_multiple = float(
            kwargs.get("atr_stop_multiple")
            or getattr(cfg, "atr_stop_multiple", DEFAULT_ATR_STOP_MULTIPLE)
        )
        result = compute_position_size(
            account_equity=account_equity,
            method=method,
            win_rate=float(kwargs.get("win_rate", 0.0) or 0.0),
            payoff_ratio=float(kwargs.get("payoff_ratio", 0.0) or 0.0),
            kelly_fraction=kelly_fraction,
            risk_pct=risk_pct,
            entry_price=float(kwargs.get("entry_price", 0.0) or 0.0),
            atr=float(kwargs.get("atr", 0.0) or 0.0),
            atr_stop_multiple=atr_stop_multiple,
        )
        return json.dumps(result, indent=2)