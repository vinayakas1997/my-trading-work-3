"""Layer 4 of the news plan: facts about a story, computed once when the story is first seen. Facts, not verdicts.

For each story: the ticker it is mainly about, the other tickers it mentions (with how strongly), the entities and key words,
an event tag, and the sentiment as a number with the method that produced it. The event tag rules and the key-word list are
proposals (a first, readable rule set), kept in one place so they can be tuned and re-applied to everything stored: the
rebuild at the bottom recomputes every story from its lead article.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from vinu_news.analysis.storage.models import ArticleRecord, EnrichedArticle

# first match wins, in this order
EVENT_RULES: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (tag, re.compile(pattern, re.I))
    for tag, pattern in (
        ("fda", r"\bfda\b|clinical trial|phase [123]\b|drug approval|\bpdufa\b"),
        ("m_and_a", r"\bacquir\w*|\bacquisition\b|\bmerger\b|\btakeover\b|\bbuyout\b|\bto buy\b|\bdeal to\b"),
        ("earnings", r"\bearnings\b|\beps\b|quarterly results|\bq[1-4]\b.*\b(results|revenue|profit)\b|revenue (beat|miss)|\bprofit\b"),
        ("guidance", r"\bguidance\b|\boutlook\b|\bforecast\b|raises? (its )?(forecast|view)|cuts? (its )?(forecast|view)"),
        ("analyst", r"\bupgrade[sd]?\b|\bdowngrade[sd]?\b|price target|initiates? coverage|\banalyst\w*\b"),
        ("capital_return", r"\bdividend\b|\bbuyback\b|\brepurchase\b|stock split"),
        ("regulatory_legal", r"\blawsuit\b|\bsues?\b|\bsued\b|\bsettlement\b|\bantitrust\b|\binvestigation\b|\bprobe\b|\bsubpoena\b|\bfined?\b|\bsec\b"),
        ("leadership", r"\bceo\b|\bcfo\b|\bresigns?\b|\bappoints?\b|steps? down|\bexecutive\b"),
        ("macro", r"\bfed\b|\binflation\b|\bcpi\b|rate (cut|hike)|jobs report|\btariffs?\b|\bgdp\b"),
        ("product", r"\blaunch\w*\b|\bunveils?\b|new product|\bannounces? new\b|\brelease[sd]?\b"),
    )
)

_STOP = frozenset(
    "the a an and or of to in on for with as at by from is are was were be been it its this that these those has have had "
    "will would could should may might can not no new more less than over after before into out up down about says said "
    "say stock stocks shares share company inc corp ltd co amid vs via per".split()
)
_WORD = re.compile(r"[a-z][a-z0-9&\-]{2,}")


def event_tag(text: str) -> str:
    for tag, pattern in EVENT_RULES:
        if pattern.search(text or ""):
            return tag
    return "other"


def keywords(text: str, limit: int = 8) -> list[str]:
    counts = Counter(w for w in _WORD.findall((text or "").lower()) if w not in _STOP)
    first_seen = {w: i for i, w in enumerate(dict.fromkeys(_WORD.findall((text or "").lower())))}
    ranked = sorted(counts, key=lambda w: (-counts[w], first_seen.get(w, 0)))
    return ranked[:limit]


def _mentions(item: EnrichedArticle) -> tuple[str | None, list[dict[str, Any]]]:
    primary: str | None = None
    others: list[dict[str, Any]] = []
    for m in sorted(item.mentions, key=lambda m: -m.dominance):
        if m.is_primary and primary is None:
            primary = m.ticker
        else:
            others.append({"ticker": m.ticker, "dominance": m.dominance})
    if primary is None and others:
        primary = others.pop(0)["ticker"]
    return primary, others


def compute_facts(item: EnrichedArticle) -> dict[str, Any]:
    a: ArticleRecord = item.article
    primary, others = _mentions(item)
    text = f"{a.headline}. {a.summary}"
    # sentiment as a number, never a label: FinBERT when it has scored the lead, else the rule-based score
    if a.finbert_score is not None:
        sentiment_score, method = float(a.finbert_score), "finbert"
    else:
        sentiment_score, method = float(a.sentiment_score), "rule_based"
    return {
        "primary_ticker": primary,
        "other_tickers_json": json.dumps(others),
        "entities_json": a.entities_json or "{}",
        "keywords_json": json.dumps(keywords(text)),
        "event_tag": event_tag(text),
        "sentiment_score": sentiment_score,
        "sentiment_method": method,
    }


def store_facts(conn: Any, thread_id: str, facts: dict[str, Any], now: int) -> None:
    conn.execute(
        """
        INSERT INTO story_facts (story_id, primary_ticker, other_tickers_json, entities_json, keywords_json, event_tag,
                                 sentiment_score, sentiment_method, computed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(story_id) DO UPDATE SET
            primary_ticker = excluded.primary_ticker, other_tickers_json = excluded.other_tickers_json,
            entities_json = excluded.entities_json, keywords_json = excluded.keywords_json,
            event_tag = excluded.event_tag, sentiment_score = excluded.sentiment_score,
            sentiment_method = excluded.sentiment_method, computed_at = excluded.computed_at
        """,
        (thread_id, facts["primary_ticker"], facts["other_tickers_json"], facts["entities_json"], facts["keywords_json"],
         facts["event_tag"], facts["sentiment_score"], facts["sentiment_method"], now),
    )


def refresh_sentiment_from_finbert(conn: Any, article_id: str, score: float) -> None:
    """When FinBERT scores a story's lead article later, the story's number follows it (and says which method made it)."""
    row = conn.execute("SELECT thread_id, is_lead FROM articles WHERE id = ?", (article_id,)).fetchone()
    if row and row["thread_id"] and row["is_lead"]:
        conn.execute(
            "UPDATE story_facts SET sentiment_score = ?, sentiment_method = 'finbert' WHERE story_id = ?",
            (float(score), row["thread_id"]),
        )
        conn.execute(
            "UPDATE ticker_news SET sentiment_score = ?, sentiment_method = 'finbert' WHERE story_id = ?",
            (float(score), row["thread_id"]),
        )
