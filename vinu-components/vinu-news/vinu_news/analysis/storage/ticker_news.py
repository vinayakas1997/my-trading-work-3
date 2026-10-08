"""Layer 5 of the news plan: the table consumers read. One row per (ticker, story).

A story that is mainly about AAPL and mentions MSFT has two rows, `role` primary and mentioned. A range query for one ticker
is one indexed read, with the facts of layer 4 and the source tags of layer 3 on the row. The table is derived: `rebuild()`
recomputes all of it from the raw articles, so a better rule in any layer can be re-applied to everything stored.

Times: `published_at` is the article's own time and is what range and replay (`as_of`) cuts use, as the existing news routes
do. `first_seen_at` is when this system first saw the story (live: the "known at" time); a reader that wants the stricter
cut passes `known_by`. Backfilled history has a late `first_seen_at` by construction, so it is not used for replay by default.
"""
from __future__ import annotations

import json
import time
from typing import Any

from vinu_news.analysis.storage.facts import compute_facts, store_facts
from vinu_news.analysis.storage.models import ArticleRecord, EnrichedArticle, TickerMention

_COLUMNS = (
    "ticker", "story_id", "role", "dominance", "lead_article_id", "headline", "published_at", "first_seen_at",
    "last_seen_at", "n_sources", "n_reports", "event_tag", "sentiment_score", "sentiment_method", "updated_at",
)


def _story(conn: Any, thread_id: str) -> Any:
    return conn.execute(
        "SELECT thread_id, n_sources, article_count, first_seen_at FROM story_threads WHERE thread_id = ?", (thread_id,)
    ).fetchone()


def index_story(conn: Any, thread_id: str, lead: EnrichedArticle, now: int | None = None) -> None:
    """Compute the facts of a story from its lead article and write them and the per-ticker rows (idempotent)."""
    now = int(now if now is not None else time.time())
    facts = compute_facts(lead)
    store_facts(conn, thread_id, facts, now)
    story = _story(conn, thread_id)
    a = lead.article
    n_sources = story["n_sources"] if story else 1
    n_reports = story["article_count"] if story else 1
    last_seen = conn.execute(
        "SELECT COALESCE(MAX(last_seen_at), 0) FROM articles WHERE thread_id = ? AND is_current = 1", (thread_id,)
    ).fetchone()[0] or a.last_seen_at or a.first_seen_at
    rows: list[tuple[Any, ...]] = []
    for m in lead.mentions:
        role = "primary" if m.ticker == facts["primary_ticker"] else "mentioned"
        rows.append((m.ticker, thread_id, role, m.dominance, a.id, a.headline, a.published_at or a.sort_ts,
                     a.first_seen_at or a.ingested_at, last_seen, n_sources, n_reports, facts["event_tag"],
                     facts["sentiment_score"], facts["sentiment_method"], now))
    if not rows and facts["primary_ticker"]:
        rows.append((facts["primary_ticker"], thread_id, "primary", 1.0, a.id, a.headline, a.published_at or a.sort_ts,
                     a.first_seen_at or a.ingested_at, last_seen, n_sources, n_reports, facts["event_tag"],
                     facts["sentiment_score"], facts["sentiment_method"], now))
    conn.execute("DELETE FROM ticker_news WHERE story_id = ?", (thread_id,))
    conn.executemany(
        f"INSERT INTO ticker_news ({', '.join(_COLUMNS)}) VALUES ({', '.join('?' for _ in _COLUMNS)})", rows
    )


def refresh_story_counts(conn: Any, thread_id: str, now: int | None = None) -> None:
    """A later report joined the story: only the counters and the end time move; nothing is recomputed."""
    now = int(now if now is not None else time.time())
    story = _story(conn, thread_id)
    if story is None:
        return
    last_seen = conn.execute(
        "SELECT COALESCE(MAX(last_seen_at), 0) FROM articles WHERE thread_id = ? AND is_current = 1", (thread_id,)
    ).fetchone()[0]
    conn.execute(
        "UPDATE ticker_news SET n_sources = ?, n_reports = ?, last_seen_at = MAX(last_seen_at, ?), updated_at = ? "
        "WHERE story_id = ?",
        (story["n_sources"], story["article_count"], last_seen, now, thread_id),
    )


def touch_story(conn: Any, thread_id: str | None, seen_at: int) -> None:
    """The source served an item of this story again: extend the end time."""
    if thread_id:
        conn.execute("UPDATE ticker_news SET last_seen_at = MAX(last_seen_at, ?) WHERE story_id = ?", (seen_at, thread_id))


def query(
    conn: Any,
    ticker: str,
    *,
    from_ts: int | None = None,
    to_ts: int | None = None,
    known_by: int | None = None,
    event_tag: str | None = None,
    min_sources: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    sql = f"SELECT {', '.join(_COLUMNS)} FROM ticker_news WHERE ticker = ?"
    params: list[Any] = [ticker.upper()]
    if from_ts is not None:
        sql += " AND published_at >= ?"
        params.append(from_ts)
    if to_ts is not None:
        sql += " AND published_at <= ?"
        params.append(to_ts)
    if known_by is not None:
        sql += " AND first_seen_at <= ?"
        params.append(known_by)
    if event_tag:
        sql += " AND event_tag = ?"
        params.append(event_tag)
    if min_sources:
        sql += " AND n_sources >= ?"
        params.append(min_sources)
    sql += " ORDER BY published_at DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _lead_item(conn: Any, thread_id: str) -> EnrichedArticle | None:
    from vinu_news.analysis.storage.repository import ARTICLE_COLUMNS

    row = conn.execute(
        f"SELECT {', '.join(ARTICLE_COLUMNS)} FROM articles WHERE thread_id = ? AND is_current = 1 "
        "ORDER BY is_lead DESC, first_seen_at ASC, rowid ASC LIMIT 1",
        (thread_id,),
    ).fetchone()
    if row is None:
        return None
    record = ArticleRecord(**{c: row[c] for c in ARTICLE_COLUMNS})
    mentions = [
        TickerMention(id=m["id"], article_id=m["article_id"], ticker=m["ticker"], dominance=m["dominance"], is_primary=m["is_primary"])
        for m in conn.execute(
            "SELECT id, article_id, ticker, dominance, is_primary FROM article_ticker_mentions WHERE article_id = ?",
            (record.id,),
        ).fetchall()
    ]
    return EnrichedArticle(article=record, mentions=mentions)


def rebuild(conn: Any, *, chunk: int = 500) -> int:
    """Recompute the facts and the ticker rows of every story from the raw articles. Idempotent; commits in small steps so
    the ingest loop is not locked out. Returns the number of stories indexed."""
    ids = [r[0] for r in conn.execute("SELECT thread_id FROM story_threads").fetchall()]
    done = 0
    for i in range(0, len(ids), chunk):
        for tid in ids[i:i + chunk]:
            lead = _lead_item(conn, tid)
            if lead is not None:
                index_story(conn, tid, lead)
                done += 1
        conn.commit()
    return done


MARKER_KEY = "layer45_indexed_v1"   # bump the suffix to make every database rebuild once more
STALE_AFTER = 600


def rebuild_once(conn: Any) -> bool:
    """Run `rebuild` at most once per database, by whichever connection gets there first (first start opens several at once).
    A marker in vinu_settings elects the runner; a marker left by a runner that died is taken over after ten minutes."""
    now = int(time.time())
    conn.execute("CREATE TABLE IF NOT EXISTS vinu_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    row = conn.execute("SELECT value FROM vinu_settings WHERE key = ?", (MARKER_KEY,)).fetchone()
    if row is not None:
        value = row[0]
        if value == "done":
            return False
        try:
            started = int(value.split(":", 1)[1])
        except (IndexError, ValueError):
            started = 0
        if now - started < STALE_AFTER:
            return False
    stories = conn.execute("SELECT COUNT(*) FROM story_threads").fetchone()[0]
    indexed = conn.execute("SELECT COUNT(*) FROM story_facts").fetchone()[0]
    if stories == 0 or indexed >= stories:
        conn.execute("INSERT OR REPLACE INTO vinu_settings (key, value) VALUES (?, 'done')", (MARKER_KEY,))
        conn.commit()
        return False
    conn.execute("INSERT OR REPLACE INTO vinu_settings (key, value) VALUES (?, ?)", (MARKER_KEY, f"running:{now}"))
    conn.commit()
    rebuild(conn)
    conn.execute("INSERT OR REPLACE INTO vinu_settings (key, value) VALUES (?, 'done')", (MARKER_KEY,))
    conn.commit()
    return True
