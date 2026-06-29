"""TF-IDF vectorization for cosine similarity clustering."""

from __future__ import annotations

import math
import re
from collections import Counter

from vinu_news.analysis.post_enrichment.cosine_dedup.settings import MIN_TOKEN_LEN

TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> list[str]:
    """Extract lowercase tokens from normalized text."""
    return [t for t in TOKEN_PATTERN.findall(text.lower()) if len(t) >= MIN_TOKEN_LEN]


def build_tfidf_vectors(texts: list[str]) -> list[dict[str, float]]:
    """
    Build TF-IDF vectors using Fincept-style formula:
    TF-IDF = (term_count / total_terms) * (ln((N+1)/(DF+1)) + 1)
    """
    tokenized = [tokenize(t) for t in texts]
    n_docs = len(texts)
    if n_docs == 0:
        return []

    df: Counter[str] = Counter()
    for tokens in tokenized:
        for term in set(tokens):
            df[term] += 1

    vectors: list[dict[str, float]] = []
    for tokens in tokenized:
        total = len(tokens) or 1
        tf = Counter(tokens)
        vec: dict[str, float] = {}
        for term, count in tf.items():
            tf_val = count / total
            idf_val = math.log((n_docs + 1) / (df[term] + 1)) + 1
            vec[term] = tf_val * idf_val
        vectors.append(vec)
    return vectors


def cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """Cosine similarity between two sparse vectors."""
    if not vec_a or not vec_b:
        return 0.0
    common = set(vec_a) & set(vec_b)
    dot = sum(vec_a[k] * vec_b[k] for k in common)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return min(1.0, dot / (norm_a * norm_b))
