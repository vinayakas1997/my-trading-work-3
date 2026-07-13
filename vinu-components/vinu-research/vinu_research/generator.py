from __future__ import annotations

from typing import Any

STRATEGY_TEMPLATE = """from __future__ import annotations

import pandas as pd
import numpy as np

from vinu_simulator.engine.strategies import BaseStrategy


class UserStrategy(BaseStrategy):
    def __init__(self{params_sig}):
{params_init}

    def generate_weights(self, data: pd.DataFrame) -> pd.Series:
{body}
"""

CROSSOVER_TEMPLATE = """fast_ma = data['close'].rolling(int({fast_period})).mean()
slow_ma = data['close'].rolling(int({slow_period})).mean()
signal = (fast_ma > slow_ma).astype(int).diff()
return signal * {allocation}"""

RSI_TEMPLATE = """rsi = data['rsi_{rsi_period}']
signal = pd.Series(0.0, index=data.index)
signal[rsi < {oversold}] = 1.0
signal[rsi > {overbought}] = -1.0
return signal * {allocation}"""

MOMENTUM_TEMPLATE = """momentum = data['close'] / data['close'].shift(int({lookback})) - 1
signal = momentum.clip(-1, 1)
return signal * {allocation}"""

ALLOWED_PARAM_KEYS = frozenset({
    "fast_period", "slow_period", "rsi_period",
    "oversold", "overbought", "lookback", "allocation",
})

ALLOWED_PARAM_TYPES = (int, float, str)

DEFAULT_PARAMS: dict[str, Any] = {
    "fast_period": 20,
    "slow_period": 50,
    "rsi_period": 14,
    "oversold": 30,
    "overbought": 70,
    "lookback": 20,
    "allocation": 0.98,
}

BUILTIN_RECIPES: dict[str, str] = {
    "crossover": CROSSOVER_TEMPLATE,
    "rsi": RSI_TEMPLATE,
    "momentum": MOMENTUM_TEMPLATE,
}


def _sanitize_params(params: dict[str, Any] | None) -> dict[str, Any]:
    if not params:
        return {}
    sanitized: dict[str, Any] = {}
    for key, val in params.items():
        if key not in ALLOWED_PARAM_KEYS:
            continue
        if not isinstance(val, ALLOWED_PARAM_TYPES):
            sanitized[key] = str(val)
        else:
            sanitized[key] = val
    return sanitized


def list_recipes() -> list[str]:
    return list(BUILTIN_RECIPES.keys())


def generate_strategy(
    recipe: str | None = None,
    user_description: str | None = None,
    params: dict[str, Any] | None = None,
) -> str:
    merged = dict(DEFAULT_PARAMS)
    merged.update(_sanitize_params(params))

    if recipe and recipe in BUILTIN_RECIPES:
        template = BUILTIN_RECIPES[recipe]
        body = _safe_format(template, merged)
    elif user_description:
        body = _generate_from_description(user_description, merged)
    else:
        body = _safe_format(CROSSOVER_TEMPLATE, merged)

    template_body = BUILTIN_RECIPES.get(recipe or "", "")
    param_names = _extract_params(template_body)
    param_names = [p for p in param_names if p != "allocation"]
    if param_names:
        params_sig = ", " + ", ".join(f"{p}=None" for p in param_names)
        params_init = "\n".join(
            f"        self.{p} = {p} or {merged.get(p, 20)}"
            for p in param_names
        )
    else:
        params_sig = ""
        params_init = "        pass"

    lines = body.strip().split("\n")
    body_indented = "\n".join("        " + line for line in lines)

    return _safe_format(
        STRATEGY_TEMPLATE,
        {
            "params_sig": params_sig,
            "params_init": params_init,
            "body": body_indented,
        },
    )


def _safe_format(template: str, values: dict[str, Any]) -> str:
    expected = _extract_params(template)
    safe_values = {k: values.get(k, "") for k in expected}
    return template.format(**safe_values)


def _extract_params(body: str) -> list[str]:
    import re
    return re.findall(r"\{(\w+)\}", body)


def _generate_from_description(
    description: str,
    params: dict[str, Any],
) -> str:
    desc_lower = description.lower()
    if "crossover" in desc_lower or "sma" in desc_lower or "ma" in desc_lower:
        return _safe_format(CROSSOVER_TEMPLATE, params)
    if "rsi" in desc_lower or "mean reversion" in desc_lower:
        return _safe_format(RSI_TEMPLATE, params)
    if "momentum" in desc_lower or "trend" in desc_lower:
        return _safe_format(MOMENTUM_TEMPLATE, params)
    return _safe_format(CROSSOVER_TEMPLATE, params)
