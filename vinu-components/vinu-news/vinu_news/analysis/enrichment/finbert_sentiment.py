"""FinBERT-based sentiment scoring.

Why this exists: `sentiment.py`'s `score_sentiment()` is a rule-based keyword/lexicon tally (-N..+N int score).
Empirical testing (news-analysis-code/07_robustness_and_direction.py) showed that score has ZERO usable directional
value even on articles independently confirmed to have moved price (agreement with the actual direction was
consistently below a coin flip on AAPL and TSLA, and with pooled data, n=209). FinBERT (ProsusAI/finbert) is the
standard fine-tuned model for 3-way financial sentiment. This module scores headline+summary text and returns a
continuous score in [-1, 1] (P(positive) - P(negative)) plus the argmax label. It does NOT replace the rule-based
`sentiment` / `sentiment_score` columns used elsewhere.

Where the model runs: vinu-news no longer needs `torch`. When `VINU_MODEL_SERVICE_URL` is set the scoring is done by
the model-serving service (`vinu-models`); when it is unset the same code runs in-process (`vinu_infra.finbert_scoring`,
which needs torch + transformers installed). A service failure raises `ModelServiceError`; it is never turned into
neutral scores, which would be stored as if they were real.
"""

from __future__ import annotations

import logging

LOG = logging.getLogger(__name__)


def score_finbert_batch(texts: list[str], batch_size: int = 16) -> list[dict]:
    """One dict per input: {"finbert_label": "positive"|"negative"|"neutral", "finbert_score": float in [-1, 1]}.
    Empty / whitespace-only texts get a neutral 0.0 without running inference."""
    from vinu_infra import model_client

    if model_client.service_url():
        if not any(t and t.strip() for t in texts):
            return [{"finbert_label": "neutral", "finbert_score": 0.0} for _ in texts]
        from vinu_infra.pipeline_edge_recorder import record_edge

        edge = "models.finbert_score->news.backfill"
        try:
            results = model_client.score_finbert(texts, batch_size)
        except model_client.ModelServiceError as exc:
            record_edge(edge, "missing", str(exc))
            raise
        record_edge(edge, "received", f"{len(results)} text(s) scored")
        return results
    from vinu_infra.finbert_scoring import score_finbert_batch as _local

    return _local(texts, batch_size)


def score_finbert(text: str) -> dict:
    return score_finbert_batch([text])[0]
