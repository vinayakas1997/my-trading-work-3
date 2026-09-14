"""Post-trade causal loss classification (high-expectations follow-up):
pnl_attribution aggregates win_rate/avg_win/avg_loss but never tagged WHY a
trade lost -- risk-limit exit vs. regime shift vs. wrong thesis vs. bad
execution were all indistinguishable in the data. Deterministic, not
LLM-based: every input here is already on hand at exit time (the triggering
rule, the realized P&L, whether the fill exceeded its slippage budget), so a
mechanical rule suffices -- same "don't over-engineer free-text
classification" posture as condition_evaluator.py's own mechanical rules.
"""

from __future__ import annotations

from typing import Any

_RISK_METRICS = {"drawdown_pct", "realized_vol_ratio"}
_REGIME_METRICS = {"shock_cluster_correlation"}


def classify_exit_cause(
    rule: dict[str, Any], realized_pnl: float, *, slippage_exceeded: bool = False,
) -> str:
    """The primary cause tag for a closed trade. A winning trade
    (`realized_pnl > 0`) is always "expected_outcome" -- wins don't need a
    cause, and a rule that happened to be the exit trigger (e.g. a
    contingency tighten-then-exit) doesn't retroactively make a profitable
    trade a "risk_error". `slippage_exceeded` adds "execution_error" as a
    SECOND, independent tag (joined with "+") rather than replacing the
    primary cause -- a trade can be both wrong and badly filled.
    """
    if realized_pnl > 0:
        primary = "expected_outcome"
    else:
        metric = rule.get("metric", "")
        condition = str(rule.get("condition", ""))
        if metric in _RISK_METRICS:
            primary = "risk_error"
        elif metric in _REGIME_METRICS:
            primary = "regime_change_error"
        elif condition.startswith("thesis_recheck"):
            primary = "prediction_error"
        elif "time_stop" in condition:
            primary = "time_decay"
        else:
            primary = "unclassified"

    if slippage_exceeded and primary != "expected_outcome":
        return f"{primary}+execution_error"
    return primary
