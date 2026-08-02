"""Technique 1 + 2: event-study filtering + category classification.

Instead of averaging all news into one blunt correlation (what the
vinu-initial-analysis correlation angle does and gets ~0 for), filter down
to articles that produced a statistically significant abnormal return
(ar_significant, already computed per-article) and see whether that
0.4-0.7% "real signal" subset clusters by news category/priority.

Reference: RavenPack's Event Sentiment Score scores 330+ distinct event
categories separately rather than blending everything into one average.
"""

from __future__ import annotations

import pandas as pd

from common import TICKERS, load_article_meta, load_impact_events

pd.set_option("display.width", 140)


def main() -> None:
    for symbol in TICKERS:
        events = load_impact_events(symbol)
        if events.empty:
            print(f"{symbol}: no impact events found")
            continue

        total = len(events)
        sig = events[events["ar_significant"] == True]  # noqa: E712
        print(f"\n=== {symbol} ===")
        print(f"total events: {total}   significant (ar_significant=True): {len(sig)} "
              f"({100 * len(sig) / total:.2f}%)")

        if sig.empty:
            continue

        meta = load_article_meta(sig["article_id"].astype(str).tolist())
        if meta.empty:
            print("  (no article metadata joined — check article_id dtype match)")
            continue

        merged = sig.merge(meta, left_on="article_id", right_on="id", how="left")

        print("\n  significant events by category:")
        print(merged.groupby("category").size().sort_values(ascending=False).to_string())

        print("\n  significant events by priority:")
        print(merged.groupby("priority").size().sort_values(ascending=False).to_string())

        # base rate comparison: is BREAKING more likely to be significant
        # than ROUTINE? compare against the *all-events* priority mix, not
        # just the significant subset, or this is meaningless.
        all_meta = load_article_meta(events["article_id"].astype(str).tolist())
        all_merged = events.merge(all_meta, left_on="article_id", right_on="id", how="left")
        base_counts = all_merged.groupby("priority").size()
        sig_counts = merged.groupby("priority").size()
        hit_rate = (sig_counts / base_counts * 100).dropna().sort_values(ascending=False)
        print("\n  hit rate (% of events in this priority bucket that were significant):")
        print(hit_rate.round(2).to_string())


if __name__ == "__main__":
    main()
