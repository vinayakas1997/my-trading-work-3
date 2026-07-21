# DA-2 🔵 Sentiment Scores Are Integer by Design (False Positive)

**Component:** `vinu-news`
**Files Investigated:** `analysis/enrichment/sentiment.py`, `analysis/storage/schema.sql`, `analysis/enrichment/impact.py`, `analysis/storage/models.py`

## Investigation

The original audit claimed `sentiment_score` floats are truncated to 0 by `INTEGER NOT NULL` in schema.sql. This is incorrect.

## Root Cause of Investigation

The audit assumed sentiment scores are floats in [-1.0, 1.0], but the rule-based `score_sentiment()` function produces unbounded integers via `net = pos - neg` (keyword weights ±1/±2/±3). SQLite INTEGER has dynamic type affinity and stores arbitrary integers without truncation. Tests confirm scores like 4 round-trip correctly.

## Verdict

**False positive.** No data corruption exists. The INTEGER column is appropriate for rule-based integer scores. The separate LLM sentiment score (float -1.0 to +1.0) is stored in `news_analysis.analysis_json`, not in `articles.sentiment_score`.

## Files Changed

None — no code changes needed.
