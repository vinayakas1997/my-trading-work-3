"""Method 4 — Multi-Source Triangulation as a Credibility Signal.

Spec: New-talk-/Final-implementation/01-present-considerations/04-multi-source-triangulation.md

Build call: **adapt**. The spec's reference implementation groups
articles by a crude first-50-characters headline prefix, but the spec's
own caveat says this is fragile and explicitly recommends reusing this
project's existing TF-IDF cosine-similarity grouping instead: "vinu-news
already has a better tool for this exact problem ... reuse that grouping
logic instead of porting the crude version." This project's TF-IDF
machinery lives in `vinu_news/analysis/post_enrichment/cosine_dedup/
vectorize.py` (hand-rolled `build_tfidf_vectors`/`cosine_similarity`,
same formula shape the spec itself describes) and `synonyms/normalize.py`
(financial synonym folding) — this module reuses both directly rather
than re-deriving TF-IDF or porting the prefix-matching version.

Unlike `cosine_dedup/cluster.py`'s `cluster_articles`, this module does
NOT apply the ticker/entity merge gates from `gates.py` — triangulation
is specifically about whether *independent sources* are covering the
same story, so gating on ticker/entity overlap (designed for is-this-a-
duplicate dedup, not is-this-triangulated) would be the wrong tool here;
plain cosine similarity over synonym-normalized text is what the spec
calls for.

Input: a batch of articles (each needs at least `id`, `headline`,
`summary`, `source`).

Output: a list of triangulation signals — dicts with `triangulation:
True`, fixed `severity: "medium"`, `sources` (list of confirming source
names), and `article_ids` — one entry per story confirmed by
`min_sources` or more distinct sources. Stories under that threshold
produce no entry (matches spec: "a single article alone can never
trigger this signal").

Reuses `tfidf_semantic_clustering.cluster_semantic` (method 5) for the
actual grouping step rather than duplicating the greedy-clustering loop
— both methods share the exact same "which articles in this batch are
about the same story" primitive, just consume the resulting groups
differently.
"""

from __future__ import annotations

from vinu_news.analysis.methods.tfidf_semantic_clustering import (
    DEFAULT_SIMILARITY_THRESHOLD,
    cluster_semantic,
)

MIN_SOURCES = 3


def find_triangulated_stories(
    articles: list[dict],
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    min_sources: int = MIN_SOURCES,
) -> list[dict]:
    """Greedily group articles by TF-IDF cosine similarity, then flag
    groups confirmed by >= `min_sources` distinct sources.
    """
    if not articles:
        return []

    by_id = {a["id"]: a for a in articles}
    groups = cluster_semantic(articles, similarity_threshold=similarity_threshold)

    signals: list[dict] = []
    for group_ids in groups:
        sources = sorted({by_id[aid]["source"] for aid in group_ids})
        if len(sources) >= min_sources:
            signals.append(
                {
                    "triangulation": True,
                    "severity": "medium",
                    "sources": sources,
                    "article_ids": group_ids,
                }
            )
    return signals
