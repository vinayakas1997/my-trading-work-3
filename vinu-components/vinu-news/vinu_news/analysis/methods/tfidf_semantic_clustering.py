"""Method 5 — TF-IDF Semantic Clustering (grouping same-story articles without ML).

Spec: New-talk-/Final-implementation/01-present-considerations/05-tfidf-semantic-clustering.md

Build call: **adapt** (nearly reuse-as-is). Everything the spec asks for
already exists in this codebase's `cosine_dedup` package:
- hand-rolled TF-IDF (`vectorize.build_tfidf_vectors`) using the exact
  same formula shape the spec describes (`tf * idf`,
  `idf = log((N+1)/(df+1)) + 1`) — no sklearn dependency, matching the
  spec's own "no dependency beyond stdlib" requirement.
- pairwise cosine similarity (`vectorize.cosine_similarity`).
- the spec's "one genuinely new, worth-porting idea", the
  synonym-normalization dictionary (`"fed"/"federal"/"reserve" ->
  federal_reserve`, `"rates"/"rate" -> interest_rate`, etc.), already
  exists as `synonyms/synonym_map.py` + `synonyms/normalize.py`.
- the similarity threshold (`0.25`) already configured in
  `analysis.yaml`'s `dedup.similarity_threshold` matches the spec's
  tuned reference-repo constant exactly.

The one thing NOT reused is `cosine_dedup/cluster.py`'s
`cluster_articles`, because that function's purpose is different: it
requires `EnrichedArticle` objects and applies ticker/entity merge gates
(`gates.py`) tuned for *duplicate detection*, and returns clusters in
processing order. This spec asks for plain "which articles in this whole
batch are similar to each other" clustering with no gating, sorted
largest-cluster-first — this module is a thin wrapper around the shared
`vectorize`/`normalize_text` primitives doing exactly that, per the
spec's own instruction to "share a vectorizer/similarity function rather
than separate code paths."

Input: a batch of articles (`id`, `headline`, `summary`) — clustering
only makes sense over a set.

Output: a list of clusters (each a list of article IDs), sorted by
cluster size descending.
"""

from __future__ import annotations

from vinu_news.analysis.post_enrichment.cosine_dedup.vectorize import (
    build_tfidf_vectors,
    cosine_similarity,
)
from vinu_news.analysis.post_enrichment.synonyms.normalize import normalize_text

DEFAULT_SIMILARITY_THRESHOLD = 0.25


def cluster_semantic(
    articles: list[dict], similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
) -> list[list[str]]:
    """Greedy single-pass TF-IDF cosine clustering over a batch of articles.

    Returns clusters (lists of article IDs), largest first.
    """
    if not articles:
        return []

    texts = [normalize_text(f"{a['headline']} {a.get('summary', '')}") for a in articles]
    vectors = build_tfidf_vectors(texts)

    groups: list[list[int]] = []
    for i in range(len(articles)):
        assigned = False
        for group in groups:
            if any(cosine_similarity(vectors[i], vectors[j]) >= similarity_threshold for j in group):
                group.append(i)
                assigned = True
                break
        if not assigned:
            groups.append([i])

    groups.sort(key=len, reverse=True)
    return [[articles[i]["id"] for i in group] for group in groups]
