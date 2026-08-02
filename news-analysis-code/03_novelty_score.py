"""Technique 4: novelty scoring via thread_id.

Real systems (Thomson Reuters TRNA) score novelty separately from
sentiment: is this genuinely new information, or a rehash of a story
already priced in? We don't have a real NLP novelty score, but the
existing `thread_id` clustering (vinu-news groups related articles into
story threads) gives a cheap proxy: the FIRST article in a thread is
"novel", every later article covering the same thread is a "rehash".

Hypothesis: novel (first-in-thread) articles should show a bigger and/or
more-often-significant price reaction than rehash articles, since the
rehash articles report information the market has already absorbed.
"""

from __future__ import annotations

import pandas as pd

from common import TICKERS, load_impact_events


def main() -> None:
    for symbol in TICKERS:
        events = load_impact_events(symbol)
        if events.empty or "thread_id" not in events.columns:
            print(f"{symbol}: no impact events / no thread_id column")
            continue

        events = events.dropna(subset=["thread_id", "ts"]).copy()
        events = events.sort_values(["thread_id", "ts"])
        events["rank_in_thread"] = events.groupby("thread_id").cumcount()
        events["novelty"] = events["rank_in_thread"].apply(lambda r: "novel" if r == 0 else "rehash")

        print(f"\n=== {symbol} ===")
        counts = events["novelty"].value_counts()
        print(f"  novel (first-in-thread): {counts.get('novel', 0)}   "
              f"rehash (later-in-thread): {counts.get('rehash', 0)}")

        summary = events.groupby("novelty").agg(
            n=("article_id", "count"),
            sig_rate_pct=("ar_significant", lambda s: 100 * s.mean()),
            mean_abs_change_15m=("price_change_15m", lambda s: s.abs().mean()),
            mean_abs_change_1h=("price_change_1h", lambda s: s.abs().mean()),
        )
        print(summary.round(4).to_string())


if __name__ == "__main__":
    main()
