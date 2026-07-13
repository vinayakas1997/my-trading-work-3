"""Price reaction computation and cache (TASK-N03)."""

from __future__ import annotations

import sqlite3
import time
from typing import Any

from vinu_news.integrations.stock_price import StockPriceClient


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
