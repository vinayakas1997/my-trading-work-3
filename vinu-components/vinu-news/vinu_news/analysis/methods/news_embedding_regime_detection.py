"""Method 9 — News-Embedding-Driven Regime Detection.

Spec: New-talk-/Final-implementation/01-present-considerations/32-news-embedding-regime-detection.md

Build call: **build new**, deliberately reusing this project's existing
TF-IDF vectorizer as the "embedding" step rather than adding a new
dense-embedding model. The spec itself is explicit that this method has
**no confirmed source paper** ("the original description ... did not
resolve to one specific citable paper") and that the embedding choice is
unconstrained: "a generic FinBERT-class embedding model would comfortably
fit" — i.e. any reasonable dense-vector text representation satisfies
the method as specified, FinBERT is offered as an example, not a
requirement. Loading FinBERT here would mean downloading/holding a
~400MB transformer purely to produce vectors that get immediately
collapsed into cluster centroids and cosine distances — the same
downstream classical-clustering math this project's hand-rolled TF-IDF
(`cosine_dedup/vectorize.py`) already does for `tfidf_semantic_clustering`
(method 5) and `multi_source_triangulation` (method 4). Reusing it here
keeps method 9 dependency-free and fast (this task's own testing
guidance: "keep test fixtures small ... so tests run fast"), and the
spec's own "Is it LLM-dependent?" section confirms the clustering/
shift-detection logic itself is "classical (unsupervised clustering +
statistical shift detection), not LLM-dependent at all" regardless of
which embedding is fed into it.

How it works: articles are pre-bucketed chronologically by the caller
(e.g. daily/hourly bins of a rolling window). All bucket texts are
vectorized together (so every bucket's vectors share one global
vocabulary/IDF, making cross-bucket geometry comparable), then each
bucket's centroid (mean vector) and internal dispersion (mean distance
of member vectors from their own centroid) are computed. A regime shift
is flagged at any bucket boundary where consecutive centroids' cosine
*distance* (`1 - cosine_similarity`) exceeds `shift_threshold` — the
"new cluster emerging / existing clusters splitting/merging / overall
dispersion changing" geometry-shift signal the spec describes.

Input: a rolling window of news articles, already grouped by the caller
into chronologically ordered buckets (e.g. `[[day1_texts], [day2_texts],
...]`) — not a single article, per spec.

Output: not a numeric score — a regime-shift flag/label:
`{"regime_shift": bool, "shift_boundaries": list[int], "centroid_distances":
list[float], "dispersion": list[float]}`, where `shift_boundaries[i]`
means a shift was detected between bucket `i` and bucket `i+1`.
"""

from __future__ import annotations

from vinu_news.analysis.post_enrichment.cosine_dedup.vectorize import (
    build_tfidf_vectors,
    cosine_similarity,
)
from vinu_news.analysis.post_enrichment.synonyms.normalize import normalize_text

DEFAULT_SHIFT_THRESHOLD = 0.5


def _centroid(vectors: list[dict[str, float]]) -> dict[str, float]:
    if not vectors:
        return {}
    centroid: dict[str, float] = {}
    for vec in vectors:
        for term, weight in vec.items():
            centroid[term] = centroid.get(term, 0.0) + weight
    n = len(vectors)
    return {term: weight / n for term, weight in centroid.items()}


def detect_regime_shift(
    article_buckets: list[list[str]], shift_threshold: float = DEFAULT_SHIFT_THRESHOLD
) -> dict:
    """Detect a news-embedding regime shift across chronologically ordered buckets.

    `article_buckets` is a list of buckets, each a list of raw
    headline+summary strings for that time slice, oldest bucket first.
    """
    if len(article_buckets) < 2:
        return {
            "regime_shift": False,
            "shift_boundaries": [],
            "centroid_distances": [],
            "dispersion": [0.0] * len(article_buckets),
        }

    flat_texts = [normalize_text(t) for bucket in article_buckets for t in bucket]
    all_vectors = build_tfidf_vectors(flat_texts)

    bucket_vectors: list[list[dict[str, float]]] = []
    cursor = 0
    for bucket in article_buckets:
        size = len(bucket)
        bucket_vectors.append(all_vectors[cursor:cursor + size])
        cursor += size

    centroids = [_centroid(vectors) for vectors in bucket_vectors]

    dispersion: list[float] = []
    for vectors, centroid in zip(bucket_vectors, centroids):
        if not vectors:
            dispersion.append(0.0)
            continue
        distances = [1 - cosine_similarity(v, centroid) for v in vectors]
        dispersion.append(round(sum(distances) / len(distances), 4))

    centroid_distances: list[float] = []
    shift_boundaries: list[int] = []
    for i in range(len(centroids) - 1):
        distance = 1 - cosine_similarity(centroids[i], centroids[i + 1])
        distance = round(distance, 4)
        centroid_distances.append(distance)
        if distance >= shift_threshold:
            shift_boundaries.append(i)

    return {
        "regime_shift": len(shift_boundaries) > 0,
        "shift_boundaries": shift_boundaries,
        "centroid_distances": centroid_distances,
        "dispersion": dispersion,
    }
