"""Persist leads with cross-batch thread matching and snapshot rollups."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from vinu_news.analysis.storage.models import EnrichedArticle
from vinu_news.analysis.storage.repository import NewsRepository, utc_date_from_ts
from vinu_news.analysis.storage.threading.assign import (
    dominant_ticker_from_mentions,
    generate_thread_id,
    thread_row_from_article,
)
from vinu_news.analysis.storage.stories import add_source, initial_sources
from vinu_news.analysis.storage.ticker_news import index_story, refresh_story_counts, touch_story
from vinu_news.analysis.storage.threading.matcher import find_matching_thread


@dataclass
class PersistResult:
    inserted: int
    url_skipped: int
    thread_matched_skipped: int
    threads_created: int
    threads_updated: int
    inserted_links: list[str] = field(default_factory=list)
    seen_again: int = 0     # same item, same text, served again by the source
    revisions: int = 0      # same link, changed text: stored as a new linked row
    stories_joined: int = 0  # a report of an existing story, stored as a raw non-lead row (layer 3)
    members_stored: int = 0  # other reports of a cluster in the same batch, stored under the lead's story


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
    duplicates: list[EnrichedArticle] | None = None,
) -> PersistResult:
    """Insert leads with per-source dedup (layer 2), story matching (layer 3) and snapshot updates.

    `duplicates` are the other reports of each cluster in the same batch. They are kept as raw rows under the story of
    their cluster's lead (not served as separate articles) and add their source to the story."""
    result = PersistResult(
        inserted=0,
        url_skipped=0,
        thread_matched_skipped=0,
        threads_created=0,
        threads_updated=0,
        inserted_links=[],
    )

    for item in leads:
        a = item.article
        entities = a.entities()

        existing = repo.current_by_link(a.link) if a.link else None
        if existing:
            # Layer 2: the same item from the source again. Same text: only last_seen_at and seen_count move (no
            # new thread or daily-count increment: a re-served item is not a new article). Changed text: a new row
            # linked to the old one, with its own first_seen_at.
            result.url_skipped += 1
            now = a.ingested_at or int(time.time())
            a.thread_id = existing.get("thread_id") or a.thread_id
            if existing["content_hash"] in (None, a.content_hash):
                repo.mark_seen(existing["id"], now)
                with repo.conn:
                    touch_story(repo.conn, a.thread_id, now)
                result.seen_again += 1
            else:
                a.first_seen_at = a.last_seen_at = now
                repo.add_revision(item, existing)
                with repo.conn:
                    if a.is_lead:
                        index_story(repo.conn, a.thread_id, item, now)   # the lead's wording changed: facts follow
                result.revisions += 1
            continue

        matched_thread = find_matching_thread(repo, item, entities)

        if matched_thread:
            # Layer 3: a report of a story we already have. It used to be dropped here, so the source that told it
            # (and when) was lost. Keep the raw row under the story, not as a separate article, and tag the story.
            result.thread_matched_skipped += 1
            a.thread_id = matched_thread
            a.is_lead = 0
            if repo.upsert_article(item):
                result.stories_joined += 1
            with repo.conn:
                _bump_thread(repo.conn, matched_thread, a.sort_ts, increment_count=True)
                _upsert_thread_snapshot(repo.conn, matched_thread, item)
                add_source(repo.conn, matched_thread, a.source, a.first_seen_at or a.ingested_at)
                refresh_story_counts(repo.conn, matched_thread)
            result.threads_updated += 1
            continue

        dominant = dominant_ticker_from_mentions(item)
        thread_id = generate_thread_id(item.norm_text, a.sort_ts, dominant)
        a.thread_id = thread_id

        inserted = repo.upsert_article(item)
        if inserted:
            result.inserted += 1
            result.inserted_links.append(a.link)
            row = thread_row_from_article(item, thread_id)
            with repo.conn:
                repo.conn.execute(
                    """
                    INSERT INTO story_threads (
                        thread_id, first_seen_at, last_seen_at, article_count,
                        lead_headline, dominant_ticker, entities_json, category,
                        last_article_id, norm_text, sources_json, n_sources, first_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        initial_sources(a.source, a.first_seen_at or a.ingested_at),
                        1,
                        a.source,
                    ),
                )
                _upsert_thread_snapshot(repo.conn, thread_id, item)
                index_story(repo.conn, thread_id, item)
            result.threads_created += 1
        else:
            result.url_skipped += 1

    _persist_cluster_members(repo, leads, duplicates or [], result)
    repo.conn.commit()
    return result


def _persist_cluster_members(
    repo: NewsRepository,
    leads: list[EnrichedArticle],
    duplicates: list[EnrichedArticle],
    result: PersistResult,
) -> None:
    """Store the other reports of each cluster under the story the cluster's lead belongs to."""
    story_of = {
        l.article.cluster_id: l.article.thread_id for l in leads if l.article.cluster_id and l.article.thread_id
    }
    for member in duplicates:
        a = member.article
        thread_id = story_of.get(a.cluster_id)
        if not thread_id:
            continue            # its lead was filtered out or not stored: nothing to attach to
        a.thread_id = thread_id
        a.is_lead = 0
        existing = repo.current_by_link(a.link) if a.link else None
        if existing:
            now = a.ingested_at or int(time.time())
            if existing["content_hash"] in (None, a.content_hash):
                repo.mark_seen(existing["id"], now)
                result.seen_again += 1
            else:
                a.first_seen_at = a.last_seen_at = now
                repo.add_revision(member, existing)
                result.revisions += 1
            continue
        if repo.upsert_article(member):
            result.members_stored += 1
            with repo.conn:
                _bump_thread(repo.conn, thread_id, a.sort_ts, increment_count=True)
                add_source(repo.conn, thread_id, a.source, a.first_seen_at or a.ingested_at)
                refresh_story_counts(repo.conn, thread_id)
