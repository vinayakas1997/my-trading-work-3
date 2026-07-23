from __future__ import annotations

import asyncio
import ast
import builtins
import logging
import re
from typing import Any

import numpy as np
import pandas as pd

from vinu_research.angle_context import format_angle_context_lines
from vinu_research.models import BacktestResult, CriticFeedback, LlmCandidate

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


def _format_feature_lines(features: dict[str, Any] | None) -> list[str]:
    """Render feature snapshot as compact prompt lines."""
    lines: list[str] = []
    if not features:
        return lines
    data = features.get("data") or features.get("features") or features
    if isinstance(data, dict):
        lines.append("")
        lines.append("Computed Features (vinu-tools):")
        keys = list(data.keys())[:15]
        for k in keys:
            v = data[k]
            if isinstance(v, (int, float)):
                lines.append(f"  {k}: {v:.4f}")
            else:
                lines.append(f"  {k}: {v}")
        if len(data) > 15:
            lines.append(f"  ... and {len(data) - 15} more features")
    return lines


def _match_score(query: str, candidate: str) -> float:
    q_tokens = set(query.lower().split())
    c_tokens = set(candidate.lower().split())
    if not q_tokens or not c_tokens:
        return 0.0
    overlap = q_tokens & c_tokens
    return len(overlap) / min(len(q_tokens), len(c_tokens))


def _build_memory_context(
    symbol: str,
    past_runs: list[dict[str, Any]] | None,
    user_idea: str = "",
    max_runs: int = 5,
) -> str:
    if not past_runs:
        return ""

    pool = list(past_runs)
    if user_idea:
        for run in pool:
            score = _match_score(user_idea, run.get("user_idea", ""))
            run["_relevance_score"] = score
        pool.sort(key=lambda r: (r.get("_relevance_score", 0), r.get("run_id", 0)), reverse=True)
    else:
        pool = pool[:max_runs]

    selected = pool[:max_runs]
    lines = [f"Past research on {symbol} (top {len(selected)} by relevance):"]
    for run in selected:
        status_mark = " (ACTIVE)" if run.get("status") in ("done", "approved") and run.get("best_sharpe", 0) > 0.5 else ""
        score_str = f" [score={run.get('_relevance_score', 0):.2f}]" if "_relevance_score" in run else ""
        lines.append(
            f"  Run #{run['run_id']}{score_str} ({str(run.get('created_at', ''))[:10]}): "
            f"{str(run.get('user_idea', ''))[:60]} → "
            f"Sharpe {run.get('best_sharpe', 0):.2f}, "
            f"{run.get('total_iterations', 0)} iters, "
            f"status={run.get('status', 'unknown')}{status_mark}"
        )
    return "\n".join(lines)


def _build_generation_prompt(
    user_idea: str,
    symbol: str,
    from_date: str,
    to_date: str,
    indicators: list[str] | None = None,
    angles: dict[str, Any] | None = None,
    features: dict[str, Any] | None = None,
    memory_context: str = "",
    stock_profile: str = "",
) -> str:
    ind_list = ", ".join(indicators) if indicators else "sma_20, sma_50, rsi_14"
    prompt = f"""Generate a trading strategy for:

User request: {user_idea}
Symbol: {symbol}
Period: {from_date} → {to_date}
Available indicators: {ind_list}

The strategy must be a class UserStrategy(BaseStrategy) with generate_weights(self, data) method.
Make it robust, parameterizable, and suitable for the described market conditions."""
    if memory_context:
        prompt += "\n\n" + memory_context
    if stock_profile:
        prompt += "\n\nStock characterization:\n" + stock_profile
    angle_lines = format_angle_context_lines(angles or {})
    if angle_lines:
        prompt += "\n" + "\n".join(angle_lines)
    feature_lines = _format_feature_lines(features)
    if feature_lines:
        prompt += "\n" + "\n".join(feature_lines)
    return prompt


def _summarize_strategy(code: str) -> str:
    parts = []
    init_m = re.search(r'def __init__\(self,\s*([^)]+)\)', code)
    if init_m:
        raw = init_m.group(1)
        params = [p.strip().split(":")[0].split("=")[0].strip() for p in raw.split(",") if p.strip()]
        parts.append(f"Params: {', '.join(params)}")
    indicators = set()
    for ind in ['sma_20', 'sma_50', 'rsi_14', 'rsi', 'sma', 'ema', 'bb', 'atr', 'macd']:
        if ind.lower() in code.lower():
            indicators.add(ind)
    if indicators:
        parts.append(f"Indicators: {', '.join(sorted(indicators))}")
    body_m = re.search(r'def generate_weights\([^)]+\):.*', code, re.DOTALL)
    if body_m:
        body = body_m.group()
        comments = re.findall(r'#\s*(.+)', body)
        if comments:
            logic = '; '.join(c.strip() for c in comments[:5])
            parts.append(f"Logic: {logic}")
    non_comment_lines = [l for l in code.split('\n') if l.strip() and not l.strip().startswith('#') and not l.strip().startswith('from ') and not l.strip().startswith('import ')]
    parts.append(f"Size: {len(non_comment_lines)} logic lines")
    return '\n'.join(parts) if parts else f"Strategy with {len(code.splitlines())} lines"


def _build_refinement_prompt(
    user_idea: str,
    symbol: str,
    from_date: str,
    to_date: str,
    previous_code: str,
    last_result: BacktestResult,
    last_critique: CriticFeedback,
    indicators: list[str] | None = None,
    angles: dict[str, Any] | None = None,
    features: dict[str, Any] | None = None,
    memory_context: str = "",
    stock_profile: str = "",
) -> str:
    m = last_result.metrics
    ind_list = ", ".join(indicators) if indicators else "sma_20, sma_50, rsi_14"
    lines = [
        f"Refine a trading strategy for:",
        f"User request: {user_idea}",
        f"Symbol: {symbol}",
        f"Period: {from_date} → {to_date}",
        f"Available indicators: {ind_list}",
        "",
    ]
    if memory_context:
        lines.append(memory_context)
        lines.append("")
    if stock_profile:
        lines.append("Stock characterization:")
        lines.append(stock_profile)
        lines.append("")
    lines.extend([
        "Previous strategy summary:",
        _summarize_strategy(previous_code),
        "",
        "Backtest results for the code above:",
        f"- Sharpe: {m.sharpe_ratio:.2f}",
        f"- MaxDD: {m.max_drawdown:.1%}",
        f"- Win Rate: {m.win_rate:.0%}",
        f"- Total Return: {m.total_return:.1%}",
        f"- Trade Count: {last_result.trade_count}",
        "",
        f"Critic verdict: {last_critique.verdict}",
        f"Critic reasoning: {last_critique.reasoning}",
        "Critic suggestions to address:",
    ])
    if last_critique.suggestions:
        for i, s in enumerate(last_critique.suggestions, 1):
            lines.append(f"  {i}. {s}")
    else:
        lines.append("  (none)")
    lines.append("")
    lines.append(
        "Return an improved version of the strategy that directly addresses the "
        "critic's suggestions above. Keep what already works; change what doesn't."
    )
    angle_lines = format_angle_context_lines(angles or {})
    if angle_lines:
        lines.extend(angle_lines)
    feature_lines = _format_feature_lines(features)
    if feature_lines:
        lines.extend(feature_lines)
    return "\n".join(lines)


class LlmStrategyGenerator:
    def __init__(self, llm_client: Any):
        self._llm = llm_client

    async def propose_idea_from_angles(self, angles: dict[str, Any]) -> str:
        """Propose a trading strategy idea based solely on angle context."""
        angle_lines = format_angle_context_lines(angles)
        prompt_parts = [
            "Based on the following deterministic angle analysis, propose a specific "
            "trading strategy idea for this symbol. Be concise but specific about the "
            "market regime, entry/exit logic, and what indicators to use.",
        ]
        if angle_lines:
            prompt_parts.extend(angle_lines)
        prompt_parts.append(
            'Return JSON with this exact schema: {"idea": "one paragraph describing the strategy idea"}'
        )
        prompt = "\n".join(prompt_parts)

        sys_prompt = (
            "You are a senior quantitative analyst. Propose a focused, testable trading "
            "strategy idea based on the angle analysis data provided. "
            "Respond with JSON containing a single 'idea' field."
        )

        response = await self._llm.chat_json(sys_prompt, prompt)
        if response and isinstance(response, dict) and "idea" in response:
            return str(response["idea"])
        tl = angles.get("trend_lifecycle", {})
        stage = tl.get("stage", "unknown")
        risk = tl.get("risk", "unknown")
        return f"Trend-following strategy for {stage} stage with {risk} risk regime"

    async def generate(
        self,
        user_idea: str,
        symbol: str,
        from_date: str,
        to_date: str,
        indicators: list[str] | None = None,
        n_candidates: int = 3,
        story: dict[str, Any] | None = None,
    ) -> list[LlmCandidate]:
        # Candidates are independent draws against the same prompt — nothing about
        # candidate i depends on candidate i-1's response, so generating them
        # sequentially just serializes n_candidates LLM round-trips (5-10s each)
        # into one long wait. Run them concurrently instead; the rate limiter and
        # circuit breaker inside the LLM client are already safe under concurrent
        # callers (TokenBucket uses a lock, CircuitBreaker uses an asyncio.Lock).
        angles = (story or {}).get("angles")
        features = (story or {}).get("features")
        memory_context = (story or {}).get("memory_context", "")
        stock_profile = (story or {}).get("stock_profile", "")
        results = await asyncio.gather(
            *[
                self._generate_one(user_idea, symbol, from_date, to_date, indicators, angles, features, memory_context, stock_profile)
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
        angles: dict[str, Any] | None = None,
        features: dict[str, Any] | None = None,
        memory_context: str = "",
        stock_profile: str = "",
    ) -> LlmCandidate | None:
        prompt = _build_generation_prompt(user_idea, symbol, from_date, to_date, indicators, angles, features, memory_context, stock_profile)
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

    async def refine(
        self,
        user_idea: str,
        symbol: str,
        from_date: str,
        to_date: str,
        previous_code: str,
        last_result: BacktestResult,
        last_critique: CriticFeedback,
        indicators: list[str] | None = None,
        n_candidates: int = 1,
        story: dict[str, Any] | None = None,
    ) -> list[LlmCandidate]:
        angles = (story or {}).get("angles")
        features = (story or {}).get("features")
        memory_context = (story or {}).get("memory_context", "")
        stock_profile = (story or {}).get("stock_profile", "")
        candidates: list[LlmCandidate] = []
        for i in range(n_candidates):
            try:
                c = await self._refine_one(
                    user_idea, symbol, from_date, to_date, previous_code,
                    last_result, last_critique, indicators, angles, features,
                    memory_context, stock_profile,
                )
                if c is not None:
                    candidates.append(c)
            except Exception as e:
                LOG.warning("LLM refinement candidate %d generation failed: %s", i + 1, e)
        return candidates

    async def _refine_one(
        self,
        user_idea: str,
        symbol: str,
        from_date: str,
        to_date: str,
        previous_code: str,
        last_result: BacktestResult,
        last_critique: CriticFeedback,
        indicators: list[str] | None = None,
        angles: dict[str, Any] | None = None,
        features: dict[str, Any] | None = None,
        memory_context: str = "",
        stock_profile: str = "",
    ) -> LlmCandidate | None:
        prompt = _build_refinement_prompt(
            user_idea, symbol, from_date, to_date, previous_code,
            last_result, last_critique, indicators, angles, features, memory_context, stock_profile,
        )
        response = await self._llm.chat_json(LLM_GEN_SYSTEM_PROMPT, prompt)
        if response is None:
            return None

        code = response.get("strategy_code", "")
        if not code or not validate_code(code):
            LOG.warning("LLM refined code failed AST validation")
            return None

        return LlmCandidate(
            code=code,
            features_required=response.get("features_required", []),
            reasoning=response.get("reasoning", ""),
            params=response.get("params", {}),
            validated=True,
        )
