"""Top-level news analysis pipeline orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vinu_news.analysis.enrichment.enrich import enrich_article, enrich_batch
from vinu_news.analysis.post_enrichment.post_process import post_process_batch
from vinu_news.analysis.pre_enrichment.url_dedup import dedup_urls_batch
from vinu_news.analysis.pre_enrichment.validate_raw import validate_raw_batch
from vinu_news.analysis.storage.models import EnrichedArticle


@dataclass
class ProcessResult:
    articles: list[EnrichedArticle]
    validated_count: int
    enriched_count: int
    clusters_found: int
    duplicates_dropped: int
    post_process_applied: bool
    url_dedup_dropped: int


def process_batch(
    raw_articles: list[dict[str, Any]],
    *,
    skip_post_process: bool = False,
) -> ProcessResult:
    """Validate, URL dedup, enrich, optionally post-process (NER, dedup, lead pick)."""
    validated = validate_raw_batch(raw_articles)
    url_deduped = dedup_urls_batch(validated)
    url_dedup_dropped = len(validated) - len(url_deduped)
    enriched = enrich_batch(url_deduped)

    if skip_post_process:
        return ProcessResult(
            articles=enriched,
            validated_count=len(validated),
            enriched_count=len(enriched),
            clusters_found=0,
            duplicates_dropped=0,
            post_process_applied=False,
            url_dedup_dropped=url_dedup_dropped,
        )

    post_result = post_process_batch(enriched)
    return ProcessResult(
        articles=post_result.articles,
        validated_count=len(validated),
        enriched_count=post_result.enriched_count,
        clusters_found=post_result.clusters_found,
        duplicates_dropped=post_result.duplicates_dropped,
        post_process_applied=True,
        url_dedup_dropped=url_dedup_dropped,
    )


__all__ = ["ProcessResult", "enrich_article", "enrich_batch", "process_batch"]
