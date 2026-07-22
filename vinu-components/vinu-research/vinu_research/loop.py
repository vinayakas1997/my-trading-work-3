from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Callable

import pandas as pd

from vinu_research.comparison import rank_candidates
from vinu_research.config import ResearchConfig, load_config
from vinu_research.generator import find_recipe, generate_strategy
from vinu_research.llm import LLM_SYSTEM_PROMPT, ResearchLlmClient, _build_risk_critic_prompt
from vinu_research.llm_generator import LlmStrategyGenerator
from vinu_research.models import (
    BacktestMetrics,
    BacktestResult,
    CriticFeedback,
    HoldoutResult,
    IterationRecord,
    ResearchResult,
    StressTestResult,
    StressWindowResult,
    WalkForwardResult,
)
from vinu_research.report import generate_report
from vinu_research.benchmark import compute_benchmark_comparison, compute_benchmark_returns_metrics
from vinu_research.portfolio import analyze_portfolio
from vinu_research.tools import ResearchTools, timestamps_from_dates
from vinu_research.walk_forward import (
    WalkForwardConfig,
    WalkForwardWindow,
    WindowSplitter,
    aggregate_metrics,
)

LOG = logging.getLogger(__name__)

_MAX_CACHE_SIZE = 64
_MIN_HOLDOUT_DAYS = 5
_MIN_RESEARCH_DAYS = 30


def _split_research_and_holdout(
    from_date: str,
    to_date: str,
    holdout_fraction: float,
    gap_days: int,
) -> tuple[str, str, str, str] | None:
    """
    Carve a trailing slice of the requested range off as a true holdout: the
    refinement loop (iterations, filter generation, the PASS/REFINE/STOP decision)
    only ever sees `research_from..research_to`. `holdout_from..holdout_to` is
    evaluated exactly once, after a candidate has already looked good enough
    in-sample to be worth checking, and is never used to choose a filter.

    Returns None if the range is too short to carve a meaningful holdout out of —
    callers should fall back to running without holdout gating in that case rather
    than fail the whole run.
    """
    from_dt = datetime.strptime(from_date, "%Y-%m-%d")
    to_dt = datetime.strptime(to_date, "%Y-%m-%d")
    total_days = (to_dt - from_dt).days

    holdout_days = int(total_days * holdout_fraction)
    research_days = total_days - holdout_days - gap_days

    if holdout_days < _MIN_HOLDOUT_DAYS or research_days < _MIN_RESEARCH_DAYS:
        return None

    holdout_start_dt = to_dt - timedelta(days=holdout_days)
    research_end_dt = holdout_start_dt - timedelta(days=gap_days)

    return (
        from_dt.strftime("%Y-%m-%d"),
        research_end_dt.strftime("%Y-%m-%d"),
        holdout_start_dt.strftime("%Y-%m-%d"),
        to_dt.strftime("%Y-%m-%d"),
    )


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
        self._benchmark_returns: pd.Series | None = None
        self._benchmark_cache_key: str = ""
        self._llm = ResearchLlmClient(self._config) if self._config.llm_enabled else None

    async def run(
        self,
        user_idea: str,
        symbol: str,
        from_date: str,
        to_date: str,
        strategy_code: str | None = None,
        indicators: list[str] | None = None,
        initial_capital: float | None = None,
        universe: list[str] | None = None,
    ) -> ResearchResult:
        """
        `symbol` remains the primary ticker used for story/drawdown lookups (the
        correlation service is keyed per-symbol, with no multi-symbol equivalent)
        and for report headers. Pass `universe` (a list of 2+ tickers, `symbol`
        need not be included) to additionally backtest the same strategy across a
        basket of names — the underlying engine already runs one strategy per
        symbol and aggregates into a single portfolio, so this is a wiring change
        here, not a new engine capability. When `universe` has fewer than 2
        distinct symbols, behavior is identical to a single-symbol run.
        """
        best_result: BacktestResult | None = None
        best_iteration = -1
        history: list[IterationRecord] = []
        strategy_code = strategy_code or ""
        holdout_result: HoldoutResult | None = None

        backtest_symbols = list(dict.fromkeys(universe)) if universe and len(set(universe)) > 1 else [symbol]

        # Reserve a trailing slice of the range the refinement loop never sees — no
        # filter is ever chosen using this data, so it's a real check on whether a
        # PASS candidate generalizes rather than just fit the researched period.
        split = _split_research_and_holdout(
            from_date, to_date,
            self._config.holdout_fraction, self._config.holdout_gap_days,
        )
        if split is not None:
            research_from, research_to, holdout_from, holdout_to = split
        else:
            LOG.info("Date range too short to carve a holdout — running without holdout gating")
            research_from, research_to, holdout_from, holdout_to = from_date, to_date, "", ""

        cache_key = f"{symbol.upper()}:{research_from}:{research_to}"
        self._user_idea = user_idea
        self._symbol = symbol
        self._from_date = research_from
        self._to_date = research_to
        # Tracked so _generate_filters can check whether an indicator a filter needs
        # was actually requested — if not, the simulator won't have computed it and
        # injecting the filter would just run against a fake constant column.
        self._indicators = indicators or []

        # Fetched once up front (depends only on symbol + interval, not on research
        # dates or iteration state) so the strategy generator sees the same
        # deterministic angle signals as the risk critic, from iteration 1 onward.
        self._angle_context = await self._tools.get_angle_context(
            symbol, self._config.interval,
        )

        # Feature/factor snapshot from vinu-tools — includes Alpha101/191,
        # ML pipeline outputs, and recipe bundles. Fetched alongside angle
        # context so the LLM generator sees richer signals than just the 3
        # hardcoded indicators (sma_20, sma_50, rsi_14).
        self._feature_snapshot = await self._tools.get_feature_snapshot(symbol)

        benchmark_symbol = self._config.benchmark_symbol
        bench_cache_key = f"{benchmark_symbol}:{research_from}:{research_to}"

        for iteration in range(1, self._config.max_iterations + 1):
            try:
                if iteration == 1 and not strategy_code:
                    strategy_code = await self._quant_coder(
                        user_idea, iteration, None, None
                    )
                elif iteration > 1:
                    last = history[-1]
                    strategy_code = await self._quant_coder(
                        user_idea, iteration, last.result, last.critique, last.strategy_code
                    )

                # 1. Static AST Verification Check
                verification_errors = self._verify_strategy_code(strategy_code)
                if verification_errors:
                    result = BacktestResult(
                        run_id=f"failed_verification_{iteration}",
                        strategy_name="UserStrategy",
                        metrics=BacktestMetrics.from_dict({}),
                        benchmark_metrics={},
                        trade_count=0,
                        equity_points=0,
                        raw={},
                    )
                    critic_feedback = CriticFeedback(
                        verdict="REFINE",
                        reasoning=f"Static AST Verification failed: {verification_errors[0]}",
                        suggestions=verification_errors,
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
                    continue

                result = await self._run_backtest(
                    strategy_code, symbol, research_from, research_to,
                    indicators=indicators,
                    initial_capital=initial_capital,
                    symbols=backtest_symbols,
                )
                if result is None:
                    LOG.warning("Backtest returned no result, stopping")
                    break

                if self._benchmark_returns is None or self._benchmark_cache_key != bench_cache_key:
                    self._benchmark_returns = await self._tools.get_benchmark_data(
                        benchmark_symbol, research_from, research_to,
                    )
                    self._benchmark_cache_key = bench_cache_key

                if self._benchmark_returns is not None:
                    bm_metrics = compute_benchmark_returns_metrics(
                        self._benchmark_returns
                    )
                    result.benchmark_metrics[benchmark_symbol] = bm_metrics

                story = self._story_cache.get(cache_key)
                if story is None:
                    story = await self._tools.get_story(
                        symbol,
                        *timestamps_from_dates(research_from, research_to),
                    ) or {}
                    # Enrich with the deterministic angle context (trend_lifecycle,
                    # session structure, news causality) for the critic and LLM;
                    # already fetched once up front, before the loop.
                    if self._angle_context:
                        story["angles"] = self._angle_context
                    self._story_cache.set(cache_key, story)

                drawdowns = self._drawdown_cache.get(cache_key)
                if drawdowns is None:
                    drawdowns = await self._tools.get_drawdowns(
                        symbol,
                        *timestamps_from_dates(research_from, research_to),
                    )
                    self._drawdown_cache.set(cache_key, drawdowns)

                critic_feedback = await self._risk_critic(
                    result, story, drawdowns, iteration
                )

                # 2. Post-backtest Weight Holding Check
                holding_errors = await self._verify_weights_holding(result.run_id)
                if holding_errors:
                    critic_feedback = CriticFeedback(
                        verdict="REFINE",
                        reasoning=f"Weight holding verification failed: {holding_errors[0]}",
                        suggestions=critic_feedback.suggestions + holding_errors,
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
                    if holdout_from and holdout_to:
                        holdout_result = await self._check_holdout(
                            strategy_code, symbol, holdout_from, holdout_to,
                            result, indicators, initial_capital,
                            symbols=backtest_symbols,
                        )
                    if holdout_result is None or holdout_result.passed:
                        if best_result is None or result.metrics.sharpe_ratio > best_result.metrics.sharpe_ratio:
                            best_result = result
                            best_iteration = iteration
                        break
                    # Don't accept an in-sample PASS that fails holdout validation —
                    # downgrade back to REFINE and let refinement continue.
                    downgraded = CriticFeedback(
                        verdict="REFINE",
                        reasoning=(
                            f"{critic_feedback.reasoning} | Holdout check failed: "
                            f"{holdout_result.note}"
                        ),
                        suggestions=critic_feedback.suggestions + [
                            f"Holdout validation failed: {holdout_result.note}. "
                            "Strategy may be overfit to the researched period."
                        ],
                    )
                    record.critique = downgraded
                    critic_feedback = downgraded
                    # Falls through to the REFINE handling below (best_result is set
                    # there too), so the loop continues iterating instead of stopping.

                if critic_feedback.verdict == "STOP":
                    if best_result is None:
                        best_result = result
                        best_iteration = iteration
                    break

                if best_result is None or result.metrics.sharpe_ratio > best_result.metrics.sharpe_ratio:
                    best_result = result
                    best_iteration = iteration

                if result.metrics.max_drawdown < self._config.max_drawdown_threshold:
                    LOG.warning(
                        "MaxDD %.1f%% exceeds threshold %.1f%%, stopping",
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

        best_rec = next(
            (r for r in history if r.iteration == best_iteration),
            history[-1] if history else None,
        )

        walk_forward_result: WalkForwardResult | None = None
        if self._config.walk_forward_enabled and best_result and best_rec:
            walk_forward_result = await self._run_walk_forward(
                strategy_code=best_rec.strategy_code,
                symbol=symbol,
                from_date=from_date,
                to_date=to_date,
                indicators=indicators,
                initial_capital=initial_capital,
            )

        stress_test_result: StressTestResult | None = None
        if best_result and best_rec:
            stress_test_result = await self._run_stress_test(
                strategy_code=best_rec.strategy_code,
                symbol=symbol,
                indicators=indicators,
                initial_capital=initial_capital,
                symbols=backtest_symbols,
            )

        equity_rets = None
        if best_result and self._benchmark_returns is not None and len(self._benchmark_returns) >= 20:
            equity_rets = await self._tools.fetch_equity_returns(best_result.run_id)
            if equity_rets is not None and len(equity_rets) >= 20:
                comparison = compute_benchmark_comparison(
                    equity_rets, self._benchmark_returns
                )
                if comparison:
                    bm_dict = best_result.benchmark_metrics.setdefault(benchmark_symbol, {})
                    bm_dict.update(comparison)

        portfolio_result = None
        if (
            len(backtest_symbols) > 1
            and equity_rets is not None
            and self._benchmark_returns is not None
        ):
            returns_by_symbol: dict[str, pd.Series] = {}
            for sym in backtest_symbols:
                sym_returns = await self._tools.get_benchmark_data(sym, research_from, research_to)
                if sym_returns is not None and len(sym_returns) >= 20:
                    returns_by_symbol[sym] = sym_returns
            portfolio_result = analyze_portfolio(
                returns_by_symbol,
                equity_rets,
                self._benchmark_returns,
                lookback_days=self._config.portfolio_beta_hedge_lookback_days,
                max_hedge_ratio=self._config.portfolio_beta_hedge_max_ratio,
            )

        report_md = generate_report(
            symbol, from_date, to_date, user_idea,
            history, best_result, best_iteration,
            walk_forward=walk_forward_result,
            holdout=holdout_result,
            portfolio=portfolio_result,
            stress_test=stress_test_result,
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
            walk_forward=walk_forward_result,
            holdout=holdout_result,
            portfolio=portfolio_result,
            stress_test=stress_test_result,
        )

    async def _run_backtest(
        self,
        strategy_code: str,
        symbol: str,
        from_date: str,
        to_date: str,
        indicators: list[str] | None = None,
        initial_capital: float | None = None,
        symbols: list[str] | None = None,
    ) -> BacktestResult | None:
        strategy_class_name = "UserStrategy"
        return await self._tools.run_backtest(
            strategy_code=strategy_code,
            strategy_class_name=strategy_class_name,
            symbols=symbols or [symbol],
            from_date=from_date,
            to_date=to_date,
            indicators=indicators,
            initial_capital=initial_capital or self._config.initial_capital,
            transaction_cost_pct=self._config.transaction_cost_pct,
            slippage_pct=self._config.slippage_pct,
            allow_short=self._config.allow_short,
            interval=self._config.interval,
        )

    async def _check_holdout(
        self,
        strategy_code: str,
        symbol: str,
        holdout_from: str,
        holdout_to: str,
        in_sample_result: BacktestResult,
        indicators: list[str] | None,
        initial_capital: float | None,
        symbols: list[str] | None = None,
    ) -> HoldoutResult | None:
        """
        Re-test a strategy that just earned an in-sample PASS against data the
        refinement loop never touched. Returns None (accept without gating) if the
        holdout backtest itself can't be run — e.g. the simulator is unreachable —
        matching the codebase's existing pattern of degrading gracefully on service
        failures rather than blocking the whole run on an infrastructure issue.
        """
        try:
            holdout_bt = await self._run_backtest(
                strategy_code, symbol, holdout_from, holdout_to,
                indicators=indicators, initial_capital=initial_capital,
                symbols=symbols,
            )
        except Exception as e:
            LOG.warning("Holdout backtest failed: %s, accepting without holdout gating", e)
            return None
        if holdout_bt is None:
            return None

        is_sharpe = in_sample_result.metrics.sharpe_ratio
        oos_sharpe = holdout_bt.metrics.sharpe_ratio

        if oos_sharpe < 0:
            passed, note = False, f"holdout Sharpe {oos_sharpe:.2f} is negative"
        else:
            degradation = (is_sharpe - oos_sharpe) / max(abs(is_sharpe), 1e-6)
            if degradation > self._config.max_holdout_sharpe_degradation:
                passed = False
                note = (
                    f"holdout Sharpe ({oos_sharpe:.2f}) degraded {degradation:.0%} "
                    f"vs in-sample ({is_sharpe:.2f}), exceeding the "
                    f"{self._config.max_holdout_sharpe_degradation:.0%} threshold"
                )
            else:
                passed, note = True, ""

        return HoldoutResult(
            holdout_from=holdout_from,
            holdout_to=holdout_to,
            in_sample_sharpe=is_sharpe,
            holdout_sharpe=oos_sharpe,
            holdout_max_drawdown=holdout_bt.metrics.max_drawdown,
            holdout_total_return=holdout_bt.metrics.total_return,
            holdout_trade_count=holdout_bt.trade_count,
            passed=passed,
            note=note,
        )

    async def _run_walk_forward(
        self,
        strategy_code: str,
        symbol: str,
        from_date: str,
        to_date: str,
        indicators: list[str] | None = None,
        initial_capital: float | None = None,
    ) -> WalkForwardResult | None:
        wf_config = WalkForwardConfig(
            method=self._config.walk_forward_method,
            train_pct=self._config.walk_forward_train_pct,
            test_pct=self._config.walk_forward_test_pct,
            n_windows=self._config.walk_forward_windows,
            min_train_days=self._config.walk_forward_min_train_days,
            step_size_days=self._config.walk_forward_step_size_days,
            gap_days=self._config.walk_forward_gap_days,
        )
        splitter = WindowSplitter(wf_config)
        windows = splitter.split(from_date, to_date)

        if not windows:
            LOG.warning("Walk-forward: not enough data for %d windows", wf_config.n_windows)
            return None

        LOG.info("Walk-forward: running %d windows", len(windows))

        async def _run_window(w: WalkForwardWindow) -> dict | None:
            is_result, oos_result = await asyncio.gather(
                self._run_backtest(
                    strategy_code=strategy_code,
                    symbol=symbol,
                    from_date=w.train_start,
                    to_date=w.train_end,
                    indicators=indicators,
                    initial_capital=initial_capital,
                ),
                self._run_backtest(
                    strategy_code=strategy_code,
                    symbol=symbol,
                    from_date=w.test_start,
                    to_date=w.test_end,
                    indicators=indicators,
                    initial_capital=initial_capital,
                ),
                return_exceptions=True,
            )
            if isinstance(is_result, Exception) or is_result is None:
                return None
            if isinstance(oos_result, Exception) or oos_result is None:
                return None
            return {
                "window_id": w.window_id,
                "train_start": w.train_start,
                "train_end": w.train_end,
                "test_start": w.test_start,
                "test_end": w.test_end,
                "in_sample_metrics": {
                    "sharpe_ratio": is_result.metrics.sharpe_ratio,
                    "max_drawdown": is_result.metrics.max_drawdown,
                    "win_rate": is_result.metrics.win_rate,
                    "cagr": is_result.metrics.cagr,
                    "total_return": is_result.metrics.total_return,
                },
                "out_of_sample_metrics": {
                    "sharpe_ratio": oos_result.metrics.sharpe_ratio,
                    "max_drawdown": oos_result.metrics.max_drawdown,
                    "win_rate": oos_result.metrics.win_rate,
                    "cagr": oos_result.metrics.cagr,
                    "total_return": oos_result.metrics.total_return,
                },
            }

        raw = await asyncio.gather(
            *[_run_window(w) for w in windows],
            return_exceptions=True,
        )
        window_records = [r for r in raw if isinstance(r, dict)]

        if not window_records:
            return None

        is_list = [r["in_sample_metrics"] for r in window_records]
        oos_list = [r["out_of_sample_metrics"] for r in window_records]
        aggregated_is, aggregated_oos = aggregate_metrics(is_list, oos_list)

        is_sharpe = aggregated_is.get("sharpe_ratio", 0.0)
        oos_sharpe = aggregated_oos.get("sharpe_ratio", 0.0)
        is_max_dd = aggregated_is.get("max_drawdown", 0.0)
        oos_max_dd = aggregated_oos.get("max_drawdown", 0.0)
        is_win_rate = aggregated_is.get("win_rate", 0.0)
        oos_win_rate = aggregated_oos.get("win_rate", 0.0)

        LOG.info(
            "Walk-forward: IS Sharpe=%.2f, OOS Sharpe=%.2f, gap=%.2f",
            is_sharpe, oos_sharpe, is_sharpe - oos_sharpe,
        )

        return WalkForwardResult(
            windows=window_records,
            aggregated_is_metrics=aggregated_is,
            aggregated_oos_metrics=aggregated_oos,
            sharpe_gap=is_sharpe - oos_sharpe,
            max_dd_gap=oos_max_dd - is_max_dd,
            win_rate_gap=is_win_rate - oos_win_rate,
            n_windows=len(window_records),
            method=self._config.walk_forward_method,
        )

    async def _run_stress_test(
        self,
        strategy_code: str,
        symbol: str,
        indicators: list[str] | None = None,
        initial_capital: float | None = None,
        symbols: list[str] | None = None,
    ) -> StressTestResult | None:
        """Replay the winning strategy through fixed historical crisis windows.

        Unlike walk-forward/holdout, these windows are never used to pick or
        tune the strategy — they're only ever run once, after refinement is
        already done, purely to answer "what does this do in a known shock."
        """
        if not self._config.stress_test_enabled or not self._config.stress_test_windows:
            return None

        results: list[StressWindowResult] = []
        for name, w_from, w_to in self._config.stress_test_windows:
            try:
                bt = await self._run_backtest(
                    strategy_code, symbol, w_from, w_to,
                    indicators=indicators, initial_capital=initial_capital,
                    symbols=symbols,
                )
            except Exception as e:
                LOG.warning("Stress window %s failed: %s", name, e)
                results.append(StressWindowResult(
                    name=name, from_date=w_from, to_date=w_to,
                    note=f"backtest failed: {e}",
                ))
                continue

            if bt is None or bt.trade_count == 0:
                # No price data for this symbol over this window (e.g. it IPO'd
                # after 2020), or the strategy never traded — not a failure,
                # just not evaluable, so it's excluded from the pass/fail roll-up
                # rather than counted against the strategy.
                results.append(StressWindowResult(
                    name=name, from_date=w_from, to_date=w_to,
                    note="no data or no trades in this window",
                ))
                continue

            passed = bt.metrics.max_drawdown >= self._config.stress_test_max_drawdown_threshold
            results.append(StressWindowResult(
                name=name, from_date=w_from, to_date=w_to,
                max_drawdown=bt.metrics.max_drawdown,
                total_return=bt.metrics.total_return,
                trade_count=bt.trade_count,
                passed=passed,
                note="" if passed else (
                    f"max_drawdown {bt.metrics.max_drawdown:.1%} breached threshold "
                    f"{self._config.stress_test_max_drawdown_threshold:.1%}"
                ),
            ))

        if not results:
            return None
        return StressTestResult(windows=results)

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
        previous_code: str | None = None,
    ) -> str:
        llm_available = (
            self._llm and self._llm.is_configured()
            and self._config.generator_mode in ("llm", "hybrid")
        )
        story: dict[str, Any] | None = None
        if getattr(self, "_angle_context", None):
            story = {"angles": self._angle_context}
            feat = getattr(self, "_feature_snapshot", None)
            if feat:
                story["features"] = feat
        indicators = ["sma_20", "sma_50", "rsi_14"]
        symbol = self._symbol if hasattr(self, "_symbol") else ""
        from_date = self._from_date if hasattr(self, "_from_date") else ""
        to_date = self._to_date if hasattr(self, "_to_date") else ""

        if iteration == 1:
            llm_code: str | None = None
            if llm_available:
                llm_gen = LlmStrategyGenerator(self._llm)
                candidates = await llm_gen.generate(
                    user_idea=user_idea,
                    symbol=symbol,
                    from_date=from_date,
                    to_date=to_date,
                    indicators=indicators,
                    n_candidates=self._config.llm_candidates,
                    story=story,
                )
                if candidates:
                    # Rank by complexity penalty (no backtest results available yet
                    # at generation time) rather than blindly taking the first
                    # candidate the LLM happened to return first.
                    ranked = rank_candidates(candidates)
                    best = ranked[0].candidate
                    llm_code = best.code
                    LOG.info(
                        "LLM generated strategy (ranked best of %d candidates, score=%.1f): %s",
                        len(candidates), ranked[0].score, best.reasoning[:100],
                    )
            if llm_code:
                return llm_code
            recipe = find_recipe(user_idea)
            return generate_strategy(recipe=recipe, user_description=user_idea)

        # Iteration 2+: LLM refinement is the primary path — it sees the previous
        # code, the actual backtest metrics, and the critic's suggestions, and can
        # rewrite the strategy directly instead of only splicing fixed filters.
        # The template + rule-based filter injection below is kept only as the
        # fallback for `--no-llm`/generator_mode="template" or if the LLM call
        # fails; it is not being actively developed further for now.
        if llm_available and previous_code and last_result is not None and last_critique is not None:
            llm_gen = LlmStrategyGenerator(self._llm)
            candidates = await llm_gen.refine(
                user_idea=user_idea,
                symbol=symbol,
                from_date=from_date,
                to_date=to_date,
                previous_code=previous_code,
                last_result=last_result,
                last_critique=last_critique,
                indicators=indicators,
                n_candidates=self._config.llm_candidates,
                story=story,
            )
            if candidates:
                ranked = rank_candidates(candidates)
                best = ranked[0].candidate
                LOG.info(
                    "LLM refined strategy (ranked best of %d candidates, score=%.1f): %s",
                    len(candidates), ranked[0].score, best.reasoning[:100],
                )
                return best.code

        if llm_available and previous_code:
            LOG.warning(
                "LLM refinement returned no candidates for iteration %d, "
                "reusing previous iteration's code", iteration,
            )
            code = previous_code
        else:
            recipe = find_recipe(user_idea)
            code = generate_strategy(recipe=recipe, user_description=user_idea)

        if last_critique is not None:
            lines = code.split("\n")
            def_line = None
            for i, line in enumerate(lines):
                if line.strip().startswith("def generate_weights"):
                    def_line = i
                    break

            # Filters read/modify the strategy's already-computed signal/weights
            # variable, so they must land right before the function's return
            # statement, not immediately after its signature — inserting there
            # runs the filter before that variable exists, raising
            # UnboundLocalError the moment the backtest actually executes it.
            return_line = None
            if def_line is not None:
                for i in range(def_line + 1, len(lines)):
                    if lines[i].strip().startswith("return"):
                        return_line = i
                        break

            filters = self._generate_filters(last_critique.suggestions)
            if filters and return_line is not None:
                indent = "        "
                for f_line in reversed(filters):
                    lines.insert(return_line, indent + f_line)
                code = "\n".join(lines)

        return code

    def _classify_suggestion(self, suggestion: str) -> str | None:
        """
        Map a critique suggestion to one of the known filter kinds, or None if it
        doesn't clearly match. Requires multiple, more specific signal words per
        kind (not a single common word like bare "news" or "cool") so that
        incidental phrasing in free-text LLM suggestions doesn't trigger a filter
        the suggestion wasn't actually asking for.
        """
        s = suggestion.lower()
        if "adx" in s:
            return "adx"
        if "london" in s and ("session" in s or "exclusion" in s):
            return "session_exclusion"
        if "news" in s and ("cool" in s or "pause" in s):
            return "news_cooldown"
        if "volatil" in s:
            return "volatility_guard"
        return None

    def _generate_filters(self, suggestions: list[str]) -> list[str]:
        # What each filter kind actually reads from `data` — if none of these were
        # requested via --indicators, the simulator never computed the column, and
        # injecting the filter would run against a constant fake value instead of
        # real market data (e.g. an "ADX filter" that never actually sees ADX).
        required_indicator_keywords: dict[str, tuple[str, ...]] = {
            "adx": ("adx",),
            "volatility_guard": ("atr", "volatil"),
            # session/news columns aren't sourced from the --indicators list in this
            # system; treat them as always available rather than blocking on a
            # signal this check has no way to verify.
        }

        filter_code: dict[str, list[str]] = {
            "adx": [
                "# ADX filter: no trade if ADX < 20",
                "adx = data['adx_14']",
                "signal[adx < 20] = 0",
            ],
            "session_exclusion": [
                "# Session filter: skip London session",
                "session = data.get('session', pd.Series('ny_regular', index=data.index))",
                "signal[session == 'london'] = 0",
            ],
            "news_cooldown": [
                "# News cooling-off: skip 60min after high-impact news",
                "news_cooldown = data.get('news_cooldown', pd.Series(False, index=data.index))",
                "signal[news_cooldown] = 0",
            ],
            "volatility_guard": [
                "# Volatility guard: skip if ATR > 5%",
                "atr = data['atr_14']",
                "close = data['close']",
                "signal[atr / close > 0.05] = 0",
            ],
        }

        available_indicators = [i.lower() for i in getattr(self, "_indicators", [])]

        applied_kinds: set[str] = set()
        filters: list[str] = []
        for suggestion in suggestions:
            kind = self._classify_suggestion(suggestion)
            if kind is None or kind in applied_kinds:
                continue

            needed = required_indicator_keywords.get(kind)
            if needed and not any(
                kw in ind for ind in available_indicators for kw in needed
            ):
                LOG.info(
                    "Skipping %s filter: none of %s present in requested indicators %s",
                    kind, needed, available_indicators,
                )
                continue

            filters.extend(filter_code[kind])
            applied_kinds.add(kind)

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

            # Deterministic angle context (suggestions only — never changes verdicts)
            angles = story.get("angles") or {}
            tl = angles.get("trend_lifecycle") or {}
            sig = tl.get("signal") or {}
            if tl.get("risk") == "high" or sig.get("signal_type") == "book_profits":
                exit_pct = sig.get("exit_threshold_pct")
                hint = f" (pattern library suggests exit at {exit_pct}% from peak)" if exit_pct is not None else ""
                suggestions.append(
                    f"trend_lifecycle flags '{tl.get('stage', 'unknown')}' stage with "
                    f"{tl.get('risk', 'unknown')} reversal risk — consider a trailing stop "
                    f"or profit-taking rule{hint}"
                )
            nc = angles.get("news_causality") or {}
            granger = nc.get("granger_causes_prices")
            p_value = nc.get("p_value")
            if granger and (p_value is None or p_value < 0.05):
                lag = nc.get("best_lag_minutes")
                suggestions.append(
                    f"News Granger-causes price moves (lag ~{lag} min, p={p_value}) — "
                    "news-based entry/exit filters may add edge"
                )
            elif granger is False:
                suggestions.append(
                    "No news→price causality detected for this symbol — "
                    "avoid news-driven entry conditions"
                )
            ss = angles.get("session_structure") or {}
            if ss.get("worst_session"):
                suggestions.append(
                    f"Session structure ({ss.get('time_format')}): drawdowns after peaks are "
                    f"deepest in the {ss['worst_session']} session (shallowest: "
                    f"{ss.get('best_session')}) — consider a session filter"
                )

        if m.cvar_95 < -0.03:
            suggestions.append(
                f"CVaR 95% is {m.cvar_95:.1%} — "
                "extreme tail risk. Consider stop-loss or position limits"
            )

        if m.recovery_time_days > 120:
            suggestions.append(
                f"Recovery from max drawdown took {m.recovery_time_days} days. "
                "Consider adding drawdown-recovery filters"
            )

        if m.annual_turnover > 2000:
            suggestions.append(
                f"Annual turnover {m.annual_turnover:.0f}% — "
                "costs will erode edge. Add holding period filter"
            )

        if m.sharpe_p_value > 0.05:
            suggestions.append(
                f"Sharpe {m.sharpe_ratio:.2f} is not statistically significant "
                f"(p={m.sharpe_p_value:.3f}). Need more data"
            )

        if m.profit_factor < 1.0 and m.profit_factor > 0:
            suggestions.append(
                f"Profit factor {m.profit_factor:.2f} < 1 — "
                "strategy loses more on losers than it gains on winners"
            )

        if m.var_95 < -0.04:
            suggestions.append(
                f"VaR (95%) is {m.var_95:.1%} — "
                "daily loss risk too high. Add tighter stop-loss"
            )

        if result.benchmark_metrics:
            for bm_name, bm_data in result.benchmark_metrics.items():
                bm_sharpe = bm_data.get("sharpe_ratio", 0)
                bm_cagr = bm_data.get("cagr", 0)
                bm_alpha = bm_data.get("alpha", None)
                bm_ir = bm_data.get("information_ratio", None)
                bm_down = bm_data.get("down_capture", None)
                bm_excess_cagr = bm_data.get("excess_cagr", None)

                if bm_alpha is not None and bm_alpha < 0:
                    suggestions.append(
                        f"Alpha is {bm_alpha:.1%} vs {bm_name} — "
                        "strategy is destroying value relative to benchmark"
                    )

                if bm_ir is not None and 0 < bm_ir < 0.5:
                    suggestions.append(
                        f"Information ratio {bm_ir:.2f} vs {bm_name} — "
                        "active returns do not justify tracking error"
                    )

                if bm_down is not None and bm_down > 1.2:
                    suggestions.append(
                        f"Down capture {bm_down:.0%} vs {bm_name} — "
                        "strategy falls more than market in downturns. Add tail protection"
                    )

                if bm_excess_cagr is not None and bm_excess_cagr < 0:
                    suggestions.append(
                        f"CAGR below {bm_name} benchmark — "
                        "consider if active management is justified"
                    )
                elif bm_alpha is None and bm_cagr > m.cagr:
                    suggestions.append(
                        f"Benchmark {bm_name} CAGR ({bm_cagr:.1%}) exceeds strategy ({m.cagr:.1%}) — "
                        "simpler passive approach may outperform"
                    )

        meets_performance_bar = (
            m.sharpe_ratio >= self._config.target_sharpe_ratio
            and m.max_drawdown >= self._config.target_max_drawdown
        )
        has_enough_trades = result.trade_count >= self._config.min_trades_for_pass

        if meets_performance_bar and not has_enough_trades:
            # Never allow PASS on a thin sample, regardless of how good the ratio
            # looks — a handful of trades isn't enough to trust any Sharpe computed
            # from them.
            suggestions.append(
                f"Only {result.trade_count} trades over the period (need at least "
                f"{self._config.min_trades_for_pass}) — insufficient sample to trust "
                f"Sharpe={m.sharpe_ratio:.2f} despite meeting the PASS threshold"
            )

        if meets_performance_bar and has_enough_trades:
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

        reasoning_parts = [f"Sharpe={m.sharpe_ratio:.2f}, MaxDD={m.max_drawdown:.1%}, WinRate={m.win_rate:.0%}, CVaR={m.cvar_95:.1%}"]
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

    def _verify_strategy_code(self, strategy_code: str) -> list[str]:
        """
        Statically check strategy code for hallucinations or missing columns in AST.
        """
        import ast
        errors = []
        try:
            tree = ast.parse(strategy_code)
        except Exception as e:
            return [f"Failed to parse Python AST: {e}"]

        class ColumnAccessVisitor(ast.NodeVisitor):
            def __init__(self, df_name: str = "data"):
                self.df_name = df_name
                self.referenced_columns: set[str] = set()

            def visit_Subscript(self, node: ast.Subscript):
                if isinstance(node.value, ast.Name) and node.value.id == self.df_name:
                    if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                        self.referenced_columns.add(node.slice.value)
                    elif hasattr(node.slice, "value") and isinstance(node.slice.value, ast.Constant) and isinstance(node.slice.value.value, str):
                        self.referenced_columns.add(node.slice.value.value)
                self.generic_visit(node)

            def visit_Call(self, node: ast.Call):
                if (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == self.df_name
                    and node.func.attr == "get"
                ):
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        self.referenced_columns.add(node.args[0].value)
                self.generic_visit(node)

            def visit_Attribute(self, node: ast.Attribute):
                if isinstance(node.value, ast.Name) and node.value.id == self.df_name:
                    if node.attr != "get":
                        self.referenced_columns.add(node.attr)
                self.generic_visit(node)

        visitor = ColumnAccessVisitor()
        visitor.visit(tree)

        allowed = {"open", "high", "low", "close", "volume", "symbol", "ts", "timestamp", "bar_ts"}
        available_indicators = [i.lower() for i in getattr(self, "_indicators", [])]
        for ind in available_indicators:
            allowed.add(ind)
            if "_" in ind:
                allowed.add(ind)
                allowed.add(ind.split("_")[0])
            allowed.add(f"{ind}_14")
            allowed.add(f"{ind}_20")
            allowed.add(f"{ind}_50")

        allowed.add("session")
        allowed.add("news_cooldown")

        for col in visitor.referenced_columns:
            if col not in allowed:
                if col in ("index", "columns", "copy", "reindex", "fillna", "iloc", "loc", "dropna", "astype", "diff", "shift", "values", "pct_change", "get"):
                    continue
                errors.append(
                    f"Referenced column '{col}' is not available in the dataset. "
                    f"Available columns/indicators: {sorted(list(allowed))}. "
                    f"Please request the indicator or use available fields."
                )
        return errors

    async def _verify_weights_holding(self, run_id: str) -> list[str]:
        """
        Post-backtest check to ensure weights are held consecutively and not just single-bar spikes.
        """
        errors = []
        weights_data = await self._tools.fetch_weights(run_id)
        if not weights_data:
            return []

        tickers = [col for col in weights_data[0].keys() if col != "date"]
        if not tickers:
            return []

        for ticker in tickers:
            non_zero_runs = []
            current_run = 0
            for row in weights_data:
                val = float(row.get(ticker) or 0.0)
                if val != 0.0:
                    current_run += 1
                else:
                    if current_run > 0:
                        non_zero_runs.append(current_run)
                        current_run = 0
            if current_run > 0:
                non_zero_runs.append(current_run)

            if not non_zero_runs:
                continue

            total_runs = len(non_zero_runs)
            single_bar_runs = sum(1 for r in non_zero_runs if r == 1)
            
            if total_runs >= 3 and single_bar_runs == total_runs:
                errors.append(
                    f"Strategy has a crossover state bug: all {total_runs} trades for {ticker} "
                    "were held for exactly 1 bar. Please rewrite signal/weight generation "
                    "to hold positions rather than exiting immediately."
                )
        return errors
