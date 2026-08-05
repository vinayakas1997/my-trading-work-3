from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vinu_infra.debug import debug_log
from vinu_infra.llm import AsyncLlmClient as SharedAsyncLlmClient, LlmConfig
from vinu_research.angle_context import format_angle_context_lines
from vinu_research.config import ResearchConfig
from vinu_research.models import BacktestResult, CriticFeedback

LOG = logging.getLogger(__name__)

LLM_SYSTEM_PROMPT = """You are a senior quantitative risk analyst. Review the strategy's backtest metrics and the market story blocks. The rule-based system has already produced initial suggestions below. You may add ADDITIONAL suggestions that the rules may have missed.

Return JSON with exactly this schema, no markdown, no extra text:
{
  "additional_suggestions": ["suggestion 1", "suggestion 2"],
  "verdict_upgrade": null,
  "reasoning": "brief explanation of what the rules missed"
}

Only set verdict_upgrade to "PASS" or "STOP" if you are highly confident the rules are wrong. Otherwise keep it null. Be specific and implementable — mention exact indicators (ADX, ATR, RSI) and thresholds."""


def _build_risk_critic_prompt(
    user_idea: str,
    symbol: str,
    from_date: str,
    to_date: str,
    result: BacktestResult,
    rules_feedback: CriticFeedback,
    story: dict[str, Any] | None,
    catalog_entry: dict[str, Any] | None = None,
) -> str:
    m = result.metrics
    lines = [
        f"Strategy: {user_idea}",
        f"Symbol: {symbol}",
        f"Period: {from_date} → {to_date}",
        "",
        "Backtest Results:",
        f"- Sharpe: {m.sharpe_ratio:.2f}",
        f"- MaxDD: {m.max_drawdown:.1%}",
        f"- Win Rate: {m.win_rate:.0%}",
        f"- Total Return: {m.total_return:.1%}",
        f"- Sortino: {m.sortino_ratio:.2f}",
        f"- Calmar: {m.calmar_ratio:.2f}",
        f"- Trade Count: {result.trade_count}",
        "",
    ]

    if catalog_entry:
        lt = catalog_entry.get("lifetime_trial_count", 0)
        bs = catalog_entry.get("best_sharpe_ever", 0.0)
        if lt:
            lines.append("Cross-Run History:")
            lines.append(f"  Lifetime trials on {symbol}: {lt}")
            lines.append(f"  Best Sharpe ever on {symbol}: {bs:.2f}")
            lines.append("")

    lines.append("Rule-based suggestions:")
    if rules_feedback.suggestions:
        for i, s in enumerate(rules_feedback.suggestions, 1):
            lines.append(f"  {i}. {s}")
    else:
        lines.append("  (none)")
    lines.append(f"  Verdict: {rules_feedback.verdict}")
    lines.append(f"  Reasoning: {rules_feedback.reasoning}")

    if story:
        lines.append("")
        lines.append("Story Blocks:")
        dd_events = story.get("drawdown_events", [])
        lines.append(f"  Drawdown events: {len(dd_events)}")
        for dd in dd_events[:3]:
            lines.append(f"    - drop {dd.get('drop_pct', 0):.1f}%, sessions: {dd.get('sessions_involved', [])}")
        by_session = story.get("correlations", {}).get("by_session", {})
        if by_session:
            lines.append("  Session correlations:")
            for sess, data in by_session.items():
                lines.append(f"    {sess}: r={data.get('pearson', 0):.3f}, n={data.get('sample_hours', 0)}")
        anomalies = story.get("baseline_anomalies", [])
        if anomalies:
            lines.append(f"  Baseline anomalies: {len(anomalies)}")

        angles = story.get("angles") or {}
        lines.extend(format_angle_context_lines(angles))

    return "\n".join(lines)


class LlmCache:
    """Kept for backward compatibility with tests. New code uses vinu_infra.llm.cache.LlmCache."""

    def __init__(self, cache_path: str | Path, ttl_sec: int = 86400) -> None:
        self._path = Path(cache_path)
        self._ttl = ttl_sec
        self._local = threading.local()

    def _get_conn(self) -> sqlite3.Connection:
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self._path))
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS llm_cache ("
                "  cache_key TEXT PRIMARY KEY,"
                "  response_json TEXT NOT NULL,"
                "  created_at INTEGER NOT NULL"
                ")"
            )
            self._local.conn = conn
        return conn

    def get(self, cache_key: str) -> dict[str, Any] | None:
        if self._ttl <= 0:
            return None
        conn = self._get_conn()
        row = conn.execute(
            "SELECT response_json, created_at FROM llm_cache WHERE cache_key=?",
            (cache_key,),
        ).fetchone()
        if row is None:
            return None
        if time.time() - row[1] > self._ttl:
            conn.execute("DELETE FROM llm_cache WHERE cache_key=?", (cache_key,))
            conn.commit()
            return None
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return None

    def set(self, cache_key: str, data: dict[str, Any]) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO llm_cache (cache_key, response_json, created_at) VALUES (?, ?, ?)",
            (cache_key, json.dumps(data), int(time.time())),
        )
        conn.commit()

    def close(self) -> None:
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None


DIAGNOSIS_SYSTEM_PROMPT = """You are a senior quantitative analyst diagnosing why a trading strategy failed.
Analyze the strategy code, backtest results, and stock profile to identify the root cause.
Only cite specific numbers that appear in the data provided above — do not estimate or invent values that weren't given to you.

Possible root causes:
1. Wrong indicator choice for this stock's behavior
2. Wrong indicator thresholds (e.g., RSI 30/70 when RSI never hits those levels)
3. Wrong timeframe (e.g., strategy works on daily but not on hourly data)
4. Missing conditions (e.g., no volatility filter causing whipsaws)
5. Data issue (e.g., not enough data points for the indicator window)
6. Fundamentally wrong approach (e.g., mean-reversion on a trending stock)

Return JSON with this exact schema:
{
  "root_cause": "brief description of the primary root cause",
  "category": "indicator_choice | indicator_thresholds | timeframe | missing_conditions | data_issue | wrong_approach",
  "evidence": "specific data points that support this diagnosis",
  "recommendation": "what to change in the next iteration"
}"""


STOCK_CHARACTERIZATION_PROMPT = """You are a senior quant analyst characterizing a stock for strategy development.
Analyze the following stock data and determine what strategy approaches would work best.
Only cite specific numbers that appear in the data provided above — do not estimate or invent values that weren't given to you.

Return JSON with this exact schema:
{
  "volatility_category": "low | medium | high",
  "trend_strength": "weak | moderate | strong",
  "rsi_behavior": "extreme | moderate | rangebound",
  "recommended_approaches": ["momentum", "mean_reversion", "breakout", "trend_following"],
  "avoid_approaches": ["momentum", "mean_reversion", "breakout", "trend_following"],
  "reasoning": "brief explanation of the characterization"
}"""


def _build_diagnosis_prompt(
    strategy_code: str,
    sharpe: float,
    max_dd: float,
    trade_count: int,
    symbol: str,
    stock_profile: str | None = None,
) -> str:
    lines = [
        "The following trading strategy produced 0 trades. Diagnose why.",
        "",
        f"Symbol: {symbol}",
        f"Trade Count: {trade_count}",
        f"Sharpe: {sharpe:.2f}",
        f"MaxDD: {max_dd:.1%}",
        "",
        "Strategy code:",
        strategy_code,
    ]
    if stock_profile:
        lines.append("")
        lines.append("Stock Profile:")
        lines.append(stock_profile)
    return "\n".join(lines)


def _build_characterization_prompt(
    symbol: str,
    volatility: float | None,
    rsi_percentiles: dict[str, float] | None,
    ar1: float | None,
    adx: float | None,
    angle_context: dict[str, Any] | None,
) -> str:
    lines = [f"Characterize {symbol} for strategy development."]
    if volatility is not None:
        lines.append(f"Annualized Volatility: {volatility:.1%}")
    if rsi_percentiles:
        lines.append(f"RSI Distribution: P10={rsi_percentiles.get('p10', 0):.0f}, P50={rsi_percentiles.get('p50', 0):.0f}, P90={rsi_percentiles.get('p90', 0):.0f}")
    if ar1 is not None:
        lines.append(f"Auto-correlation (AR1): {ar1:.3f}")
    if adx is not None:
        lines.append(f"ADX Average: {adx:.1f}")
    if angle_context:
        tl = angle_context.get("trend_lifecycle", {})
        if tl:
            lines.append(f"Trend Lifecycle Stage: {tl.get('stage', 'unknown')}")
            lines.append(f"Trend Risk: {tl.get('risk', 'unknown')}")
    return "\n".join(lines)


REFLECTION_SYSTEM_PROMPT = """You are a senior quantitative strategist deciding whether to continue, pivot, or stop.

Your approach has failed multiple times. Review the history and decide what to do.
Only cite specific numbers that appear in the data provided above — do not estimate or invent values that weren't given to you.

Options:
1. "continue" — Keep refining the current approach (if there's still hope)
2. "pivot" — Switch to a fundamentally different strategy class
3. "stop" — This stock may not be tradeable with available indicators

If pivot, suggest a specific new approach.

Return JSON with this exact schema:
{
  "decision": "continue | pivot | stop",
  "new_approach": "description of new approach if pivoting, empty otherwise",
  "reasoning": "explanation of the decision",
  "confidence": 0.0
}"""


VALIDATION_SYSTEM_PROMPT = """You are a senior quantitative analyst validating whether a user's strategy idea is suitable for a given stock.

Analyze the stock profile and user idea. Consider:
1. Is the strategy type appropriate for this stock's behavior?
2. Are the right indicators available?
3. Is there a fundamental mismatch (e.g., mean-reversion on a trending stock)?
Only cite specific numbers that appear in the data provided above — do not estimate or invent values that weren't given to you.

Return JSON with this exact schema:
{
  "is_suitable": true,
  "warning": "description of any concerns, empty if suitable",
  "suggested_alternative": "alternative strategy type if not suitable, empty otherwise",
  "reasoning": "explanation of the assessment",
  "confidence": 0.0
}"""


RUN_SUMMARY_SYSTEM_PROMPT = """You are a senior quantitative analyst writing a short status update for a colleague who has not been following this research run.

Write 2-4 plain-English sentences: what was tried, what the result was, and what happens next (promoted, rejected, or needs another look). No jargon-only numbers without context, no markdown, no bullet points — this replaces a metrics table, it does not repeat one.
Only cite specific numbers that appear in the data provided above — do not estimate or invent values that weren't given to you.

Return JSON with exactly this schema, no markdown, no extra text:
{
  "summary": "2-4 sentence plain-English summary"
}"""


def _build_run_summary_prompt(
    user_idea: str,
    symbol: str,
    from_date: str,
    to_date: str,
    total_iterations: int,
    best_sharpe: float,
    best_max_dd: float,
    holdout_passed: bool | None,
    stress_test_passed: bool | None,
    promoted: bool,
) -> str:
    lines = [
        f"Strategy idea: {user_idea or '(none given — generator picked one)'}",
        f"Symbol: {symbol}",
        f"Period: {from_date} → {to_date}",
        f"Iterations tried: {total_iterations}",
        f"Best Sharpe found: {best_sharpe:.2f}",
        f"Best max drawdown: {best_max_dd:.1%}",
        f"Holdout passed: {holdout_passed}",
        f"Stress test passed: {stress_test_passed}",
        f"Promoted to an active strategy artifact: {promoted}",
    ]
    return "\n".join(lines)


class ResearchTraceWriter:
    def __init__(self, data_root: Path, run_id: int) -> None:
        self._path = data_root / "traces" / f"{run_id}.jsonl"
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def log_call(
        self,
        call_type: str,
        iteration: int,
        symbol: str,
        system: str,
        user: str,
        response: Any,
        latency_ms: float,
        success: bool,
        error: str | None = None,
    ) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "llm_call",
            "call_type": call_type,
            "iteration": iteration,
            "symbol": symbol,
            "system_preview": system[:200],
            "user_preview": user[:200],
            "response_summary": str(response)[:200] if response else None,
            "latency_ms": round(latency_ms, 1),
            "success": success,
            "error": error,
        }
        try:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError as exc:
            LOG.warning("Failed to write trace: %s", exc)


class ResearchLlmClient:
    def __init__(self, config: ResearchConfig) -> None:
        self._config = config
        llm_cfg = LlmConfig(
            base_url=config.llm_base_url,
            model=config.llm_model,
            api_key=config.llm_api_key,
            max_tokens=config.llm_max_tokens,
            timeout_sec=config.llm_timeout_sec,
            ttl_sec=config.llm_ttl_sec,
            data_root=str(config.data_root),
            rate_limit=10,
            rate_period_sec=60.0,
        )
        self._client = SharedAsyncLlmClient(llm_cfg, service="vinu-research")
        self._trace: ResearchTraceWriter | None = None
        self._trace_run_id: int = 0
        self._trace_symbol: str = ""
        self._trace_iteration: int = 0

    def is_configured(self) -> bool:
        return bool(self._config.llm_base_url and self._config.llm_model)

    def set_trace_context(self, run_id: int, symbol: str) -> None:
        self._trace_run_id = run_id
        self._trace_symbol = symbol
        self._trace = ResearchTraceWriter(self._config.data_root, run_id)

    async def _traced_chat(
        self,
        call_type: str,
        system: str,
        user: str,
    ) -> dict[str, Any] | None:
        start = time.perf_counter()
        result = await self._client.chat_json(system, user)
        latency_ms = (time.perf_counter() - start) * 1000
        if self._trace:
            self._trace.log_call(
                call_type=call_type,
                iteration=self._trace_iteration,
                symbol=self._trace_symbol,
                system=system,
                user=user,
                response=result,
                latency_ms=latency_ms,
                success=result is not None,
            )
        debug_log(f"{call_type}: latency={latency_ms:.0f}ms success={result is not None}", level=1)
        if result is None:
            debug_log(f"{call_type}: LLM returned None", level=1)
        debug_log(f"{call_type} system prompt:\n{system}", level=2)
        debug_log(f"{call_type} user prompt:\n{user}", level=2)
        if result is not None:
            debug_log(f"{call_type} response:\n{json.dumps(result, indent=2, default=str)}", level=2)
        return result

    async def chat_json(self, system: str, user: str) -> dict[str, Any] | None:
        return await self._traced_chat("chat_json", system, user)

    async def diagnose_failure(
        self,
        strategy_code: str,
        sharpe: float,
        max_dd: float,
        trade_count: int,
        symbol: str,
        stock_profile: str | None = None,
    ) -> dict[str, Any] | None:
        prompt = _build_diagnosis_prompt(strategy_code, sharpe, max_dd, trade_count, symbol, stock_profile)
        return await self._traced_chat("diagnose_failure", DIAGNOSIS_SYSTEM_PROMPT, prompt)

    async def suggest_pivot(
        self,
        user_idea: str,
        symbol: str,
        history_summary: str,
    ) -> dict[str, Any] | None:
        prompt = f"""Research run for {symbol}.

User idea: {user_idea}

Iteration history:
{history_summary}

Review the above and decide: continue, pivot, or stop?"""
        return await self._traced_chat("suggest_pivot", REFLECTION_SYSTEM_PROMPT, prompt)

    async def validate_idea(
        self,
        user_idea: str,
        symbol: str,
        stock_profile: str,
    ) -> dict[str, Any] | None:
        prompt = f"""Validate this strategy idea for {symbol}.

User idea: {user_idea}

Stock profile:
{stock_profile}

Is this approach suitable?"""
        return await self._traced_chat("validate_idea", VALIDATION_SYSTEM_PROMPT, prompt)

    async def summarize_run(
        self,
        user_idea: str,
        symbol: str,
        from_date: str,
        to_date: str,
        total_iterations: int,
        best_sharpe: float,
        best_max_dd: float,
        holdout_passed: bool | None,
        stress_test_passed: bool | None,
        promoted: bool,
    ) -> str:
        """Best-effort plain-English summary of a completed run — distinct
        from report_md's metrics table. Returns "" if the LLM isn't
        configured or the call fails; never raises."""
        if not self.is_configured():
            return ""
        prompt = _build_run_summary_prompt(
            user_idea, symbol, from_date, to_date, total_iterations,
            best_sharpe, best_max_dd, holdout_passed, stress_test_passed, promoted,
        )
        result = await self._traced_chat("summarize_run", RUN_SUMMARY_SYSTEM_PROMPT, prompt)
        if not result:
            return ""
        return str(result.get("summary", "")).strip()

    async def characterize_stock(
        self,
        symbol: str,
        volatility: float | None = None,
        rsi_percentiles: dict[str, float] | None = None,
        ar1: float | None = None,
        adx: float | None = None,
        angle_context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        prompt = _build_characterization_prompt(symbol, volatility, rsi_percentiles, ar1, adx, angle_context)
        return await self._traced_chat("characterize_stock", STOCK_CHARACTERIZATION_PROMPT, prompt)

    async def close(self) -> None:
        await self._client.close()
