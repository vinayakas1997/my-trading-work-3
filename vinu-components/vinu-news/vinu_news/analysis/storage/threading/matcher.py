"""Cross-batch thread matching against active story_threads."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from vinu_news.analysis.post_enrichment.cosine_dedup.gates import should_merge
from vinu_news.analysis.post_enrichment.cosine_dedup.settings import (
    LOOKBACK_HOURS,
    THREAD_MATCH_THRESHOLD,
)
from vinu_news.analysis.post_enrichment.cosine_dedup.vectorize import (
    build_tfidf_vectors,
    cosine_similarity,
)
from vinu_news.analysis.storage.models import EnrichedArticle
from vinu_news.analysis.storage.repository import NewsRepository


def find_matching_thread(
    repo: NewsRepository,
    item: EnrichedArticle,
    entities: dict[str, Any],
) -> str | None:
    """Return existing thread_id if candidate matches an active thread."""
    reference_ts = item.article.sort_ts
    since_ts = reference_ts - LOOKBACK_HOURS * 3600
    active = repo.get_active_threads(since_ts)
    if not active or not item.norm_text:
        return None

    candidate_text = item.norm_text
    thread_texts = [t.get("norm_text") or t.get("lead_headline", "") for t in active]
    all_texts = [candidate_text] + thread_texts
    vectors = build_tfidf_vectors(all_texts)
    candidate_vec = vectors[0]

    stub = EnrichedArticle(
        article=item.article,
        mentions=item.mentions,
        norm_text=item.norm_text,
    )

    best_id: str | None = None
    best_score = 0.0

    for idx, thread in enumerate(active):
        score = cosine_similarity(candidate_vec, vectors[idx + 1])
        if score < THREAD_MATCH_THRESHOLD:
            continue

        thread_entities = {}
        try:
            thread_entities = json.loads(thread.get("entities_json") or "{}")
        except json.JSONDecodeError:
            thread_entities = {}

        thread_article = deepcopy(item.article)
        dominant = thread.get("dominant_ticker")
        if dominant:
            thread_article.tickers = json.dumps([dominant])
        thread_article.entities_json = thread.get("entities_json", "{}")

        thread_stub = EnrichedArticle(
            article=thread_article,
            mentions=[],
            norm_text=thread.get("norm_text", ""),
        )

        if not should_merge(stub, thread_stub, entities, thread_entities):
            continue

        if score > best_score:
            best_score = score
            best_id = thread["thread_id"]

    return best_id
