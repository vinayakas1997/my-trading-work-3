"""Persist leads with cross-batch thread matching and snapshot rollups."""

from __future__ import annotations

import json
from dataclasses import dataclass

from vinu_news.analysis.storage.models import EnrichedArticle
from vinu_news.analysis.storage.repository import NewsRepository, utc_date_from_ts
from vinu_news.analysis.storage.threading.assign import (
    dominant_ticker_from_mentions,
    generate_thread_id,
    thread_row_from_article,
)
from vinu_news.analysis.storage.threading.matcher import find_matching_thread


@dataclass
class PersistResult:
    inserted: int
    url_skipped: int
    thread_matched_skipped: int
    threads_created: int
    threads_updated: int


def _upsert_thread_snapshot(
    conn,
    thread_id: str,
    article: EnrichedArticle,
) -> None:
    a = article.article
    date = utc_date_from_ts(a.sort_ts)
    flash_inc = 1 if a.priority == "FLASH" else 0
    bull_inc = 1 if a.sentiment == "BULLISH" else 0
    bear_inc = 1 if a.sentiment == "BEARISH" else 0
    neut_inc = 1 if a.sentiment == "NEUTRAL" else 0

    conn.execute(
        """
        INSERT INTO thread_daily_snapshots
            (thread_id, date, article_count, bullish_count, bearish_count,
             neutral_count, flash_count)
        VALUES (?, ?, 1, ?, ?, ?, ?)
        ON CONFLICT(thread_id, date) DO UPDATE SET
            article_count = article_count + 1,
            bullish_count = bullish_count + excluded.bullish_count,
            bearish_count = bearish_count + excluded.bearish_count,
            neutral_count = neutral_count + excluded.neutral_count,
            flash_count = flash_count + excluded.flash_count
        """,
        (thread_id, date, bull_inc, bear_inc, neut_inc, flash_inc),
    )

    ticker = dominant_ticker_from_mentions(article)
    if not ticker:
        return

    conn.execute(
        """
        INSERT INTO ticker_daily_stats
            (ticker, date, article_count, bullish_count, bearish_count,
             neutral_count, top_thread_id)
        VALUES (?, ?, 1, ?, ?, ?, ?)
        ON CONFLICT(ticker, date) DO UPDATE SET
            article_count = article_count + 1,
            bullish_count = bullish_count + excluded.bullish_count,
            bearish_count = bearish_count + excluded.bearish_count,
            neutral_count = neutral_count + excluded.neutral_count,
            top_thread_id = excluded.top_thread_id
        """,
        (ticker, date, bull_inc, bear_inc, neut_inc, thread_id),
    )


def _bump_thread(conn, thread_id: str, sort_ts: int, increment_count: bool) -> None:
    if increment_count:
        conn.execute(
            """
            UPDATE story_threads
            SET last_seen_at = CASE WHEN ? > last_seen_at THEN ? ELSE last_seen_at END,
                article_count = article_count + 1
            WHERE thread_id = ?
            """,
            (sort_ts, sort_ts, thread_id),
        )
    else:
        conn.execute(
            """
            UPDATE story_threads
            SET last_seen_at = CASE WHEN ? > last_seen_at THEN ? ELSE last_seen_at END
            WHERE thread_id = ?
            """,
            (sort_ts, sort_ts, thread_id),
        )


def persist_leads(
    repo: NewsRepository,
    leads: list[EnrichedArticle],
) -> PersistResult:
    """Insert leads with URL dedup, thread matching, and snapshot updates."""
    result = PersistResult(
        inserted=0,
        url_skipped=0,
        thread_matched_skipped=0,
        threads_created=0,
        threads_updated=0,
    )

    for item in leads:
        a = item.article
        entities = a.entities()

        if repo.link_exists(a.link):
            result.url_skipped += 1
            thread_id = repo.get_thread_id_for_link(a.link)
            if thread_id:
                with repo.conn:
                    _bump_thread(repo.conn, thread_id, a.sort_ts, increment_count=False)
                    _upsert_thread_snapshot(repo.conn, thread_id, item)
                    result.threads_updated += 1
            continue

        matched_thread = find_matching_thread(repo, item, entities)

        if matched_thread:
            result.thread_matched_skipped += 1
            with repo.conn:
                _bump_thread(repo.conn, matched_thread, a.sort_ts, increment_count=True)
                _upsert_thread_snapshot(repo.conn, matched_thread, item)
            result.threads_updated += 1
            continue

        dominant = dominant_ticker_from_mentions(item)
        thread_id = generate_thread_id(item.norm_text, a.sort_ts, dominant)
        a.thread_id = thread_id

        inserted = repo.upsert_article(item)
        if inserted:
            result.inserted += 1
            row = thread_row_from_article(item, thread_id)
            with repo.conn:
                repo.conn.execute(
                    """
                    INSERT INTO story_threads (
                        thread_id, first_seen_at, last_seen_at, article_count,
                        lead_headline, dominant_ticker, entities_json, category,
                        last_article_id, norm_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["thread_id"],
                        row["first_seen_at"],
                        row["last_seen_at"],
                        row["article_count"],
                        row["lead_headline"],
                        row["dominant_ticker"],
                        row["entities_json"],
                        row["category"],
                        row["last_article_id"],
                        row["norm_text"],
                    ),
                )
                _upsert_thread_snapshot(repo.conn, thread_id, item)
            result.threads_created += 1
        else:
            result.url_skipped += 1

    repo.conn.commit()
    return result
