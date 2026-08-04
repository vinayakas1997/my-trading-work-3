---
name: vader-finance-tuned-sentiment
status: candidate-not-implemented
purpose: reference note on a VADER-based sentiment engine (with a finance lexicon overlay) found in the fincept-terminal reference repo, for the 06-news-analysis-fix redesign discussion — not yet evaluated or built. Read alongside the disproven-signal finding before assuming this is worth adopting.
---

# VADER + Finance Lexicon — An Alternative Sentiment Engine

## What is it

A third sentiment-scoring engine (distinct from this project's existing
rule-based lexicon and FinBERT): VADER (Valence Aware Dictionary and
sEntiment Reasoner, a well-known rule-based sentiment tool originally
built for social media text), extended with a hand-tuned finance-specific
word lexicon, with a keyword-only fallback when the `vaderSentiment`
package isn't installed.

## How it works

1. A finance lexicon of ~25 positive words (`"surge": 3.0, "soar": 3.2,
   "breakthrough": 3.0, ...`) and ~25 negative words (`"crash": -3.5,
   "bankruptcy": -3.8, "fraud": -3.5, ...`), weighted on VADER's native
   `[-4, 4]` valence scale.
2. If `vaderSentiment` is installed: instantiate VADER's
   `SentimentIntensityAnalyzer`, then `analyzer.lexicon.update(...)` to
   merge the finance words into VADER's existing general-purpose lexicon
   (VADER already handles negation, intensifiers, punctuation-based
   emphasis — the finance words just add domain vocabulary VADER
   wouldn't otherwise know).
3. Score via `analyzer.polarity_scores(text)["compound"]`, a single
   `[-1, 1]` value; label `BULLISH`/`BEARISH`/`NEUTRAL` via a `±0.15`
   threshold on that score.
4. If `vaderSentiment` isn't installed: fall back to plain keyword
   counting (`net = pos_count - neg_count`), same integer-weighted
   lexicon, same output schema — a graceful degrade, not a different
   feature.
5. Confidence is derived from a mix of the polarity magnitude and total
   keyword-hit count — higher when more finance-specific words fired.

## Requirements

- **No LLM call** — VADER itself is a lexicon+rules engine, not a neural
  model; runs in milliseconds per article, no GPU/API cost.
- **Dependency**: `vaderSentiment` (pip package) for the primary path;
  works with zero new dependencies via the fallback if that's not wanted.
- **Formula**: VADER's own compound-score algorithm (lexicon lookup +
  negation/intensifier/punctuation heuristics) — well-documented, not
  reproduced here; the finance lexicon is just additional vocabulary fed
  into it.

## Source

`personal-important/other-reference-repos/ref-fincept-terminal/fincept-qt/scripts/news_nlp.py`
— `_get_vader()`, `_keyword_signals()`, `analyze_sentiment_batch()`.

## Notes for future reference — read this before adopting

**This does not address the actual problem already found in this
project.** The seeded fact
(`vinu-agent/vinu_agent/facts/seed.py`) is specific: both the rule-based
lexicon sentiment *and* FinBERT were tested against real AAPL/TSLA/JNJ
price moves and neither predicts direction (~50% sign-agreement, p>0.1).
VADER is a third member of the *same family* of methods (lexicon/rule- or
classifier-based sentiment polarity) — there's no reason from the
existing evidence to expect it would predict direction any better than
the two methods already disproven. It might be marginally more accurate
*as a sentiment classifier* (VADER handles negation/intensifiers better
than a flat keyword tally), but "more accurate sentiment classification"
was never the bottleneck — "sentiment doesn't predict direction" was.

Where this could still be useful: as a **third, independent opinion**
fed alongside the other two into an ensemble/voting scheme, or as a
faster/cheaper replacement for the *existing* rule-based lexicon
specifically (same cost profile, likely better-calibrated confidence
scores) — not as a new signal expected to unlock direction prediction on
its own.
