from __future__ import annotations

import asyncio
import ast
import builtins
import logging
from typing import Any

import numpy as np
import pandas as pd

from vinu_research.models import LlmCandidate

LOG = logging.getLogger(__name__)

LLM_GEN_SYSTEM_PROMPT = """You are a senior quantitative analyst who writes trading strategy code.
The code must start with these exact imports, then define a class
`UserStrategy(BaseStrategy)` with:
- `__init__(self, ...)` accepting any strategy parameters
- `generate_weights(self, data: pd.DataFrame) -> pd.Series`

Required imports at the top of every response (the execution environment does
not pre-inject these — omitting them will fail to compile):
```
from __future__ import annotations
import pandas as pd
import numpy as np
from vinu_simulator.engine.strategies import BaseStrategy
```

The `data` DataFrame contains columns: open, high, low, close, volume
plus any technical indicators requested via `features_required`.

Rules:
- Use pandas rolling/ewm operations, not loops
- Return a pd.Series of target weights (between -1.0 and 1.0)
- Handle NaN values (use .fillna(0) or similar)
- Do not use __import__, eval, exec, os, subprocess, open
- The strategy should be parameterizable via __init__

Return JSON with this exact schema:
{
  "strategy_code": "class UserStrategy(BaseStrategy): ...",
  "features_required": ["sma_20", "rsi_14"],
  "reasoning": "Brief explanation of the strategy logic",
  "params": {"param_name": default_value}
}"""


# complexity_penalty logic lives here so LlmCandidate is just a data bag
def _complexity_penalty(code: str) -> float:
    lines = [l for l in code.split("\n") if l.strip() and not l.strip().startswith("#") and not l.strip().startswith("from ") and not l.strip().startswith("import ")]
    n = len(lines)
    if n <= 15:
        return 0.0
    return min((n - 15) * 0.02, 0.3)


def validate_code(code: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False

    unsafe = ["__import__", "eval(", "exec(", "os.", "subprocess", "open("]
    if any(pattern in code for pattern in unsafe):
        return False

    has_class = any(
        isinstance(node, ast.ClassDef) and node.name == "UserStrategy"
        for node in ast.walk(tree)
    )
    has_method = any(
        isinstance(node, ast.FunctionDef) and node.name == "generate_weights"
        for node in ast.walk(tree)
    )
    return has_class and has_method


class _BaseStrategy:
    """Mock BaseStrategy for sandbox validation."""
    pass


_ALLOWED_IMPORTS = {"pd": "pandas", "np": "numpy"}


def _sandbox_import(name: str, *args: Any, **kwargs: Any) -> object:
    if name in ("pandas",): return __import__("pandas", *args, **kwargs)
    if name in ("numpy",): return __import__("numpy", *args, **kwargs)
    if name in ("__future__",): return __import__("__future__", *args, **kwargs)
    raise ImportError(f"Module '{name}' is not allowed in sandbox")


_SAFE_BUILTINS = {
    k: v for k, v in vars(builtins).items()
    if k not in ("eval", "exec", "__import__", "compile", "open", "memoryview", "breakpoint")
}


def validate_sandbox(code: str, sample_data: pd.DataFrame) -> bool:
    restricted = {
        "__builtins__": {**_SAFE_BUILTINS, "__import__": _sandbox_import},
        "pd": pd,
        "np": np,
        "BaseStrategy": _BaseStrategy,
    }
    sanitised = "\n".join(
        line for line in code.split("\n")
        if not (line.strip().startswith("from vinu_simulator") or line.strip().startswith("import vinu_simulator"))
    )
    try:
        exec(sanitised, restricted)
        strategy_class = restricted.get("UserStrategy")
        if strategy_class is None:
            return False
        strategy = strategy_class()
        result = strategy.generate_weights(sample_data)
        if not isinstance(result, pd.Series):
            return False
        if result.isna().all():
            return False
        return True
    except Exception as e:
        LOG.debug("Sandbox validation failed: %s", e)
        return False


def _build_generation_prompt(
    user_idea: str,
    symbol: str,
    from_date: str,
    to_date: str,
    indicators: list[str] | None = None,
) -> str:
    ind_list = ", ".join(indicators) if indicators else "sma_20, sma_50, rsi_14"
    return f"""Generate a trading strategy for:

User request: {user_idea}
Symbol: {symbol}
Period: {from_date} → {to_date}
Available indicators: {ind_list}

The strategy must be a class UserStrategy(BaseStrategy) with generate_weights(self, data) method.
Make it robust, parameterizable, and suitable for the described market conditions."""


class LlmStrategyGenerator:
    def __init__(self, llm_client: Any):
        self._llm = llm_client

    async def generate(
        self,
        user_idea: str,
        symbol: str,
        from_date: str,
        to_date: str,
        indicators: list[str] | None = None,
        n_candidates: int = 3,
    ) -> list[LlmCandidate]:
        # Candidates are independent draws against the same prompt — nothing about
        # candidate i depends on candidate i-1's response, so generating them
        # sequentially just serializes n_candidates LLM round-trips (5-10s each)
        # into one long wait. Run them concurrently instead; the rate limiter and
        # circuit breaker inside the LLM client are already safe under concurrent
        # callers (TokenBucket uses a lock, CircuitBreaker uses an asyncio.Lock).
        results = await asyncio.gather(
            *[
                self._generate_one(user_idea, symbol, from_date, to_date, indicators)
                for _ in range(n_candidates)
            ],
            return_exceptions=True,
        )

        candidates: list[LlmCandidate] = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                LOG.warning("LLM candidate %d generation failed: %s", i + 1, r)
            elif r is not None:
                candidates.append(r)
        return candidates

    async def _generate_one(
        self,
        user_idea: str,
        symbol: str,
        from_date: str,
        to_date: str,
        indicators: list[str] | None = None,
    ) -> LlmCandidate | None:
        prompt = _build_generation_prompt(user_idea, symbol, from_date, to_date, indicators)
        response = await self._llm.chat_json(LLM_GEN_SYSTEM_PROMPT, prompt)
        if response is None:
            return None

        code = response.get("strategy_code", "")
        if not code or not validate_code(code):
            LOG.warning("LLM generated code failed AST validation")
            return None

        return LlmCandidate(
            code=code,
            features_required=response.get("features_required", []),
            reasoning=response.get("reasoning", ""),
            params=response.get("params", {}),
            validated=True,
        )
