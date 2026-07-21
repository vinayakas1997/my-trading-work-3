from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from vinu_lib.llm import AsyncLlmClient as SharedAsyncLlmClient, LlmConfig
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
        "Rule-based suggestions:",
    ]
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
    """Kept for backward compatibility with tests. New code uses vinu_lib.llm.cache.LlmCache."""

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

    def is_configured(self) -> bool:
        return bool(self._config.llm_base_url and self._config.llm_model)

    async def chat_json(self, system: str, user: str) -> dict[str, Any] | None:
        return await self._client.chat_json(system, user)

    async def close(self) -> None:
        await self._client.close()
