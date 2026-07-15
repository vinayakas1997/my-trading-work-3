from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from vinu_lib.client import ResilientClient
from vinu_lib.rate_limit import TokenBucket
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

    return "\n".join(lines)


class LlmCache:
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
        cache_path = config.llm_cache_path or str(config.data_root / "llm_cache.db")
        
        provider = self._resolve_provider(config.llm_model, config.llm_base_url)
        from vinu_research.llm_capabilities.client import ChatLLM
        self._chat_llm = ChatLLM(
            provider=provider,
            model=config.llm_model,
            base_url=config.llm_base_url,
            api_key=config.llm_api_key,
        )

        self._http = ResilientClient(
            config.llm_base_url.rstrip("/"),
            "llm",
            timeout=config.llm_timeout_sec,
            max_retries=2,
            circuit_breaker_threshold=3,
            allow_local=True,
            headers=self._chat_llm.get_headers(),
        )
        self._cache = LlmCache(cache_path, ttl_sec=config.llm_ttl_sec)
        self._limiter = TokenBucket(rate=10, per=60)

    @staticmethod
    def _resolve_provider(model: str, base_url: str) -> str:
        m = model.lower()
        url = base_url.lower()
        if "deepseek" in m or "deepseek" in url:
            return "deepseek"
        if "openai" in m or "openai" in url:
            return "openai"
        if "anthropic" in m or "claude" in m or "anthropic" in url:
            return "anthropic"
        if "gemini" in m or "gemini" in url:
            return "gemini"
        if "mistral" in m or "mistral" in url:
            return "mistral"
        if "groq" in m or "groq" in url:
            return "groq"
        if "together" in m or "together" in url:
            return "together"
        if "perplexity" in m or "perplexity" in url:
            return "perplexity"
        if "cohere" in m or "cohere" in url:
            return "cohere"
        if "qwen" in m or "qwen" in url:
            return "qwen"
        if "ollama" in m or "ollama" in url or "11434" in url:
            return "ollama"
        return "ollama"

    def is_configured(self) -> bool:
        return bool(self._config.llm_base_url and self._config.llm_model)

    async def chat_json(self, system: str, user: str) -> dict[str, Any] | None:
        cache_key = hashlib.md5((system + user).encode()).hexdigest()
        if self._config.llm_ttl_sec > 0:
            cached = self._cache.get(cache_key)
            if cached is not None:
                LOG.debug("LLM cache hit for %s", cache_key[:8])
                return cached

        await self._limiter.wait_async()
        
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        
        payload = self._chat_llm.build_request(
            messages=messages,
            temperature=0.2,
            max_tokens=self._config.llm_max_tokens,
        )

        data = await self._http.post("/chat/completions", json=payload)
        if data is None:
            LOG.warning("LLM returned no response (circuit open or timeout)")
            return None

        try:
            normalized = self._chat_llm.normalize_response(data)
            content = normalized.get("content", "")
        except Exception as e:
            LOG.warning("LLM response missing expected fields: %s", e)
            return None

        parsed = self._parse_json(content)
        if parsed is not None and self._config.llm_ttl_sec > 0:
            self._cache.set(cache_key, parsed)
        return parsed

    async def close(self) -> None:
        await self._http.close()
        self._cache.close()

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any] | None:
        content = content.strip()
        if content.startswith("```"):
            end = content.find("```", 3)
            if end != -1:
                content = content[content.index("\n", 3) + 1 : end].strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            LOG.warning("Failed to parse LLM response as JSON: %s", e)
            return None
