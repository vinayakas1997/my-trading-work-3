"""Method 6 — VADER + Finance Lexicon Sentiment.

Spec: New-talk-/Final-implementation/01-present-considerations/06-vader-finance-tuned-sentiment.md

Build call: **adapt**, not build-new. `vinu_news/analysis/enrichment/
sentiment.py`'s `score_sentiment()` already *is* this method's fallback
path almost exactly: a hand-weighted positive/negative word lexicon
(`POSITIVE_WORDS`/`NEGATIVE_WORDS`, -3..+3 int weights) plus a
finance-specific multi-word phrase lexicon (`FINANCIAL_LEXICON`) layered
on top — the module's own docstring self-identifies it as "Fincept
Section 6D", the same reference-repo lineage this spec cites. The spec's
own fallback path (used "if vaderSentiment isn't installed") is
word-count-based net scoring with the "same integer-weighted lexicon,
same output schema" — which is exactly what `score_sentiment` already
does. This project has no `vaderSentiment` pip dependency and none is
added here: per the spec's own "Notes for future reference," VADER
would be "a third member of the *same family* of methods" as the two
already-tested-and-disproven sentiment scorers (rule-based lexicon,
FinBERT) with "no reason from the existing evidence to expect it would
predict direction any better" — so the real VADER package buys no new
directional signal here, only a different lexicon engine. Given that,
adapting the existing (already-in-production, already-tested) lexicon
scorer to VADER's *output shape* is the right-sized amount of work:
zero new dependency, reuses the exact fallback algorithm the spec itself
describes.

What's adapted (not already present in `sentiment.py`): the spec's
specific output shape — a compound float normalized to `[-1, 1]`
(VADER's own normalization formula, `x / sqrt(x*x + alpha)` with
`alpha=15`, reused here to convert `score_sentiment`'s unbounded integer
net score into VADER's characteristic bounded range), a label via a
`+/-0.15` threshold on that compound value (not `score_sentiment`'s own
`>=1`/`<=-1` integer threshold), and a confidence score blending
polarity magnitude with total keyword-hit count.

Input: a single article's text (headline + summary).

Output: `{"compound": float in [-1, 1], "sentiment": "BULLISH"|"BEARISH"|
"NEUTRAL", "confidence": float in [0, 1]}`.
"""

from __future__ import annotations

import math

from vinu_news.analysis.enrichment.sentiment import score_sentiment

# VADER's own compound-score normalization constant.
VADER_ALPHA = 15
LABEL_THRESHOLD = 0.15


def score_vader_finance(text: str) -> dict:
    """Score text using the existing finance lexicon, in VADER's output shape."""
    base = score_sentiment(text)
    net = base["sentiment_score"]
    pos = base["positive_total"]
    neg = base["negative_total"]

    compound = net / math.sqrt(net * net + VADER_ALPHA)
    compound = max(-1.0, min(1.0, compound))

    if compound >= LABEL_THRESHOLD:
        label = "BULLISH"
    elif compound <= -LABEL_THRESHOLD:
        label = "BEARISH"
    else:
        label = "NEUTRAL"

    hits = pos + neg
    confidence = 0.5 * abs(compound) + 0.5 * min(1.0, hits / 10)

    return {
        "compound": round(compound, 4),
        "sentiment": label,
        "confidence": round(confidence, 4),
    }
