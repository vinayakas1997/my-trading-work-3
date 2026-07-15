"""09_historical_news_and_bars_analysis.py

Fetches Alpaca historical news (with content) + 1-min bars for AAPL
using raw HTTP requests with proper pagination, measures sizes/API
calls, and estimates full-year storage.

Usage:
    python alpaca-try/09_historical_news_and_bars_analysis.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

API_KEY = os.environ.get("ALPACA_API_KEY", "")
SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY", "")

if not API_KEY or not SECRET_KEY:
    sys.exit("ERROR: ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in .env")

DATA_BASE_URL = "https://data.alpaca.markets"
SYMBOL = "AAPL"

_HEADERS = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": SECRET_KEY,
}


def fmt_bytes(b: int) -> str:
    if b < 1024:
        return f"{b} B"
    elif b < 1024 * 1024:
        return f"{b / 1024:.1f} KB"
    else:
        return f"{b / (1024 * 1024):.2f} MB"


def fmt_num(n: int | float) -> str:
    if isinstance(n, float):
        return f"{n:,.1f}"
    return f"{n:,}"


def fetch_news_raw(
    symbol: str,
    start_iso: str,
    end_iso: str,
    include_content: bool = True,
    exclude_contentless: bool = True,
) -> tuple[list[dict], int, int]:
    """Fetch all news articles for a date range using raw HTTP.

    Returns: (articles, api_calls, total_response_bytes)
    """
    articles: list[dict] = []
    calls = 0
    total_bytes = 0
    page_token: str | None = None
    url = f"{DATA_BASE_URL}/v1beta1/news"

    while True:
        params: dict[str, str] = {
            "symbols": symbol,
            "start": start_iso,
            "end": end_iso,
            "limit": "50",
            "include_content": "true" if include_content else "false",
            "exclude_contentless": "true" if exclude_contentless else "false",
        }
        if page_token:
            params["page_token"] = page_token

        resp = requests.get(url, headers=_HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        calls += 1
        raw_size = len(resp.content)
        total_bytes += raw_size
        data = resp.json()

        chunk = data.get("news", [])
        articles.extend(chunk)

        page_token = data.get("next_page_token")
        if not page_token:
            break

    return articles, calls, total_bytes


def fetch_bars_raw(
    symbol: str,
    start_iso: str,
    end_iso: str,
) -> tuple[list[dict], int, int]:
    """Fetch all 1-min bars for a date range using raw HTTP.

    Returns: (bars, api_calls, total_response_bytes)
    """
    bars: list[dict] = []
    calls = 0
    total_bytes = 0
    page_token: str | None = None
    url = f"{DATA_BASE_URL}/v2/stocks/bars"

    while True:
        params: dict[str, str] = {
            "symbols": symbol,
            "timeframe": "1Min",
            "start": start_iso,
            "end": end_iso,
            "limit": "10000",
        }
        if page_token:
            params["page_token"] = page_token

        resp = requests.get(url, headers=_HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        calls += 1
        raw_size = len(resp.content)
        total_bytes += raw_size
        data = resp.json()

        chunk = data.get("bars", {}).get(symbol, [])
        bars.extend(chunk)

        page_token = data.get("next_page_token")
        if not page_token:
            break

    return bars, calls, total_bytes


def analyze_articles_raw(articles: list[dict]) -> dict:
    """Measure per-field sizes across all articles (raw dicts)."""
    if not articles:
        return {}

    field_sizes: dict[str, list[int]] = {
        "id": [],
        "headline": [],
        "summary": [],
        "content": [],
        "author": [],
        "source": [],
        "url": [],
        "symbols": [],
        "images": [],
        "created_at": [],
        "updated_at": [],
    }

    for a in articles:
        field_sizes["id"].append(sys.getsizeof(str(a.get("id", ""))))
        field_sizes["headline"].append(sys.getsizeof(a.get("headline", "")))
        field_sizes["summary"].append(sys.getsizeof(a.get("summary", "")))
        field_sizes["content"].append(sys.getsizeof(a.get("content", "")))
        field_sizes["author"].append(sys.getsizeof(a.get("author", "")))
        field_sizes["source"].append(sys.getsizeof(a.get("source", "")))
        field_sizes["url"].append(sys.getsizeof(a.get("url", "") or ""))
        field_sizes["symbols"].append(sys.getsizeof(json.dumps(a.get("symbols", []))))
        imgs = json.dumps(a.get("images", []))
        field_sizes["images"].append(sys.getsizeof(imgs))
        field_sizes["created_at"].append(sys.getsizeof(a.get("created_at", "") or ""))
        field_sizes["updated_at"].append(sys.getsizeof(a.get("updated_at", "") or ""))

    stats = {}
    for field, sizes in field_sizes.items():
        if not sizes:
            continue
        stats[field] = {
            "avg": sum(sizes) / len(sizes),
            "min": min(sizes),
            "max": max(sizes),
            "total": sum(sizes),
        }
    stats["_article_count"] = len(articles)
    stats["_total_bytes"] = sum(
        v["total"] for k, v in stats.items() if not k.startswith("_")
    )
    return stats


def estimate_storage(stats: dict, no_content: bool = False) -> dict:
    count = stats["_article_count"]
    total = stats["_total_bytes"]
    if no_content:
        total -= stats.get("content", {}).get("total", 0)
    daily_articles = count / 31
    yearly_articles = daily_articles * 365
    yearly_bytes = (total / count) * yearly_articles
    return {
        "per_article_bytes": total / count,
        "daily_articles": daily_articles,
        "yearly_articles": yearly_articles,
        "yearly_bytes": yearly_bytes,
        "three_year_bytes": yearly_bytes * 3,
    }


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def run() -> None:
    print("=" * 70)
    print("  ALPACA HISTORICAL DATA ANALYSIS  [raw HTTP + pagination]")
    print("  Symbol: AAPL  |  Sample: January 2023")
    print("  News: include_content=True, exclude_contentless=False")
    print("  Bars: 1-minute timeframe")
    print("=" * 70)

    # -- SPLIT JAN 2023 INTO 4 WEEKLY CHUNKS --
    weeks = [
        (datetime(2023, 1, 1, tzinfo=timezone.utc),
         datetime(2023, 1, 7, 23, 59, 59, tzinfo=timezone.utc)),
        (datetime(2023, 1, 8, tzinfo=timezone.utc),
         datetime(2023, 1, 14, 23, 59, 59, tzinfo=timezone.utc)),
        (datetime(2023, 1, 15, tzinfo=timezone.utc),
         datetime(2023, 1, 21, 23, 59, 59, tzinfo=timezone.utc)),
        (datetime(2023, 1, 22, tzinfo=timezone.utc),
         datetime(2023, 1, 31, 23, 59, 59, tzinfo=timezone.utc)),
    ]

    jan_start_iso = "2023-01-01T00:00:00Z"
    jan_end_iso = "2023-01-31T23:59:59Z"

    # -- PHASE 1: NEWS (parallel weekly chunks) --
    print("\n-- PHASE 1: FETCHING NEWS (4 parallel workers) --\n")
    news_start = time.perf_counter()

    all_news: list[dict] = []
    news_call_count = 0
    news_total_bytes = 0
    news_errors: list[str] = []
    week_details: list[dict] = []

    def fetch_news_worker(week_num: int, s: datetime, e: datetime) -> dict:
        s_iso = iso(s)
        e_iso = iso(e)
        articles, calls, raw_bytes = fetch_news_raw(
            SYMBOL, s_iso, e_iso,
            include_content=True,
            exclude_contentless=False,
        )
        return {
            "week": week_num,
            "articles": articles,
            "calls": calls,
            "raw_bytes": raw_bytes,
        }

    with ThreadPoolExecutor(max_workers=4) as pool:
        fut_map = {
            pool.submit(fetch_news_worker, i + 1, s, e): (i + 1, s, e)
            for i, (s, e) in enumerate(weeks)
        }
        for fut in as_completed(fut_map):
            week_num, ws, we = fut_map[fut]
            try:
                result = fut.result()
                week_details.append(result)
                all_news.extend(result["articles"])
                news_call_count += result["calls"]
                news_total_bytes += result["raw_bytes"]
                print(
                    f"  Week {week_num} ({ws.strftime('%m/%d')}-{we.strftime('%m/%d')}): "
                    f"{len(result['articles']):>5} articles, "
                    f"{result['calls']} API calls, "
                    f"{fmt_bytes(result['raw_bytes'])}"
                )
            except Exception as e:
                err = f"Week {week_num}: {e}"
                news_errors.append(err)
                print(f"  Week {week_num}: ERROR -- {e}")

    news_elapsed = time.perf_counter() - news_start

    # -- PHASE 2: BARS (1-min, full month) --
    print("\n-- PHASE 2: FETCHING 1-MIN BARS (full month) --\n")
    bars_start = time.perf_counter()

    bars, bars_calls, bars_total_bytes = fetch_bars_raw(
        SYMBOL, jan_start_iso, jan_end_iso
    )
    print(
        f"  Fetched {fmt_num(len(bars))} bars, "
        f"{bars_calls} API calls, "
        f"{fmt_bytes(bars_total_bytes)}"
    )

    bars_elapsed = time.perf_counter() - bars_start

    # -- ANALYSIS --
    print("\n-- ANALYSIS --\n")

    news_stats = analyze_articles_raw(all_news)
    yearly_est = estimate_storage(news_stats, no_content=False)
    yearly_est_nc = estimate_storage(news_stats, no_content=True)

    bar_total_size = 0
    avg_bar = 0
    if bars:
        bar_sizes = [sys.getsizeof(json.dumps(b, default=str)) for b in bars]
        bar_total_size = sum(bar_sizes)
        avg_bar = bar_total_size / len(bars)

    # -- PRINT REPORT --
    print("=" * 70)
    print("  COMPLETE ANALYSIS REPORT")
    print("=" * 70)
    print()
    print(f"  Total articles fetched:  {fmt_num(len(all_news))}")
    print(f"  Total 1-min bars:        {fmt_num(len(bars))}")
    print()

    if news_errors:
        print("  ERRORS ENCOUNTERED:")
        for e in news_errors:
            print(f"    - {e}")
        print()

    print("  -- API CALLS --")
    print(f"  News API calls:          {news_call_count}")
    print(f"  Bars API calls:          {bars_calls}")
    print(f"  Total API calls:         {news_call_count + bars_calls}")
    print(f"  Peak parallelism:        4 workers")
    print()

    print("  -- RAW RESPONSE DATA VOLUME --")
    print(f"  News response bytes:     {fmt_bytes(news_total_bytes)}")
    print(f"  Bars response bytes:     {fmt_bytes(bars_total_bytes)}")
    print(f"  Total response data:     {fmt_bytes(news_total_bytes + bars_total_bytes)}")
    print()

    # Per-week news breakdown
    print("  -- NEWS PER-WEEK BREAKDOWN --")
    print(f"  {'Week':<10} {'Articles':>10} {'API Calls':>10} {'Resp Size':>12} {'Articles/Page':>14}")
    print(f"  {'-'*10} {'-'*10} {'-'*10} {'-'*12} {'-'*14}")
    for w in sorted(week_details, key=lambda x: x["week"]):
        pages_needed = w["calls"]
        articles_per_page = len(w["articles"]) / max(pages_needed, 1)
        print(
            f"  {w['week']:<10} {len(w['articles']):>10} "
            f"{w['calls']:>10} {fmt_bytes(w['raw_bytes']):>12} "
            f"{articles_per_page:>13.1f}"
        )
    print()

    # Per-article field breakdown
    if news_stats:
        print("  -- PER-ARTICLE FIELD SIZE BREAKDOWN --")
        print(f"  {'Field':<15} {'Avg':>10} {'Min':>10} {'Max':>10} {'% of total':>12}")
        print(f"  {'-'*15} {'-'*10} {'-'*10} {'-'*10} {'-'*12}")
        for field in ["headline", "summary", "content", "author", "source",
                       "url", "symbols", "images", "created_at", "updated_at", "id"]:
            if field not in news_stats:
                continue
            s = news_stats[field]
            pct = (s["total"] / news_stats["_total_bytes"]) * 100
            print(
                f"  {field:<15} {fmt_bytes(int(s['avg'])):>10} "
                f"{fmt_bytes(int(s['min'])):>10} {fmt_bytes(int(s['max'])):>10} "
                f"{pct:>10.1f}%"
            )
        print(f"  {'-'*15} {'-'*10} {'-'*10} {'-'*10} {'-'*12}")
        content_total = news_stats.get("content", {}).get("total", 0)
        non_content = news_stats["_total_bytes"] - content_total
        print(f"  {'TOTAL (with content)':<15} {fmt_bytes(news_stats['_total_bytes']):>10}")
        print(f"  {'TOTAL (no content)':<15}  {fmt_bytes(int(non_content)):>10}")
        print()

    # Storage estimates
    if news_stats:
        print("  -- STORAGE ESTIMATES (extrapolated) --")
        print()
        print(f"  Based on Jan 2023 sample ({fmt_num(len(all_news))} articles over 31 days)")
        print()
        print(f"  Daily avg articles:      {news_stats['_article_count'] / 31:.1f}")
        print(f"  Per-article (with content):  {fmt_bytes(int(yearly_est['per_article_bytes']))}")
        print(f"  Per-article (no content):    {fmt_bytes(int(yearly_est_nc['per_article_bytes']))}")
        print()
        print(f"  {'Scenario':<35} {'1 Year':>15} {'3 Years':>15}")
        print(f"  {'-'*35} {'-'*15} {'-'*15}")
        print(
            f"  {'With content (raw JSON)':<35} {fmt_bytes(int(yearly_est['yearly_bytes'])):>15} "
            f"{fmt_bytes(int(yearly_est['three_year_bytes'])):>15}"
        )
        print(
            f"  {'Without content (raw JSON)':<35} {fmt_bytes(int(yearly_est_nc['yearly_bytes'])):>15} "
            f"{fmt_bytes(int(yearly_est_nc['three_year_bytes'])):>15}"
        )
        print(
            f"  {'With content (SQLite ~1.5x)':<35} {fmt_bytes(int(yearly_est['yearly_bytes'] * 1.5)):>15} "
            f"{fmt_bytes(int(yearly_est['three_year_bytes'] * 1.5)):>15}"
        )
        print(
            f"  {'Without content (SQLite ~1.5x)':<35} {fmt_bytes(int(yearly_est_nc['yearly_bytes'] * 1.5)):>15} "
            f"{fmt_bytes(int(yearly_est_nc['three_year_bytes'] * 1.5)):>15}"
        )
        print()

    # Bars summary
    if bars:
        print("  -- 1-MIN BARS DETAILS --")
        bar_count = len(bars)
        trading_days_est = bar_count / 390
        print(f"  Total bars:              {fmt_num(bar_count)}")
        print(f"  Estimated trading days:  {trading_days_est:.1f}")
        print(f"  Avg bar size (JSON):     {fmt_bytes(int(avg_bar))}")
        print(f"  Total bars data:         {fmt_bytes(bar_total_size)}")
        print(f"  Response bytes on wire:  {fmt_bytes(bars_total_bytes)}")
        print(f"  Fields per bar:          timestamp, open, high, low, close, volume, trade_count, vwap")
        print()

    # Timing
    print("  -- TIMING --")
    print(f"  News fetch (4 workers):  {news_elapsed:.1f}s")
    print(f"  Bars fetch (1 call):     {bars_elapsed:.1f}s")
    print(f"  Total wall time:         {news_elapsed + bars_elapsed:.1f}s")
    print()

    print("  -- KEY TAKEAWAYS --")
    content_pct = 0
    if news_stats and news_stats.get("content"):
        content_pct = (
            news_stats["content"]["total"] / news_stats["_total_bytes"]
        ) * 100
    print(f"  1. Content field is {content_pct:.0f}% of total article storage")
    print(f"  2. Without content: yearly storage ~{fmt_bytes(int(yearly_est_nc['yearly_bytes']))}")
    print(f"  3. With content: yearly storage ~{fmt_bytes(int(yearly_est['yearly_bytes']))}")
    print(f"  4. 1-min bars: ~{fmt_bytes(int(avg_bar))}/bar, {fmt_bytes(int(avg_bar * 390 * 365))}/year")
    print(f"  5. Parallel fetching used {news_call_count} total API calls across 4 workers")
    print()

    # Also show the non-content articles count from exclude_contentless=True
    # Estimate how many have content vs not
    with_content = sum(1 for a in all_news if a.get("content", "").strip())
    print(f"  -- CONTENT AVAILABILITY --")
    print(f"  Articles WITH content:    {with_content}/{len(all_news)} ({with_content/len(all_news)*100:.0f}%)")
    print(f"  Articles WITHOUT content: {len(all_news) - with_content}/{len(all_news)}")
    print()

    print("=" * 70)


if __name__ == "__main__":
    run()
