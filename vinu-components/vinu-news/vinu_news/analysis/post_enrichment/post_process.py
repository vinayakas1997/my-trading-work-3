"""Post-enrichment batch processing: NER, synonyms, dedup, lead pick."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from vinu_news.analysis.config.settings_loader import get_settings
from vinu_news.analysis.post_enrichment.cosine_dedup.cluster import cluster_articles
from vinu_news.analysis.post_enrichment.headline_cleanup import clean_headline_for_dedup
from vinu_news.analysis.post_enrichment.lead_pick.select_lead import select_leads
from vinu_news.analysis.post_enrichment.ner.extract_entities import extract_entities
from vinu_news.analysis.post_enrichment.synonyms.normalize import normalize_text
from vinu_news.analysis.storage.models import EnrichedArticle


@dataclass
class PostProcessResult:
    articles: list[EnrichedArticle]
    clusters_found: int
    duplicates_dropped: int
    enriched_count: int
    # the other reports of each cluster: same story, kept as raw rows below the lead (layer 3)
    duplicates: list[EnrichedArticle] = field(default_factory=list)


def post_process_batch(enriched: list[EnrichedArticle]) -> PostProcessResult:
    """Run NER, synonym normalization, cosine clustering, and lead selection."""
    if not enriched:
        return PostProcessResult(
            articles=[],
            clusters_found=0,
            duplicates_dropped=0,
            enriched_count=0,
        )

    use_cleanup = get_settings().threads.headline_cleanup
    normalized_texts: list[str] = []
    entities_list: list[dict] = []

    for item in enriched:
        a = item.article
        entities = extract_entities(a.headline, a.summary)
        a.entities_json = json.dumps(entities)
        entities_list.append(entities)

        headline_for_dedup = (
            clean_headline_for_dedup(a.headline) if use_cleanup else a.headline
        )
        norm = normalize_text(f"{headline_for_dedup} {a.summary}")
        item.norm_text = norm
        normalized_texts.append(norm)

    clusters = cluster_articles(enriched, normalized_texts, entities_list)
    leads = select_leads(clusters)

    lead_ids = {id(l) for l in leads}
    duplicates = [m for g in clusters for m in g.members if id(m) not in lead_ids]
    for m in duplicates:
        m.article.is_lead = 0
    duplicates_dropped = len(enriched) - len(leads)
    return PostProcessResult(
        articles=leads,
        duplicates=duplicates,
        clusters_found=len(clusters),
        duplicates_dropped=duplicates_dropped,
        enriched_count=len(enriched),
    )
