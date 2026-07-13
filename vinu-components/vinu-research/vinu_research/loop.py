from __future__ import annotations

import logging
from collections import OrderedDict
from typing import Any, Callable

from vinu_research.config import ResearchConfig, load_config
from vinu_research.generator import generate_strategy
from vinu_research.llm import LLM_SYSTEM_PROMPT, ResearchLlmClient, _build_risk_critic_prompt
from vinu_research.models import (
    BacktestResult,
    CriticFeedback,
    IterationRecord,
    ResearchResult,
)
from vinu_research.report import generate_report
from vinu_research.tools import ResearchTools, timestamps_from_dates

LOG = logging.getLogger(__name__)

_MAX_CACHE_SIZE = 64


class _LRUCache:
    def __init__(self, maxsize: int = _MAX_CACHE_SIZE):
        self._data: OrderedDict[str, Any] = OrderedDict()
        self._maxsize = maxsize

    def get(self, key: str) -> Any | None:
        if key not in self._data:
            return None
        self._data.move_to_end(key)
        return self._data[key]

    def set(self, key: str, value: Any) -> None:
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = value
        if len(self._data) > self._maxsize:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()


class StrategyResearchLoop:
    def __init__(
        self,
        tools: ResearchTools | None = None,
        config: ResearchConfig | None = None,
        quant_coder: Callable | None = None,
        risk_critic: Callable | None = None,
        on_iteration: Callable | None = None,
    ):
        self._config = config or load_config()
        self._tools = tools or ResearchTools(self._config)
        self._quant_coder = quant_coder or self._default_quant_coder
        self._risk_critic = risk_critic or self._default_risk_critic
        self._on_iteration = on_iteration
        self._story_cache = _LRUCache()
        self._drawdown_cache = _LRUCache()
        self._llm = ResearchLlmClient(self._config) if self._config.llm_enabled else None

    async def run(
        self,
        user_idea: str,
        symbol: str,
        from_date: str,
        to_date: str,
        indicators: list[str] | None = None,
        initial_capital: float | None = None,
    ) -> ResearchResult:
        best_result: BacktestResult | None = None
        best_iteration = -1
        history: list[IterationRecord] = []
        strategy_code = ""

        cache_key = f"{symbol.upper()}:{from_date}:{to_date}"
        self._user_idea = user_idea
        self._symbol = symbol
        self._from_date = from_date
        self._to_date = to_date

        for iteration in range(1, self._config.max_iterations + 1):
            try:
                if iteration == 1:
                    strategy_code = await self._quant_coder(
                        user_idea, iteration, None, None
                    )
                else:
                    last = history[-1]
                    strategy_code = await self._quant_coder(
                        user_idea, iteration, last.result, last.critique
                    )

                result = await self._run_backtest(
                    strategy_code, symbol, from_date, to_date,
                    indicators=indicators,
                    initial_capital=initial_capital,
                )
                if result is None:
                    LOG.warning("Backtest returned no result, stopping")
                    break

                story = self._story_cache.get(cache_key)
                if story is None:
                    story = await self._tools.get_story(
                        symbol,
                        *timestamps_from_dates(from_date, to_date),
                    )
                    self._story_cache.set(cache_key, story)

                drawdowns = self._drawdown_cache.get(cache_key)
                if drawdowns is None:
                    drawdowns = await self._tools.get_drawdowns(
                        symbol,
                        *timestamps_from_dates(from_date, to_date),
                    )
                    self._drawdown_cache.set(cache_key, drawdowns)

                critic_feedback = await self._risk_critic(
                    result, story, drawdowns, iteration
                )

                record = IterationRecord(
                    iteration=iteration,
                    strategy_code=strategy_code,
                    result=result,
                    critique=critic_feedback,
                )
                history.append(record)

                if self._on_iteration:
                    self._on_iteration(record)

                if critic_feedback.verdict == "PASS":
                    best_result = result
                    best_iteration = iteration
                    break

                if critic_feedback.verdict == "STOP":
                    if best_result is None:
                        best_result = result
                        best_iteration = iteration
                    break

                best_result = result
                best_iteration = iteration

                if result.metrics.max_drawdown < self._config.max_drawdown_threshold:
                    LOG.warning(
                        "MaxDD %.1%% exceeds threshold %.1%%, stopping",
                        result.metrics.max_drawdown * 100,
                        self._config.max_drawdown_threshold * 100,
                    )
                    if best_result is None:
                        best_result = result
                        best_iteration = iteration
                    break

                if iteration >= 2 and not self._is_improving(history):
                    break

            except Exception as e:
                LOG.warning("Iteration %d failed: %s, continuing", iteration, e)
                LOG.debug("Iteration error details", exc_info=True)
                if not history:
                    raise
                break

        report_md = generate_report(
            symbol, from_date, to_date, user_idea,
            history, best_result, best_iteration,
        )

        return ResearchResult(
            symbol=symbol,
            from_date=from_date,
            to_date=to_date,
            user_idea=user_idea,
            iterations=history,
            best_result=best_result,
            best_iteration=best_iteration,
            total_iterations=len(history),
            report_md=report_md,
        )

    async def _run_backtest(
        self,
        strategy_code: str,
        symbol: str,
        from_date: str,
        to_date: str,
        indicators: list[str] | None = None,
        initial_capital: float | None = None,
    ) -> BacktestResult | None:
        strategy_class_name = "UserStrategy"
        return await self._tools.run_backtest(
            strategy_code=strategy_code,
            strategy_class_name=strategy_class_name,
            symbols=[symbol],
            from_date=from_date,
            to_date=to_date,
            indicators=indicators,
            initial_capital=initial_capital or self._config.initial_capital,
            transaction_cost_pct=self._config.transaction_cost_pct,
            slippage_pct=self._config.slippage_pct,
            allow_short=self._config.allow_short,
        )

    def _is_improving(self, history: list[IterationRecord]) -> bool:
        if len(history) < 2:
            return True
        prev_sharpe = history[-2].result.metrics.sharpe_ratio
        curr_sharpe = history[-1].result.metrics.sharpe_ratio
        return (curr_sharpe - prev_sharpe) > self._config.improvement_threshold

    async def _default_quant_coder(
        self,
        user_idea: str,
        iteration: int,
        last_result: BacktestResult | None,
        last_critique: CriticFeedback | None,
    ) -> str:
        recipe = None
        desc_lower = user_idea.lower()
        if "crossover" in desc_lower or "sma" in desc_lower or "ma" in desc_lower:
            recipe = "crossover"
        elif "rsi" in desc_lower or "mean reversion" in desc_lower:
            recipe = "rsi"
        elif "momentum" in desc_lower or "trend" in desc_lower:
            recipe = "momentum"

        code = generate_strategy(recipe=recipe, user_description=user_idea)

        if iteration > 1 and last_critique is not None:
            lines = code.split("\n")
            insert_line = None
            for i, line in enumerate(lines):
                if line.strip().startswith("def generate_weights"):
                    insert_line = i
                    break

            filters = self._generate_filters(last_critique.suggestions)
            if filters and insert_line is not None:
                indent = "        "
                for f_line in reversed(filters):
                    lines.insert(insert_line + 1, indent + f_line)
                code = "\n".join(lines)

        return code

    def _generate_filters(self, suggestions: list[str]) -> list[str]:
        filters: list[str] = []
        for suggestion in suggestions:
            s_lower = suggestion.lower()
            if "adx" in s_lower:
                filters.append("# ADX filter: no trade if ADX < 20")
                filters.append("adx = data.get('adx_14', pd.Series(25.0, index=data.index))")
                filters.append("signal[adx < 20] = 0")
            if "session" in s_lower and "london" in s_lower:
                filters.append("# Session filter: skip London session")
                filters.append("session = data.get('session', pd.Series('ny_regular', index=data.index))")
                filters.append("signal[session == 'london'] = 0")
            if "cool" in s_lower or "news" in s_lower:
                filters.append("# News cooling-off: skip 60min after high-impact news")
                filters.append("news_cooldown = data.get('news_cooldown', pd.Series(False, index=data.index))")
                filters.append("signal[news_cooldown] = 0")
            if "volatil" in s_lower:
                filters.append("# Volatility guard: skip if ATR > 5%")
                filters.append("atr = data.get('atr_14', pd.Series(0.0, index=data.index))")
                filters.append("close = data['close']")
                filters.append("signal[atr / close > 0.05] = 0")
        return filters

    def _rule_based_check(
        self,
        result: BacktestResult,
        story: dict[str, Any] | None,
        drawdowns: dict[str, Any] | None,
        iteration: int,
    ) -> CriticFeedback:
        m = result.metrics
        suggestions: list[str] = []

        if m.max_drawdown < -0.15:
            suggestions.append("Max drawdown exceeds 15% — add volatility guard (ATR filter)")
        if m.sharpe_ratio < 0.5:
            suggestions.append("Sharpe below 0.5 — add ADX filter to avoid choppy markets")
        if m.win_rate < 0.40:
            suggestions.append("Win rate below 40% — add session filter to skip London news volatility")

        if story:
            dd_events = story.get("drawdown_events", [])
            london_dd = [
                dd for dd in dd_events
                if "london" in str(dd.get("sessions_involved", [])).lower()
            ]
            if len(london_dd) >= 2:
                suggestions.append("Multiple drawdowns in London session — add London session exclusion filter")

        if m.sharpe_ratio >= 1.5 and m.max_drawdown > -0.08:
            return CriticFeedback(
                verdict="PASS",
                reasoning=f"Strategy passes with Sharpe={m.sharpe_ratio:.2f}, MaxDD={m.max_drawdown:.1%}",
                suggestions=[],
            )

        if iteration >= 3 and m.sharpe_ratio < 0.3:
            return CriticFeedback(
                verdict="STOP",
                reasoning=f"Sharpe={m.sharpe_ratio:.2f} unchanged after {iteration} iterations",
                suggestions=[],
            )

        if not suggestions:
            suggestions.append("Try tightening position sizing or adding a news cooldown period")

        reasoning_parts = [f"Sharpe={m.sharpe_ratio:.2f}, MaxDD={m.max_drawdown:.1%}, WinRate={m.win_rate:.0%}"]
        reasoning_parts.append(f"Suggestions: {'; '.join(suggestions)}")

        return CriticFeedback(
            verdict="REFINE",
            reasoning=", ".join(reasoning_parts),
            suggestions=suggestions,
        )

    async def _llm_enhanced_check(
        self,
        user_idea: str,
        symbol: str,
        from_date: str,
        to_date: str,
        result: BacktestResult,
        story: dict[str, Any] | None,
        rules_feedback: CriticFeedback,
    ) -> dict[str, Any] | None:
        if not hasattr(self, "_llm") or self._llm is None:
            return None
        if not self._llm.is_configured():
            return None
        prompt = _build_risk_critic_prompt(
            user_idea, symbol, from_date, to_date,
            result, rules_feedback, story,
        )
        try:
            return await self._llm.chat_json(LLM_SYSTEM_PROMPT, prompt)
        except Exception as e:
            LOG.warning("LLM enhanced check failed: %s, falling back to rules only", e)
            return None

    def _merge_feedback(
        self,
        rules: CriticFeedback,
        llm: dict[str, Any] | None,
    ) -> CriticFeedback:
        if llm is None:
            return rules
        new_suggestions = list(rules.suggestions)
        for llm_s in llm.get("additional_suggestions", []):
            if llm_s not in new_suggestions:
                new_suggestions.append(llm_s)
        verdict = rules.verdict
        llm_upgrade = llm.get("verdict_upgrade")
        if verdict == "REFINE" and llm_upgrade in ("PASS", "STOP"):
            verdict = llm_upgrade
        merged_reasoning = rules.reasoning
        if llm.get("reasoning"):
            merged_reasoning += f" | LLM notes: {llm['reasoning']}"
        return CriticFeedback(
            verdict=verdict,
            reasoning=merged_reasoning,
            suggestions=new_suggestions,
        )

    async def _default_risk_critic(
        self,
        result: BacktestResult,
        story: dict[str, Any] | None,
        drawdowns: dict[str, Any] | None,
        iteration: int,
    ) -> CriticFeedback:
        rules = self._rule_based_check(result, story, drawdowns, iteration)
        llm = await self._llm_enhanced_check(
            self._user_idea if hasattr(self, "_user_idea") else "",
            self._symbol if hasattr(self, "_symbol") else "",
            self._from_date if hasattr(self, "_from_date") else "",
            self._to_date if hasattr(self, "_to_date") else "",
            result, story, rules,
        )
        return self._merge_feedback(rules, llm)
