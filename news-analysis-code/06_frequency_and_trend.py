"""Plain-language picture: how often does news come out, and how often
does it actually move the price, over the 4.5-year window (2022-01 to
2026-06)? No p-values here — just counts, per-year trend, and the
average gap in days between price-moving news events.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from common import TICKERS, load_impact_events

pd.set_option("display.width", 140)


def main() -> None:
    for symbol in TICKERS:
        events = load_impact_events(symbol)
        if events.empty:
            print(f"{symbol}: no data")
            continue

        events = events.dropna(subset=["ts"]).copy()
        events["dt"] = pd.to_datetime(events["ts"], unit="s", utc=True)
        events["year"] = events["dt"].dt.year

        total_days = (events["dt"].max() - events["dt"].min()).days
        total_years = total_days / 365.25
        total_articles = len(events)
        sig = events[events["ar_significant"] == True].sort_values("dt")  # noqa: E712
        total_sig = len(sig)

        print(f"\n=== {symbol} ===")
        print(f"  window: {events['dt'].min().date()} -> {events['dt'].max().date()}  "
              f"({total_days} days, ~{total_years:.1f} years)")
        print(f"  total articles: {total_articles}  ->  {total_articles/total_years:,.0f} articles/year  "
              f"(~{total_articles/(total_years*365):.1f} articles/day)")
        print(f"  price-moving (ar_significant) events: {total_sig}  ->  {total_sig/total_years:.1f} per year")

        if total_sig >= 2:
            gaps_days = sig["dt"].diff().dt.total_seconds().dropna() / 86400
            print(f"  average gap between price-moving news events: {gaps_days.mean():.1f} days "
                  f"(median {gaps_days.median():.1f} days, min {gaps_days.min():.1f}, max {gaps_days.max():.1f})")
        else:
            print("  not enough significant events to compute a gap")

        print("\n  year-by-year:")
        yearly = events.groupby("year").agg(
            articles=("article_id", "count"),
        )
        yearly["significant"] = sig.groupby(sig["dt"].dt.year).size()
        yearly["significant"] = yearly["significant"].fillna(0).astype(int)
        yearly["sig_rate_pct"] = (yearly["significant"] / yearly["articles"] * 100).round(2)
        print("   " + yearly.to_string().replace("\n", "\n   "))


if __name__ == "__main__":
    main()
