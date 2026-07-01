"""On-demand LLM article analysis (TASK-N01)."""

from __future__ import annotations

from typing import Any

from vinu_news.analysis.llm.cache import get_cached_analysis, save_analysis
from vinu_news.analysis.llm.client import LlmClient, LlmClientError
from vinu_news.analysis.llm.prompts import ANALYSIS_SYSTEM, ANALYSIS_USER_TEMPLATE
from vinu_news.analysis.storage.repository import NewsRepository, normalize_link
from vinu_news.config import VinuConfig, load_config


def _normalize_analysis(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "sentiment_score": float(raw.get("sentiment_score", 0.0)),
        "confidence": int(raw.get("confidence", 0)),
        "risk_flags": list(raw.get("risk_flags") or []),
        "summary": str(raw.get("summary", "")),
    }


def analyze_article(
    repo: NewsRepository,
    url_or_id: str,
    *,
    config: VinuConfig | None = None,
    client: LlmClient | None = None,
) -> dict[str, Any]:
    cfg = config or load_config()
    article = _resolve_article(repo, url_or_id)
    if article is None:
        raise ValueError("Article not found")
    url = normalize_link(article["link"]) or article["link"]
    cached = get_cached_analysis(repo.conn, url, ttl_sec=cfg.llm_ttl_sec)
    if cached is not None:
        return {"url": url, "cached": True, "analysis": cached}

    llm = client or LlmClient(cfg)
    prompt = ANALYSIS_USER_TEMPLATE.format(
        headline=article["headline"],
        summary=article.get("summary", ""),
        url=url,
    )
    raw = llm.chat_json(ANALYSIS_SYSTEM, prompt)
    analysis = _normalize_analysis(raw)
    save_analysis(repo.conn, url, analysis)
    return {"url": url, "cached": False, "analysis": analysis}


def _resolve_article(repo: NewsRepository, url_or_id: str) -> dict[str, Any] | None:
    key = url_or_id.strip()
    row = repo.conn.execute(
        "SELECT * FROM articles WHERE id = ? OR link = ? LIMIT 1",
        (key, key),
    ).fetchone()
    if row:
        return dict(row)
    norm = normalize_link(key)
    if norm:
        row = repo.conn.execute(
            "SELECT * FROM articles WHERE link = ? LIMIT 1",
            (norm,),
        ).fetchone()
        if row:
            return dict(row)
    return None
