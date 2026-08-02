"""Technique 3: shrink the reaction window from hours to minutes.

The vinu-initial-analysis correlation angle buckets news+returns into
1-HOUR windows before correlating. Real news-trading systems react in
15-30 minutes (arXiv 1807.06824). The per-article impact rows already
carry price_change_5m/15m/30m/1h/1d — this script checks whether the
signal is actually there at a faster horizon than the hourly angle looks
at, using Pearson correlation between sentiment_score and each horizon's
price change, on the full population and on the ar_significant subset.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import pearsonr

from common import TICKERS, load_impact_events

HORIZONS = ["price_change_5m", "price_change_15m", "price_change_30m", "price_change_1h", "price_change_1d"]


def corr_report(df, label: str) -> None:
    print(f"  [{label}] n={len(df)}")
    for h in HORIZONS:
        sub = df[["sentiment_score", h]].dropna()
        if len(sub) < 5:
            print(f"    {h:20s}  n too small ({len(sub)})")
            continue
        r, p = pearsonr(sub["sentiment_score"], sub[h])
        flag = "  <-- significant" if p < 0.05 else ""
        print(f"    {h:20s}  r={r:+.4f}  p={p:.4f}  n={len(sub)}{flag}")


def main() -> None:
    for symbol in TICKERS:
        events = load_impact_events(symbol)
        if events.empty:
            print(f"{symbol}: no impact events found")
            continue
        print(f"\n=== {symbol} ===")
        corr_report(events, "all events")
        sig = events[events["ar_significant"] == True]  # noqa: E712
        if not sig.empty:
            corr_report(sig, "ar_significant only")


if __name__ == "__main__":
    main()
