"""Greedy cosine-similarity clustering with optional ticker/NER gates."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from vinu_news.analysis.post_enrichment.cosine_dedup.gates import should_merge
from vinu_news.analysis.post_enrichment.cosine_dedup.settings import SIMILARITY_THRESHOLD
from vinu_news.analysis.post_enrichment.cosine_dedup.vectorize import (
    build_tfidf_vectors,
    cosine_similarity,
)
from vinu_news.analysis.storage.models import EnrichedArticle


@dataclass
class ClusterGroup:
    cluster_id: str
    members: list[EnrichedArticle]


def _cluster_id(member_ids: list[str]) -> str:
    key = "|".join(sorted(member_ids))
    return hashlib.sha256(key.encode()).hexdigest()[:32]


def cluster_articles(
    articles: list[EnrichedArticle],
    normalized_texts: list[str],
    entities_list: list[dict[str, Any]] | None = None,
) -> list[ClusterGroup]:
    """Group articles with cosine similarity >= threshold (greedy)."""
    if not articles:
        return []

    if entities_list is None:
        entities_list = [a.article.entities() for a in articles]

    vectors = build_tfidf_vectors(normalized_texts)
    clusters: list[list[int]] = []

    for i in range(len(articles)):
        assigned = False
        for cluster in clusters:
            if any(
                cosine_similarity(vectors[i], vectors[j]) >= SIMILARITY_THRESHOLD
                and should_merge(
                    articles[i], articles[j], entities_list[i], entities_list[j]
                )
                for j in cluster
            ):
                cluster.append(i)
                assigned = True
                break
        if not assigned:
            clusters.append([i])

    groups: list[ClusterGroup] = []
    for indices in clusters:
        members = [articles[i] for i in indices]
        cid = _cluster_id([m.article.id for m in members])
        for member in members:
            member.article.cluster_id = cid
        groups.append(ClusterGroup(cluster_id=cid, members=members))
    return groups
