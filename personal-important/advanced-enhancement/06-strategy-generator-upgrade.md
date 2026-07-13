# Enhancement 6: Strategy Generator Upgrade — LLM-Powered Code Generation

## Current State Score: 5/10

The `generator.py` file has **3 hardcoded templates** (crossover, RSI, momentum) matched via keyword detection. The LLM is only used in the risk critic stage, not in strategy generation. This severely limits the system's creative potential — it can only produce strategies that the template author explicitly coded.

## Target State: 10/10

A dual-mode generator:
1. **Template Mode** (fast, deterministic): 40+ templates with parameter ranges (Bollinger bands, MACD, pairs trading, statistical arbitrage, volatility breakout, etc.)
2. **LLM Mode** (creative, adaptive): Uses the existing LLM integration to generate novel strategy code from natural language descriptions, with runtime validation and sandboxed execution test

The risk critic compares template-generated vs LLM-generated strategies and selects the best. The system can compose multiple templates together.

## Why This Matters (The Problem)

- **3 templates is absurdly limited**: The system claims to be an "Agentic Strategy Researcher" but only knows 3 strategy families. A real quant has hundreds.
- **Keyword matching misses nuance**: "Buy when RSI < 30 and sell at 70" maps to RSI template. But "Buy when RSI < 30 and sell when price crosses SMA 20" is a hybrid — the system can't handle it.
- **No parameter optimization**: The templates use fixed periods (SMA 20/50, RSI 14). A real researcher optimizes parameters for each period/symbol.
- **No strategy composition**: Real strategies combine multiple signals. The system can only generate single-signal strategies.
- **LLM is underutilized**: There's already an LLM client with caching, rate limiting, and circuit breaker. Using it only for the risk critic is wasting 50% of its potential.

## What to Build

### 1. Expanded Template Library — Modify `generator.py`

Add these template families:

```python
TEMPLATE_LIBRARY = {
    # === MOVING AVERAGE VARIANTS ===
    "crossover": CROSSOVER_TEMPLATE,
    "triple_crossover": TCROSSOVER_TEMPLATE,    # 3 MA triple crossover
    "moving_average_convergence": MAC_TEMPLATE, # MA convergence/divergence
    "vwap_crossover": VWAP_CROSSOVER_TEMPLATE,  # Price vs VWAP crossover

    # === MEAN REVERSION ===
    "rsi": RSI_TEMPLATE,
    "bollinger_bands": BOLLINGER_TEMPLATE,       # Buy at lower band, sell at upper
    "mean_reversion_zscore": ZSCORE_TEMPLATE,    # Z-score based mean reversion
    "pairs_trading": PAIRS_TEMPLATE,              # Spread between two correlated assets
    "ornstein_uhlenbeck": OU_TEMPLATE,            # OU process mean reversion

    # === MOMENTUM ===
    "momentum": MOMENTUM_TEMPLATE,
    "breakout": BREAKOUT_TEMPLATE,                # 52-week high breakout
    "relative_strength": RS_TEMPLATE,             # Relative strength to universe
    "volume_confirmed_breakout": VOL_BREAKOUT,    # Breakout + volume confirmation
    "rate_of_change": ROC_TEMPLATE,               # Rate of change momentum

    # === VOLATILITY ===
    "volatility_breakout": VOL_BREAKOUT_TEMPLATE, # ATR-based breakout
    "iv_rank": IV_RANK_TEMPLATE,                  # Implied volatility rank (needs options data)
    "volatility_mean_reversion": VOL_MR_TEMPLATE, # VIX/VXN mean reversion

    # === PATTERN ===
    "supertrend": SUPERTREND_TEMPLATE,            # Supertrend indicator
    "parabolic_sar": PSAR_TEMPLATE,               # Parabolic SAR
    "ichimoku": ICHIMOKU_TEMPLATE,                # Ichimoku Cloud

    # === COMPOSITE ===
    "momentum_mean_reversion": MOM_MR_TEMPLATE,   # Momentum in trending, MR in ranging
    "adx_filtered_crossover": ADX_CROSSOVER,      # Crossover only when ADX > 25
    "multi_timeframe": MULTI_TF_TEMPLATE,         # Align signals across timeframes
}
```

### 2. LLM Code Generation — New `vinu_research/llm_generator.py`

```python
class LlmStrategyGenerator:
    """
    Uses LLM to generate strategy code from natural language descriptions.
    The LLM writes Python code that follows the BaseStrategy interface.
    Generated code is validated via AST parsing + sandboxed execution test.

    Prompt structure:
    SYSTEM: You are a senior quantitative analyst who writes strategy code.
            The code must define a class UserStrategy(BaseStrategy) with:
            - __init__(self, fast_period=None, slow_period=None, ...)
            - generate_weights(self, data: pd.DataFrame) -> pd.Series
            Available indicators in `data`: open, high, low, close, volume,
            plus any technical indicators from the features_required parameter.

    USER: Generate a strategy for: "{user_idea}"
          Symbol: {symbol}, Period: {from_date} → {to_date}
          Indicators available: {indicators_list}

    The LLM returns JSON:
    {{
        "strategy_code": "class UserStrategy(BaseStrategy): ...",
        "indicators_required": ["adx_14", "rsi_14"],
        "reasoning": "Explanation of the strategy logic",
        "expected_performance": "High Sharpe in trending markets"
    }}
    """

    def __init__(self, llm_client: ResearchLlmClient):
        self._llm = llm_client

    async def generate(
        self,
        user_idea: str,
        indicators: list[str],
        symbol: str,
        from_date: str,
        to_date: str,
        n_candidates: int = 3,
    ) -> list[LlmCandidate]:
        """Generate multiple strategy candidates and rank them"""
        candidates = []
        for i in range(n_candidates):
            code = await self._generate_one(user_idea, indicators)
            if self._validate_code(code):
                candidates.append(LlmCandidate(code=code, score=0.0))
        return candidates

    def _validate_code(self, code: str) -> bool:
        """AST parse + syntax check + restricted import validation"""
        try:
            ast.parse(code)
        except SyntaxError:
            return False

        # Check for unsafe patterns
        unsafe = ["__import__", "eval(", "exec(", "os.", "subprocess", "open("]
        if any(pattern in code for pattern in unsafe):
            return False

        # Verify class name and required method
        tree = ast.parse(code)
        has_class = any(
            isinstance(node, ast.ClassDef) and node.name == "UserStrategy"
            for node in ast.walk(tree)
        )
        has_method = any(
            isinstance(node, ast.FunctionDef) and node.name == "generate_weights"
            for node in ast.walk(tree)
        )
        return has_class and has_method

    async def _generate_one(self, user_idea, indicators) -> str:
        prompt = self._build_prompt(user_idea, indicators)
        system_prompt = self._build_system_prompt()
        response = await self._llm.chat_json(system_prompt, prompt)
        return response.get("strategy_code", "")
```

### 3. Strategy Comparison — Risk Critic Selects Best

When both template and LLM generate strategies, the risk critic compares:

```python
class StrategyComparer:
    def compare(self, template_candidates, llm_candidates, backtest_results):
        """
        Rank strategies by:
        1. Out-of-sample Sharpe (if walk-forward available)
        2. Regime diversity (performs well in multiple regimes)
        3. Complexity penalty (fewer params = better)
        4. Robustness score (low variance across walk-forward windows)
        """
        for candidate in template_candidates + llm_candidates:
            result = backtest_results[candidate.id]
            candidate.score = (
                result.sharpe * 0.4
                + result.regime_diversity * 0.2
                + candidate.complexity_penalty() * 0.2
                + result.robustness * 0.2
            )
        return sorted(candidates, key=lambda c: c.score, reverse=True)
```

### 4. Async Generator Integration — Modify `loop.py`

```python
async def _default_quant_coder(self, user_idea, iteration, last_result, last_critique):
    # Phase 1: Quick template generation (always runs)
    recipe = self._detect_recipe(user_idea)
    template_code = generate_strategy(recipe=recipe, user_description=user_idea)

    # Phase 2: LLM generation (if available)
    llm_candidates = []
    if self._llm and self._llm.is_configured():
        llm_gen = LlmStrategyGenerator(self._llm)
        llm_candidates = await llm_gen.generate(
            user_idea=user_idea,
            indicators=self._config.indicators,
            symbol=self._symbol,
            from_date=self._from_date,
            to_date=self._to_date,
        )

    # Phase 3: For iteration 1, use LLM code if valid
    if iteration == 1 and llm_candidates:
        best_llm = llm_candidates[0]  # Will be refined by comparison
        return best_llm.code

    # Phase 4: Apply refinements from previous critique
    if iteration > 1 and last_critique is not None:
        filters = self._generate_filters(last_critique.suggestions)
        code = self._inject_filters(template_code, filters)

    return code
```

### 5. Generator Config

```python
class GeneratorConfig:
    mode: str = "hybrid"                  # "template", "llm", "hybrid"
    template_preference: str = "auto"      # "auto", "crossover", "rsi", etc.
    llm_candidates: int = 3               # Number of LLM candidates to generate
    max_complexity: int = 10              # Max lines in generated strategy body
    allow_llm_code: bool = True           # Enable LLM code generation
    require_validation: bool = True       # Require AST + sandbox validation
```

## Code Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `vinu_research/generator.py` | MAJOR REWRITE | Expand from 3 to 20+ templates, add template discovery |
| `vinu_research/llm_generator.py` | **NEW** | LLM-powered code generation with validation |
| `vinu_research/loop.py` | MODIFY | Integrate LLM generator into quant coder |
| `vinu_research/models.py` | MODIFY | Add LlmCandidate, StrategyCandidate classes |
| `vinu_research/llm.py` | MODIFY | Add strategy generation prompt templates |
| `vinu_research/config.py` | MODIFY | Add generator config fields |
| `tests/test_llm_generator.py` | **NEW** | Tests for LLM code generation and validation |
| `tests/test_templates.py` | **NEW** | Tests for all 20+ templates |

## Complexity & Verdict

- **Difficulty**: High (template expansion is straightforward, but LLM code gen + validation is complex)
- **Lines of code**: ~800-1200 total
- **Priority**: **CRITICAL** — the generator is the heart of the system; 3 templates is unacceptable for a "researcher"
- **Dependencies**: Existing LLM infrastructure (cache, rate limit, circuit breaker)
- **Risk**: Medium — LLM could generate invalid code; validation layer is essential
- **Time estimate**: 8-12 days

## Implementation Order

1. **Phase 1 (3 days)**: Expand template library from 3 to 15 templates
   - Each template gets a unit test that verifies it produces valid Python code
   - Add template metadata (description, parameters, suitable regimes)
2. **Phase 2 (3 days)**: Build LLM code generator
   - Create prompt templates for strategy generation
   - Build AST validation layer
   - Build sandboxed execution test (run on 50 data points to verify no runtime errors)
3. **Phase 3 (2 days)**: Build strategy comparison/ranking
   - Define scoring criteria (Sharpe, robustness, complexity)
   - Prefer simpler strategies with similar performance (Occam's Razor)
4. **Phase 4 (2 days)**: Integrate into research loop
   - LLM mode auto-selects best of template vs LLM code
   - Fallback: LLM fails → template mode always works
5. **Phase 5 (2 days)**: Comprehensive testing
   - Test all templates on real data
   - Test LLM validation rejects bad code
   - Test LLM + template hybrid mode

## Validation Pipeline for Generated Code

```
LLM Output (string)
    → AST Parse (fail → discard)
    → Import check (unsafe imports → discard)
    → Class/Method check (missing → discard)
    → Sandbox exec on 50 rows
        → Runtime error → discard
        → Returns non-Series → discard
        → Series with inf/nan → replace with 0
    → Pass → Validated
```

The sandbox must use `exec()` with restricted `__builtins__`:
```python
def validate_sandbox(code, sample_data):
    restricted_globals = {
        "__builtins__": {"len": len, "range": range, "int": int,
                         "float": float, "abs": abs, "min": min, "max": max,
                         "isinstance": isinstance, "type": type, "list": list,
                         "dict": dict, "pd": pd, "np": np},
        "pd": pd,
        "np": np,
    }
    exec(code, restricted_globals)
    strategy = restricted_globals["UserStrategy"]()
    result = strategy.generate_weights(sample_data)
    assert isinstance(result, pd.Series)
    assert not result.isna().all()
```
