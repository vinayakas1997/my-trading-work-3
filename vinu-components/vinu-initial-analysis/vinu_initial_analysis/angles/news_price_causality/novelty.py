"""Text-similarity novelty score for news articles.

WHAT THIS IS FOR (read this before touching it):
  A crude "first article in a thread = novel" proxy is wrong: two
  independent articles about the same event, scraped seconds apart by
  different providers, land in different threads and get arbitrarily
  split into novel/rehash even though neither is more novel than the
  other content-wise. This measures actual textual similarity instead.

  novelty_score is a float in [0, 1]: 1.0 = nothing like it appeared for
  this ticker in the lookback window (genuinely new information, market
  hasn't priced it in yet). Close to 0.0 = near-duplicate of something
  already published recently (rehash/syndication, market has likely
  already reacted). It's one of the pre-event features fed into the
  significance classifier in significance_model.py — see that module's
  docstring for how the two combine.

METHOD (matches the validated approach in
  news-analysis-code/04_real_novelty_score.py — do not let this module
  drift from that one without re-validating; that script is the record of
  why this design was chosen over simpler alternatives):
  1. TF-IDF vectorize all headlines for the ticker's article set (bag-of-
     words; no local embedding model is available in this environment).
  2. Walk articles in time order. For each one, compare it only against
     articles published in the preceding `lookback_seconds` — an article
     from 3 months ago being similar doesn't make today's article "not
     novel," only recent coverage does.
  3. novelty_score = 1 - max(cosine similarity to anything in that
     window). No prior coverage in the window => novelty_score = 1.0.

CAVEAT: the TF-IDF vocabulary/IDF weights are fit once on the whole
  article batch for this run (including articles later in time than the
  one being scored). This is a mild look-ahead in the *vocabulary* only —
  the actual similarity comparison for each article still only looks
  backward in time, which is what matters for "was this known already."
  Acceptable for batch/backfill runs; would need a fixed/pre-fit
  vectorizer if this angle is ever changed to score one brand-new article
  at a time against a frozen vocabulary.
"""

from __future__ import annotations

from collections import deque

import numpy as np


def compute_novelty_scores(
    articles: list[dict],
    lookback_seconds: int = 3 * 24 * 3600,
) -> dict[str, float]:
    """Returns {article_id: novelty_score} for every article that has a
    headline and timestamp. Articles missing either are omitted — callers
    should default to 1.0 (treat as novel) for any id not in the result.
    """
    usable = [
        a for a in articles
        if a.get("headline") and a.get("sort_ts", a.get("ts")) and a.get("id")
    ]
    if len(usable) < 5:
        return {a["id"]: 1.0 for a in usable}

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    usable.sort(key=lambda a: a.get("sort_ts", a.get("ts", 0)))
    headlines = [str(a["headline"]) for a in usable]

    vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
    matrix = vectorizer.fit_transform(headlines)

    scores: dict[str, float] = {}
    window: deque[tuple[int, int]] = deque()  # (ts, row_index)

    for i, article in enumerate(usable):
        ts_i = article.get("sort_ts", article.get("ts", 0))
        while window and ts_i - window[0][0] > lookback_seconds:
            window.popleft()
        if window:
            idxs = [idx for _, idx in window]
            sims = cosine_similarity(matrix[i], matrix[idxs]).flatten()
            scores[article["id"]] = float(1.0 - sims.max())
        else:
            scores[article["id"]] = 1.0
        window.append((ts_i, i))

    return scores
