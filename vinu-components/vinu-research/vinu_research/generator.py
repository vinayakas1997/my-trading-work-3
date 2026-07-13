from __future__ import annotations

import re
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

TRIPLE_CROSSOVER_TEMPLATE = """fast_ma = data['close'].rolling(int({fast_period})).mean()
mid_ma = data['close'].rolling(int({mid_period})).mean()
slow_ma = data['close'].rolling(int({slow_period})).mean()
signal = pd.Series(0.0, index=data.index)
signal[(fast_ma > mid_ma) & (mid_ma > slow_ma)] = 1.0
signal[(fast_ma < mid_ma) & (mid_ma < slow_ma)] = -1.0
return signal * {allocation}"""

RSI_TEMPLATE = """rsi = data['rsi_{rsi_period}']
signal = pd.Series(0.0, index=data.index)
signal[rsi < {oversold}] = 1.0
signal[rsi > {overbought}] = -1.0
return signal * {allocation}"""

MOMENTUM_TEMPLATE = """momentum = data['close'] / data['close'].shift(int({lookback})) - 1
signal = momentum.clip(-1, 1)
return signal * {allocation}"""

BOLLINGER_TEMPLATE = """close = data['close']
ma = close.rolling(int({bb_period})).mean()
std = close.rolling(int({bb_period})).std()
upper = ma + {bb_std} * std
lower = ma - {bb_std} * std
signal = pd.Series(0.0, index=data.index)
signal[close < lower] = 1.0
signal[close > upper] = -1.0
return signal * {allocation}"""

ZSCORE_TEMPLATE = """close = data['close']
ma = close.rolling(int({zscore_period})).mean()
std = close.rolling(int({zscore_period})).std()
z = (close - ma) / std.replace(0, float('inf'))
signal = pd.Series(0.0, index=data.index)
signal[z < -{zscore_entry}] = 1.0
signal[z > {zscore_entry}] = -1.0
return signal * {allocation}"""

BREAKOUT_TEMPLATE = """high_high = data['high'].rolling(int({lookback})).max()
low_low = data['low'].rolling(int({lookback})).min()
signal = pd.Series(0.0, index=data.index)
signal[data['close'] > high_high.shift()] = 1.0
signal[data['close'] < low_low.shift()] = -1.0
return signal * {allocation}"""

ROC_TEMPLATE = """roc = data['close'] / data['close'].shift(int({roc_period})) - 1
roc_signal = (roc > {roc_threshold}).astype(int) - (roc < -{roc_threshold}).astype(int)
signal = roc_signal * (roc.abs() / roc.abs().rolling(100).max().replace(0, 1)).fillna(0)
return signal * {allocation}"""

VOL_BREAKOUT_TEMPLATE = """close = data['close']
high = data['high']
low = data['low']
atr = pd.concat([high - low, high - close.shift(), close.shift() - low], axis=1).max(axis=1)
atr = atr.rolling(int({atr_period})).mean()
signal = pd.Series(0.0, index=data.index)
signal[close > close.shift() + atr * {vol_entry}] = 1.0
signal[close < close.shift() - atr * {vol_entry}] = -1.0
return signal * {allocation}"""

SUPERTREND_TEMPLATE = """close = data['close']
high = data['high']
low = data['low']
atr = pd.concat([high - low, high - close.shift(), close.shift() - low], axis=1).max(axis=1)
atr = atr.rolling(int({st_period})).mean()
hl_avg = (high + low) / 2
upper_band = hl_avg + {st_multiplier} * atr
lower_band = hl_avg - {st_multiplier} * atr
in_uptrend = close > upper_band.shift()
in_uptrend = in_uptrend.where(in_uptrend.notna(), True)
signal = in_uptrend.astype(int).diff().fillna(0)
return signal * {allocation}"""

ADX_CROSSOVER_TEMPLATE = """fast_ma = data['close'].rolling(int({fast_period})).mean()
slow_ma = data['close'].rolling(int({slow_period})).mean()
adx = data.get('adx_{adx_period}', pd.Series(25.0, index=data.index))
raw_signal = (fast_ma > slow_ma).astype(int).diff()
signal = raw_signal.where(adx > {adx_threshold}, 0)
return signal * {allocation}"""

VOLUME_BREAKOUT_TEMPLATE = """high_high = data['high'].rolling(int({lookback})).max()
avg_volume = data['volume'].rolling(int({volume_period})).mean()
close = data['close']
volume_spike = data['volume'] > avg_volume * {volume_multiplier}
signal = pd.Series(0.0, index=data.index)
signal[(close > high_high.shift()) & volume_spike] = 1.0
return signal * {allocation}"""

MOM_MR_TEMPLATE = """atr = data['high'] - data['low']
regime_vol = atr.rolling(int({regime_period})).mean()
trend_vol = atr.rolling(int({trend_period})).mean()
in_trend = regime_vol > trend_vol * {vol_ratio}
fast_ma = data['close'].rolling(int({fast_period})).mean()
slow_ma = data['close'].rolling(int({slow_period})).mean()
close = data['close']
ma = close.rolling(int({mr_period})).mean()
std = close.rolling(int({mr_period})).std()
z = (close - ma) / std.replace(0, float('inf'))
trend_signal = (fast_ma > slow_ma).astype(int).diff()
mr_signal = pd.Series(0.0, index=data.index)
mr_signal[z < -{mr_entry}] = 1.0
mr_signal[z > {mr_entry}] = -1.0
signal = trend_signal.where(in_trend, mr_signal)
return signal * {allocation}"""

MACD_TEMPLATE = """ema_fast = data['close'].ewm(span=int({macd_fast}), adjust=False).mean()
ema_slow = data['close'].ewm(span=int({macd_slow}), adjust=False).mean()
macd_line = ema_fast - ema_slow
signal_line = macd_line.ewm(span=int({macd_signal}), adjust=False).mean()
signal = (macd_line > signal_line).astype(int).diff()
return signal * {allocation}"""

VWAP_CROSSOVER_TEMPLATE = """vwap = (data['volume'] * data['close']).rolling(int({vwap_period})).sum() / data['volume'].rolling(int({vwap_period})).sum().replace(0, float('inf'))
signal = (data['close'] > vwap).astype(int).diff()
return signal * {allocation}"""

TEMPLATE_METADATA: list[dict[str, Any]] = [
    {
        "key": "crossover",
        "name": "MA Crossover",
        "description": "Fast/slow moving average crossover. Long when fast MA crosses above slow MA.",
        "keywords": ["crossover", "sma", "moving average", "ma crossover", "golden cross", "death cross"],
        "regimes": ["trending"],
        "params": {"fast_period": 20, "slow_period": 50},
        "complexity": 1,
    },
    {
        "key": "triple_crossover",
        "name": "Triple MA Crossover",
        "description": "Three moving averages alignment. Long when all three are bullishly aligned.",
        "keywords": ["triple crossover", "3 ma", "triple ma", "three moving average"],
        "regimes": ["trending"],
        "params": {"fast_period": 10, "mid_period": 30, "slow_period": 60},
        "complexity": 2,
    },
    {
        "key": "macd",
        "name": "MACD Crossover",
        "description": "MACD line crosses signal line for trend-following signals.",
        "keywords": ["macd", "moving average convergence divergence"],
        "regimes": ["trending"],
        "params": {"macd_fast": 12, "macd_slow": 26, "macd_signal": 9},
        "complexity": 2,
    },
    {
        "key": "vwap_crossover",
        "name": "VWAP Crossover",
        "description": "Price crossing VWAP (volume-weighted average price). Buy when crossing above.",
        "keywords": ["vwap", "volume weighted", "vwap crossover"],
        "regimes": ["intraday", "trending"],
        "params": {"vwap_period": 20},
        "complexity": 1,
    },
    {
        "key": "rsi",
        "name": "RSI Mean Reversion",
        "description": "RSI-based mean reversion. Buy when oversold, sell when overbought.",
        "keywords": ["rsi", "mean reversion", "oversold", "overbought", "relative strength"],
        "regimes": ["ranging", "mean_reverting"],
        "params": {"rsi_period": 14, "oversold": 30, "overbought": 70},
        "complexity": 1,
    },
    {
        "key": "bollinger_bands",
        "name": "Bollinger Bands Mean Reversion",
        "description": "Buy at lower band, sell at upper band. Mean reversion strategy.",
        "keywords": ["bollinger", "bollinger band", "bb"],
        "regimes": ["ranging", "mean_reverting"],
        "params": {"bb_period": 20, "bb_std": 2.0},
        "complexity": 1,
    },
    {
        "key": "mean_reversion_zscore",
        "name": "Z-Score Mean Reversion",
        "description": "Z-score distance from moving average. Buy when far below, sell when far above.",
        "keywords": ["zscore", "z-score", "z score", "mean reversion z"],
        "regimes": ["ranging", "mean_reverting"],
        "params": {"zscore_period": 20, "zscore_entry": 2.0},
        "complexity": 2,
    },
    {
        "key": "momentum",
        "name": "Momentum",
        "description": "Rate-of-change momentum. Goes long/short proportional to recent return.",
        "keywords": ["momentum", "trend", "rate of change", "roc"],
        "regimes": ["trending"],
        "params": {"lookback": 20},
        "complexity": 1,
    },
    {
        "key": "rate_of_change",
        "name": "Rate of Change Momentum",
        "description": "Threshold-based ROC. Enters when ROC exceeds threshold, exits below.",
        "keywords": ["rate of change", "roc", "roc momentum"],
        "regimes": ["trending"],
        "params": {"roc_period": 20, "roc_threshold": 0.05},
        "complexity": 2,
    },
    {
        "key": "breakout",
        "name": "Price Breakout",
        "description": "Buy when price breaks above recent high, sell when breaks below recent low.",
        "keywords": ["breakout", "52 week high", "range breakout", "channel breakout"],
        "regimes": ["volatile", "trending"],
        "params": {"lookback": 20},
        "complexity": 1,
    },
    {
        "key": "volatility_breakout",
        "name": "ATR Volatility Breakout",
        "description": "ATR-based volatility breakout. Enters when price moves more than ATR multiple.",
        "keywords": ["volatility breakout", "atr breakout", "volatility", "breakout atr"],
        "regimes": ["volatile"],
        "params": {"atr_period": 14, "vol_entry": 2.0},
        "complexity": 2,
    },
    {
        "key": "supertrend",
        "name": "Supertrend",
        "description": "ATR-based trend-following indicator. Generates signals on trend direction changes.",
        "keywords": ["supertrend", "atr trend", "super trend"],
        "regimes": ["trending"],
        "params": {"st_period": 10, "st_multiplier": 3.0},
        "complexity": 2,
    },
    {
        "key": "adx_filtered_crossover",
        "name": "ADX-Filtered Crossover",
        "description": "MA crossover filtered by ADX. Only trades when trend strength is above threshold.",
        "keywords": ["adx", "adx crossover", "trend strength", "adx filter"],
        "regimes": ["trending"],
        "params": {"fast_period": 20, "slow_period": 50, "adx_period": 14, "adx_threshold": 25},
        "complexity": 2,
    },
    {
        "key": "volume_confirmed_breakout",
        "name": "Volume-Confirmed Breakout",
        "description": "Breakout confirmed by volume spike. Only trades when volume confirms the move.",
        "keywords": ["volume breakout", "volume confirmed", "breakout volume"],
        "regimes": ["trending", "volatile"],
        "params": {"lookback": 20, "volume_period": 20, "volume_multiplier": 1.5},
        "complexity": 2,
    },
    {
        "key": "momentum_mean_reversion",
        "name": "Momentum / Mean Reversion Hybrid",
        "description": "Uses momentum in trending regimes, mean reversion in ranging regimes detected by volatility ratio.",
        "keywords": ["hybrid", "momentum mean reversion", "regime switching", "adaptive"],
        "regimes": ["adaptive"],
        "params": {"fast_period": 20, "slow_period": 50, "regime_period": 20, "trend_period": 60, "vol_ratio": 0.8, "mr_period": 20, "mr_entry": 2.0},
        "complexity": 3,
    },
]

_TEMPLATE_VAR_MAP = {
    "crossover": CROSSOVER_TEMPLATE,
    "triple_crossover": TRIPLE_CROSSOVER_TEMPLATE,
    "rsi": RSI_TEMPLATE,
    "bollinger_bands": BOLLINGER_TEMPLATE,
    "mean_reversion_zscore": ZSCORE_TEMPLATE,
    "momentum": MOMENTUM_TEMPLATE,
    "rate_of_change": ROC_TEMPLATE,
    "breakout": BREAKOUT_TEMPLATE,
    "volatility_breakout": VOL_BREAKOUT_TEMPLATE,
    "supertrend": SUPERTREND_TEMPLATE,
    "adx_filtered_crossover": ADX_CROSSOVER_TEMPLATE,
    "volume_confirmed_breakout": VOLUME_BREAKOUT_TEMPLATE,
    "momentum_mean_reversion": MOM_MR_TEMPLATE,
    "macd": MACD_TEMPLATE,
    "vwap_crossover": VWAP_CROSSOVER_TEMPLATE,
}

BUILTIN_RECIPES: dict[str, str] = {
    tm["key"]: _TEMPLATE_VAR_MAP[tm["key"]]
    for tm in TEMPLATE_METADATA
}

ALLOWED_PARAM_KEYS: set[str] = set()
for tm in TEMPLATE_METADATA:
    ALLOWED_PARAM_KEYS.update(tm["params"].keys())
ALLOWED_PARAM_KEYS.add("allocation")

ALLOWED_PARAM_TYPES = (int, float, str)

DEFAULT_PARAMS: dict[str, Any] = {
    "allocation": 0.98,
}
for tm in TEMPLATE_METADATA:
    for k, v in tm["params"].items():
        DEFAULT_PARAMS.setdefault(k, v)

KEYWORD_RECIPE_MAP: list[tuple[list[str], str]] = []
for tm in TEMPLATE_METADATA:
    KEYWORD_RECIPE_MAP.append(([kw.lower() for kw in tm["keywords"]], tm["key"]))


def list_recipes() -> list[str]:
    return list(BUILTIN_RECIPES.keys())


def list_recipe_details() -> list[dict[str, Any]]:
    return [
        {
            "key": tm["key"],
            "name": tm["name"],
            "description": tm["description"],
            "regimes": tm["regimes"],
            "complexity": tm["complexity"],
            "params": tm["params"],
        }
        for tm in TEMPLATE_METADATA
    ]


def find_recipe(text: str) -> str | None:
    text_lower = text.lower()
    words = text_lower.split()
    best_match: str | None = None
    best_score = 0

    for keywords, recipe_key in KEYWORD_RECIPE_MAP:
        matched = [kw for kw in keywords if kw in text_lower]
        if not matched:
            continue
        n_keywords = len(keywords)
        n_matched = len(matched)
        matched_length = sum(len(kw) for kw in matched)
        word_hits = sum(1 for word in words for kw in keywords if word == kw or word in kw)
        score = n_matched * 500 - n_keywords * 10 + matched_length + word_hits * 5

        if score > best_score:
            best_score = score
            best_match = recipe_key

    return best_match


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
        body = _safe_format(BUILTIN_RECIPES["crossover"], merged)

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


def _safe_format(template: str, values: dict[str, Any]) -> str:
    expected = _extract_params(template)
    safe_values = {k: values.get(k, "") for k in expected}
    return template.format(**safe_values)


def _extract_params(body: str) -> list[str]:
    return re.findall(r"\{(\w+)\}", body)


def _generate_from_description(
    description: str,
    params: dict[str, Any],
) -> str:
    recipe = find_recipe(description)
    if recipe and recipe in BUILTIN_RECIPES:
        return _safe_format(BUILTIN_RECIPES[recipe], params)
    return _safe_format(BUILTIN_RECIPES["crossover"], params)
