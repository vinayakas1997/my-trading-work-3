"""Technique 4, real version: text-similarity novelty score.

03_novelty_score.py used "first article in a thread = novel" as a free
proxy. That's weak because thread-order is really "which article
vinu-news's clustering happened to scrape first," not "which article
contains genuinely new information" — two independently-written articles
about the same event, scraped seconds apart, get arbitrarily split into
novel/rehash by that proxy even though neither is more novel than the
other content-wise.

This version does what Thomson Reuters TRNA / the FOMC-novelty paper
actually do: measure how textually similar each headline is to whatever
was published about the same ticker in the preceding lookback window.
High max-similarity to something recent = rehash (market has likely
already priced this in). Low similarity to everything recent = genuinely
new information.

Method:
  1. TF-IDF vectorize all headlines for the ticker (bag-of-words, not a
     real embedding model — no local embedding model is set up in this
     environment, and TF-IDF is a reasonable first pass: it directly
     penalizes headlines that reuse the same wording, which is exactly
     what a rehashed/syndicated story does).
  2. Walk articles in time order. For each one, compare it only against
     articles published in the preceding LOOKBACK_HOURS (not the whole
     history) — an article from 3 months ago being similar doesn't make
     today's article "not novel," only recent coverage does.
  3. novelty_score = 1 - max(cosine similarity to anything in that
     window). No prior coverage in the window => novelty_score = 1.0.
  4. Bucket into novel/rehash by a threshold and compare ar_significant
     rate + mean |price_change| the same way 03 did, so the two
     approaches are directly comparable on the same metric.
"""

from __future__ import annotations

import numpy as np

from common import TICKERS, compute_novelty as _compute_novelty_score, load_impact_events

REHASH_THRESHOLD = 0.5  # cosine similarity above this = "rehash"


def compute_novelty(df):
    if len(df) < 5:
        return df.assign(novelty_score=1.0, novelty="novel")
    df = _compute_novelty_score(df)
    df["novelty"] = np.where(df["novelty_score"] < (1 - REHASH_THRESHOLD), "rehash", "novel")
    return df


def main() -> None:
    for symbol in TICKERS:
        events = load_impact_events(symbol)
        if events.empty:
            print(f"{symbol}: no impact events found")
            continue

        scored = compute_novelty(events)
        print(f"\n=== {symbol} ===")
        counts = scored["novelty"].value_counts()
        print(f"  novel: {counts.get('novel', 0)}   rehash: {counts.get('rehash', 0)}  "
              f"(threshold: cosine sim > {REHASH_THRESHOLD} => rehash)")

        summary = scored.groupby("novelty").agg(
            n=("article_id", "count"),
            sig_rate_pct=("ar_significant", lambda s: 100 * s.mean()),
            mean_abs_change_15m=("price_change_15m", lambda s: s.abs().mean()),
            mean_abs_change_1h=("price_change_1h", lambda s: s.abs().mean()),
            mean_novelty_score=("novelty_score", "mean"),
        )
        print(summary.round(4).to_string())


if __name__ == "__main__":
    main()
