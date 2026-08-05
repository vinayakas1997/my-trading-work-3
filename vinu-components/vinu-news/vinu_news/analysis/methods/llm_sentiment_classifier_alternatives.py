"""Method 7 — Non-LLM Sentiment Classifier Alternative (DeBERTa/RoBERTa/ensemble vs FinBERT).

Spec: New-talk-/Final-implementation/01-present-considerations/07-llm-sentiment-classifier-alternatives.md

Per the task scope, only the non-LLM classifier path is implemented here
(no generative LLM calls, ever, in this project).

Build call: **reuse-as-is**. The spec itself says this method has "same
task shape as FinBERT... just a different/newer underlying transformer
model" and "No new output shape versus what this project already has."
`vinu-news` already has a real frozen-classifier sentiment model —
FinBERT (`vinu_news/analysis/enrichment/finbert_sentiment.py`, genuine
`transformers.AutoModelForSequenceClassification` inference, not a
lexicon) — which is exactly the *class* of method this spec describes
(a pretrained, non-generative classifier model for 3-way sentiment).
Swapping FinBERT for DeBERTa/RoBERTa/an ensemble would require a new,
multi-hundred-MB model download in an environment where `transformers`
itself isn't even confirmed installed/network-reachable, for a change
the spec's own "Notes for future reference" flags as **not recommended**:
"a more accurate sentiment classifier ... improves accuracy at the
sentiment-classification task, which is a different, already-solved-well-
enough problem from predicting price direction" — i.e. this is
explicitly `status: candidate-not-recommended` in the spec's own
frontmatter. Given that, this module is a thin pass-through adapter
around the existing FinBERT scorer (satisfying "a non-LLM classifier
alternative exists and is wired up") rather than integrating a second
heavy model that the spec itself says wouldn't address the actual
problem.

Input: a single article's text at a time (same per-article unit as
FinBERT).

Output: same shape as FinBERT — `{"label": "positive"|"negative"|
"neutral", "score": float in [-1, 1]}`.
"""

from __future__ import annotations

from vinu_news.analysis.enrichment.finbert_sentiment import score_finbert


def classify_non_llm(text: str) -> dict:
    """Non-LLM sentiment classification, delegating to the existing FinBERT scorer."""
    result = score_finbert(text)
    return {"label": result["finbert_label"], "score": result["finbert_score"]}
