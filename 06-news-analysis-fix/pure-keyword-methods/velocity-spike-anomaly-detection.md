---
name: velocity-spike-anomaly-detection
status: candidate-not-implemented
purpose: reference note on a news-volume anomaly-detection method found in the fincept-terminal reference repo, for the 06-news-analysis-fix redesign discussion — not yet evaluated or built.
---

# Velocity Spike — News-Volume Anomaly Detection

## What is it

A signal that flags when the volume of news in a given category (or for a
given ticker) is unusually high *right now* compared to its own recent
history — not what the news says, just how much of it there suddenly is.
Detects "something is happening" before any sentiment/content analysis
runs.

## How it works

1. Bucket incoming articles into a category (or ticker) and a time
   window (the reference implementation uses 1-hour buckets: "last hour"
   vs "the hour before that").
2. Compute `ratio = recent_count / max(older_count, 1)`.
3. Flag a `velocity_spike` if `ratio >= 3.0` **and** `recent >= 5` (both
   thresholds exist so a jump from 1→3 articles doesn't false-positive —
   needs real absolute volume too, not just a big ratio on tiny numbers).
4. Severity: `high` if `ratio >= 5.0`, else `medium`.

A companion mechanism generalizes this beyond a fixed "last hour vs prior
hour" comparison into a proper rolling baseline:
- Maintain a rolling 168-hour (7-day) history of hourly counts per
  category.
- `mean`/`stddev` computed from that rolling window.
- `z_score = (current_count - mean) / stddev`.
- Flag a deviation if `z_score >= 2.0` (only once `sample_size >= 24`
  hours and `stddev >= 0.5`, to avoid triggering on a nearly-constant,
  low-noise series where any blip looks huge in z-score terms).
- Severity: `critical` if `z_score >= 4`, `high` if `>= 3`, else
  `medium`.

## Requirements

- **No LLM call** — pure counting/arithmetic on already-fetched article
  metadata (`category`, `sort_ts`). Cheap, real-time-capable.
- **Formula**: `ratio = recent / max(older, 1)`; `z = (x - μ) / σ` over a
  rolling window (standard z-score, no special formula).
- State needed: a rolling per-category hourly-count history (168 points
  per category is enough for the 7-day baseline) — this project doesn't
  currently persist this anywhere; would need a small new table.

## Source

`personal-important/other-reference-repos/ref-fincept-terminal/fincept-qt/scripts/news_correlation.py`
— functions `detect_signals()` (the ratio-based version) and
`baseline_update()`/`detect_deviations()` (the z-score version).

## Notes for future reference

- This is a **volume** signal, not a content signal — complementary to,
  not a replacement for, sentiment/event-type classification. It answers
  "is this worth looking at right now," not "what does it mean."
- Directly relevant to this project's **goal 2** (cascaded news
  patterns): the existing `vinu-initial-analysis`
  `news_price_causality/impact.py`'s `aggregate_by_thread()` only
  *summarizes* a thread after the fact (mean sentiment, max price
  change). A velocity-spike signal could detect a thread *escalating* in
  real time, which the current implementation doesn't do at all.
- Untested against this project's own AAPL/TSLA/JNJ data — the
  thresholds above (`ratio >= 3.0`, `z >= 2.0`) are the reference repo's
  defaults for geopolitical/macro news, not validated for single-stock
  news volume, which may have very different baseline noise
  characteristics (a stock with sparse coverage will have much wider
  natural swings in hourly count than a rolling 7-day baseline expects).
