"""Price reaction computation and cache (TASK-N03)."""

from __future__ import annotations

import sqlite3
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

from vinu_news.integrations.stock_price import StockPriceClient
from vinu_news.rss.config.settings import get_max_workers


def _close_at_or_after(candles: list[dict[str, Any]], target_ts: int) -> float | None:
    for bar in candles:
        if int(bar["bar_ts"]) >= target_ts:
            return float(bar["close"])
    return None


def compute_price_changes(
    candles: list[dict[str, Any]],
    sort_ts: int,
) -> tuple[float | None, float | None]:
    if not candles:
        return None, None
    sorted_bars = sorted(candles, key=lambda b: int(b["bar_ts"]))
    base_close = _close_at_or_after(sorted_bars, sort_ts)
    if base_close is None or base_close == 0:
        return None, None
    close_1h = _close_at_or_after(sorted_bars, sort_ts + 3600)
    close_1d = _close_at_or_after(sorted_bars, sort_ts + 86400)
    ch_1h = ((close_1h - base_close) / base_close * 100) if close_1h is not None else None
    ch_1d = ((close_1d - base_close) / base_close * 100) if close_1d is not None else None
    return ch_1h, ch_1d


def get_cached_reaction(conn: sqlite3.Connection, article_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT price_change_1h, price_change_1d, computed_at FROM article_price_reaction WHERE article_id = ?",
        (article_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "price_change_1h": row["price_change_1h"],
        "price_change_1d": row["price_change_1d"],
        "computed_at": row["computed_at"],
    }


def save_reaction(
    conn: sqlite3.Connection,
    article_id: str,
    price_change_1h: float | None,
    price_change_1d: float | None,
) -> None:
    now = int(time.time())
    conn.execute(
        """
        INSERT INTO article_price_reaction (article_id, price_change_1h, price_change_1d, computed_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(article_id) DO UPDATE SET
            price_change_1h = excluded.price_change_1h,
            price_change_1d = excluded.price_change_1d,
            computed_at = excluded.computed_at
        """,
        (article_id, price_change_1h, price_change_1d, now),
    )
    conn.commit()


def enrich_article_with_reaction(
    conn: sqlite3.Connection,
    article: dict[str, Any],
    client: StockPriceClient,
) -> dict[str, Any]:
    out = dict(article)
    article_id = str(article.get("id", ""))
    if not article_id:
        return out
    cached = get_cached_reaction(conn, article_id)
    if cached:
        out.update(cached)
        return out

    ticker = _primary_ticker(article)
    sort_ts = int(article.get("sort_ts") or 0)
    if not ticker or not sort_ts:
        return out

    candles = client.get_candles(
        ticker,
        from_ts=sort_ts,
        to_ts=sort_ts + 86400 + 3600,
        limit=2000,
    )
    ch_1h, ch_1d = compute_price_changes(candles, sort_ts)
    if ch_1h is None and ch_1d is None:
        return out
    save_reaction(conn, article_id, ch_1h, ch_1d)
    out["price_change_1h"] = ch_1h
    out["price_change_1d"] = ch_1d
    return out


def _day_bucket(sort_ts: int) -> str:
    """UTC calendar-day key used to group articles for shared candle fetches."""
    return datetime.fromtimestamp(sort_ts, tz=timezone.utc).date().isoformat()


def enrich_articles_with_reaction(
    conn: sqlite3.Connection,
    articles: list[dict[str, Any]],
    client: StockPriceClient,
) -> list[dict[str, Any]]:
    """Batched/concurrent equivalent of calling ``enrich_article_with_reaction``
    once per row.

    Produces the same per-article output (same cache reads/writes, same
    price_change_1h/1d values), but eliminates redundant network calls:

    - Articles that already have a cached reaction never hit the network,
      exactly as before.
    - Remaining articles are grouped by (ticker, UTC day). Articles sharing a
      ticker+day reuse a single ``get_candles`` fetch spanning their combined
      time range instead of each fetching independently.
    - The distinct (ticker, day) fetches are issued concurrently, mirroring
      the ThreadPoolExecutor/as_completed pattern used for RSS feed polling
      in rss/fetch/parallel_fetcher.py.

    A group of exactly one article uses the identical from_ts/to_ts/limit
    that ``enrich_article_with_reaction`` would have used, so single-article
    lookups are unaffected.
    """
    out = [dict(a) for a in articles]

    pending: list[tuple[int, str, str, int]] = []
    for i, article in enumerate(articles):
        article_id = str(article.get("id", ""))
        if not article_id:
            continue
        cached = get_cached_reaction(conn, article_id)
        if cached:
            out[i].update(cached)
            continue
        ticker = _primary_ticker(article)
        sort_ts = int(article.get("sort_ts") or 0)
        if not ticker or not sort_ts:
            continue
        pending.append((i, article_id, ticker, sort_ts))

    if not pending:
        return out

    groups: dict[tuple[str, str], list[tuple[int, str, int]]] = defaultdict(list)
    for i, article_id, ticker, sort_ts in pending:
        groups[(ticker, _day_bucket(sort_ts))].append((i, article_id, sort_ts))

    def fetch_group(key: tuple[str, str]) -> tuple[tuple[str, str], list[dict[str, Any]]]:
        ticker, _day = key
        members = groups[key]
        min_ts = min(m[2] for m in members)
        max_ts = max(m[2] for m in members)
        from_ts = min_ts
        to_ts = max_ts + 86400 + 3600
        if len(members) == 1:
            limit = 2000  # identical to the single-article path
        else:
            span_minutes = (to_ts - from_ts) // 60 + 1
            limit = max(2000, int(span_minutes * 2) + 500)
        candles = client.get_candles(ticker, from_ts=from_ts, to_ts=to_ts, limit=limit)
        return key, candles

    fetched: dict[tuple[str, str], list[dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=min(get_max_workers(), len(groups))) as executor:
        future_map = {executor.submit(fetch_group, key): key for key in groups}
        for future in as_completed(future_map):
            key, candles = future.result()
            fetched[key] = candles

    for key, members in groups.items():
        candles = fetched[key]
        for i, article_id, sort_ts in members:
            ch_1h, ch_1d = compute_price_changes(candles, sort_ts)
            if ch_1h is None and ch_1d is None:
                continue
            save_reaction(conn, article_id, ch_1h, ch_1d)
            out[i]["price_change_1h"] = ch_1h
            out[i]["price_change_1d"] = ch_1d

    return out


def _primary_ticker(article: dict[str, Any]) -> str | None:
    import json

    tickers_raw = article.get("tickers")
    if isinstance(tickers_raw, str):
        try:
            tickers = json.loads(tickers_raw)
        except json.JSONDecodeError:
            tickers = []
    else:
        tickers = tickers_raw or []
    if tickers:
        return str(tickers[0]).upper()
    return None
