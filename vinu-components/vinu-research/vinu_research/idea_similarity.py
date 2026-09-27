"""item #16 finding #4: `loop.py`'s hypothesis dedup used a bare
token-overlap ratio (`_match_score`) on the free-text idea string --
fragile enough that two differently-phrased versions of the same idea
could both get generated and backtested (wasted budget), or two
genuinely different ideas sharing a few common words could get merged
into one hypothesis's evidence trail (corrupted attribution).

TF-IDF cosine similarity, same algorithm `vinu-news`'s own
`analysis/post_enrichment/cosine_dedup/vectorize.py` already established
for this exact class of problem (short-text duplicate detection) --
reimplemented here rather than cross-imported, since neither service
depends on the other's package (same convention as every other
independently-reimplemented shared idiom in this monorepo). Downweights
common words and upweights distinctive ones, unlike a raw overlap ratio,
but is still just a lexical statistic -- `loop.py`'s own
`_match_existing_hypothesis` uses this as a cheap screen/fallback and
asks the LLM for the actual semantic judgment when there's enough shared
vocabulary to be worth checking (see that function's own docstring)."""

from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")
_MIN_TOKEN_LEN = 2


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_PATTERN.findall(text.lower()) if len(t) >= _MIN_TOKEN_LEN]


def build_tfidf_vectors(texts: list[str]) -> list[dict[str, float]]:
    """TF-IDF = (term_count / total_terms) * (ln((N+1)/(DF+1)) + 1)."""
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
    if not vec_a or not vec_b:
        return 0.0
    common = set(vec_a) & set(vec_b)
    dot = sum(vec_a[k] * vec_b[k] for k in common)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return min(1.0, dot / (norm_a * norm_b))
