"""SQLite repository for enriched news articles and thread analytics.

Uses vinu-infra's SQLiteBackend for thread-local connection management,
WAL mode, and schema lifecycle.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

from vinu_infra.sqlite import SQLiteBackend
from vinu_news.analysis.storage.fts import init_fts
from vinu_news.analysis.storage.models import ArticleRecord, EnrichedArticle, TickerMention

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "news.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

ARTICLE_COLUMNS = (
    "id", "headline", "summary", "source", "link", "sort_ts", "region", "tier",
    "category", "priority", "sentiment", "sentiment_score", "impact", "tickers",
    "lang", "threat_level", "threat_cat", "threat_conf", "source_flag",
    "entities_json", "cluster_id", "is_lead", "thread_id",
    "finbert_score", "finbert_label",
    "published_at", "ingested_at", "publish_time_is_estimated",
    "content_hash", "first_seen_at", "last_seen_at", "seen_count", "revision_of", "is_current",
)

THREAD_COLUMNS = (
    "thread_id", "first_seen_at", "last_seen_at", "article_count",
    "lead_headline", "dominant_ticker", "entities_json", "category",
    "last_article_id", "norm_text",
)

SNAPSHOT_COLUMNS = (
    "thread_id", "date", "article_count", "bullish_count",
    "bearish_count", "neutral_count", "flash_count",
)

_ARTICLE_COLS = ", ".join(ARTICLE_COLUMNS)
_ARTICLE_COLS_A = "a." + ", a.".join(ARTICLE_COLUMNS)
_THREAD_COLS = ", ".join(THREAD_COLUMNS)
_SNAPSHOT_COLS = ", ".join(SNAPSHOT_COLUMNS)

_MIGRATION_COLUMNS = (
    ("entities_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("cluster_id", "TEXT"),
    ("is_lead", "INTEGER NOT NULL DEFAULT 1"),
    ("thread_id", "TEXT"),
    ("finbert_score", "REAL"),
    ("finbert_label", "TEXT"),
    ("published_at", "INTEGER"),
    ("ingested_at", "INTEGER NOT NULL DEFAULT 0"),
    ("publish_time_is_estimated", "INTEGER NOT NULL DEFAULT 0"),
    ("content_hash", "TEXT"),
    ("first_seen_at", "INTEGER NOT NULL DEFAULT 0"),
    ("last_seen_at", "INTEGER NOT NULL DEFAULT 0"),
    ("seen_count", "INTEGER NOT NULL DEFAULT 1"),
    ("revision_of", "TEXT"),
    ("is_current", "INTEGER NOT NULL DEFAULT 1"),
)


def normalize_link(link: str) -> str:
    """Normalize URL for dedup comparisons."""
    if not link:
        return ""
    parsed = urlparse(link.strip())
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    normalized = urlunparse((parsed.scheme.lower(), netloc, path, "", parsed.query, ""))
    return normalized


class NewsRepository(SQLiteBackend):
    def __init__(self, db_path: str | Path | None = None, *, seed_reference: bool = True) -> None:
        path = str(Path(db_path) if db_path else DEFAULT_DB_PATH)
        # The 63,000-row ticker reference list is seeded once, in the central database, not into every ticker file.
        self._seed_reference = seed_reference
        super().__init__(path)

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _init_schema(self, conn: Any) -> None:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema)
        self._migrate(conn)
        init_fts(conn)
        conn.commit()
        if self._seed_reference:
            from vinu_news.analysis.enrichment.ticker_db import sync_ticker_db_if_needed
            sync_ticker_db_if_needed(conn)

    def _migrate(self, conn: Any) -> None:
        existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(articles)").fetchall()
        }
        added: set[str] = set()
        for col_name, col_def in _MIGRATION_COLUMNS:
            if col_name not in existing:
                try:
                    conn.execute(
                        f"ALTER TABLE articles ADD COLUMN {col_name} {col_def}"
                    )
                except sqlite3.OperationalError as exc:
                    # another thread's connection added it first (first start opens several at once)
                    if "duplicate column name" not in str(exc):
                        raise
                    continue
                added.add(col_name)
        if "first_seen_at" in added:
            # rows from before layer 2: first seen when this system ingested them (publish time for the oldest rows)
            conn.execute(
                "UPDATE articles SET first_seen_at = CASE WHEN ingested_at > 0 THEN ingested_at ELSE sort_ts END, "
                "last_seen_at = CASE WHEN ingested_at > 0 THEN ingested_at ELSE sort_ts END"
            )
        if "content_hash" in added:
            from vinu_news.analysis.storage.dedup import content_hash

            conn.create_function("vn_content_hash", 2, content_hash)
            conn.commit()
            # In small steps: one big UPDATE held the write lock for seconds while the ingest loop and the finbert worker
            # started in the same container, and both gave up with 'database is locked' and exited.
            last = conn.execute("SELECT COALESCE(MAX(rowid), 0) FROM articles").fetchone()[0]
            step = 2000
            for lo in range(0, last + 1, step):
                conn.execute(
                    "UPDATE articles SET content_hash = vn_content_hash(headline, summary) "
                    "WHERE content_hash IS NULL AND rowid > ? AND rowid <= ?",
                    (lo, lo + step),
                )
                conn.commit()
        from vinu_news.sources.health import migrate as migrate_feed_health

        migrate_feed_health(conn)
        from vinu_news.analysis.storage.stories import migrate_story_sources

        migrate_story_sources(conn)

    @property
    def conn(self) -> Any:
        return self._get_conn()

    def link_exists(self, link: str) -> bool:
        normalized = normalize_link(link)
        row = self.conn.execute(
            "SELECT 1 FROM articles WHERE link = ? OR link = ? LIMIT 1",
            (link, normalized),
        ).fetchone()
        return row is not None

    def get_thread_id_for_link(self, link: str) -> str | None:
        normalized = normalize_link(link)
        row = self.conn.execute(
            "SELECT thread_id FROM articles WHERE link = ? OR link = ? LIMIT 1",
            (link, normalized),
        ).fetchone()
        if row and row["thread_id"]:
            return row["thread_id"]
        return None

    def current_by_link(self, link: str) -> dict[str, Any] | None:
        """The current row for a link (the newest revision), or None."""
        normalized = normalize_link(link)
        row = self.conn.execute(
            "SELECT id, content_hash, thread_id, first_seen_at, seen_count FROM articles "
            "WHERE (link = ? OR link = ?) AND is_current = 1 ORDER BY first_seen_at DESC LIMIT 1",
            (link, normalized),
        ).fetchone()
        return dict(row) if row else None

    def mark_seen(self, article_id: str, now: int) -> None:
        """The source served the same item with the same text again: only the last-seen time and the count move."""
        with self.conn:
            self.conn.execute(
                "UPDATE articles SET last_seen_at = MAX(last_seen_at, ?), seen_count = seen_count + 1 WHERE id = ?",
                (now, article_id),
            )

    def add_revision(self, enriched: EnrichedArticle, previous: dict[str, Any]) -> str:
        """Store changed text as a new row linked to the one it replaces; the old row stays, no longer current."""
        from vinu_news.analysis.enrichment.article_splitter import _mention_id
        from vinu_news.analysis.storage.dedup import revision_id

        a = enriched.article
        new_id = revision_id(previous["id"], a.content_hash or "")
        for m in enriched.mentions:
            m.article_id = new_id
            m.id = _mention_id(new_id, m.ticker)
        a.id = new_id
        a.revision_of = previous["id"]
        a.thread_id = previous.get("thread_id") or a.thread_id
        a.is_current = 1
        with self.conn:
            self.conn.execute("UPDATE articles SET is_current = 0 WHERE id = ?", (previous["id"],))
        self.upsert_article(enriched)
        return new_id

    def upsert_article(self, enriched: EnrichedArticle) -> bool:
        """Insert article and mentions; returns True if article was inserted."""
        article = enriched.article
        placeholders = ", ".join("?" for _ in ARTICLE_COLUMNS)
        columns = ", ".join(ARTICLE_COLUMNS)

        with self.conn:
            cursor = self.conn.execute(
                f"INSERT OR IGNORE INTO articles ({columns}) VALUES ({placeholders})",
                tuple(getattr(article, col) for col in ARTICLE_COLUMNS),
            )
            inserted = cursor.rowcount > 0

            if enriched.mentions:
                self.conn.executemany(
                    """
                    INSERT OR IGNORE INTO article_ticker_mentions
                        (id, article_id, ticker, dominance, is_primary)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (m.id, m.article_id, m.ticker, m.dominance, m.is_primary)
                        for m in enriched.mentions
                    ],
                )

        return inserted

    def upsert_batch(self, enriched_list: list[EnrichedArticle]) -> int:
        """Insert multiple articles; returns count of newly inserted articles."""
        count = 0
        for item in enriched_list:
            if self.upsert_article(item):
                count += 1
        return count

    def get_active_threads(self, since_ts: int, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            f"""
            SELECT {_THREAD_COLS} FROM story_threads
            WHERE last_seen_at >= ?
            ORDER BY last_seen_at DESC
            LIMIT ?
            """,
            (since_ts, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_thread(self, thread_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            f"SELECT {_THREAD_COLS} FROM story_threads WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_thread_articles(
        self, thread_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            f"""
            SELECT {_ARTICLE_COLS} FROM articles
            WHERE thread_id = ? AND is_current = 1
            ORDER BY sort_ts DESC
            LIMIT ?
            """,
            (thread_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_thread_timeline(self, thread_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            f"""
            SELECT {_SNAPSHOT_COLS} FROM thread_daily_snapshots
            WHERE thread_id = ?
            ORDER BY date ASC
            """,
            (thread_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_ticker_daily_stats(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT * FROM ticker_daily_stats
            WHERE ticker = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
            """,
            (ticker.upper(), start_date, end_date),
        ).fetchall()
        return [dict(row) for row in rows]

    def search_articles(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            f"""
            SELECT {_ARTICLE_COLS_A}
            FROM articles a
            JOIN articles_fts ON a.rowid = articles_fts.rowid
            WHERE articles_fts MATCH ? AND a.is_current = 1 AND a.is_lead = 1
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_news_for_ticker(
        self,
        ticker: str,
        start_ts: int | None = None,
        end_ts: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = f"""
            SELECT {_ARTICLE_COLS_A}, m.ticker AS mention_ticker, m.dominance, m.is_primary
            FROM article_ticker_mentions m
            JOIN articles a ON a.id = m.article_id
            WHERE m.ticker = ? AND a.is_current = 1 AND a.is_lead = 1
        """
        params: list[Any] = [ticker.upper()]

        if start_ts is not None:
            query += " AND a.sort_ts >= ?"
            params.append(start_ts)
        if end_ts is not None:
            query += " AND a.sort_ts <= ?"
            params.append(end_ts)

        query += " ORDER BY a.sort_ts DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_news_for_date(self, date_str: str, limit: int = 500) -> list[dict[str, Any]]:
        """Return articles for calendar date YYYY-MM-DD (UTC)."""
        start = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_ts = start.replace(hour=23, minute=59, second=59)
        start_ts = int(start.timestamp())
        end_ts_int = int(end_ts.timestamp())

        rows = self.conn.execute(
            f"""
            SELECT {_ARTICLE_COLS} FROM articles
            WHERE sort_ts >= ? AND sort_ts <= ? AND is_current = 1 AND is_lead = 1
            ORDER BY sort_ts DESC
            LIMIT ?
            """,
            (start_ts, end_ts_int, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_high_impact(
        self,
        since_ts: int,
        sentiment: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = f"""
            SELECT {_ARTICLE_COLS} FROM articles
            WHERE impact = 'HIGH' AND sort_ts >= ? AND is_current = 1 AND is_lead = 1
        """
        params: list[Any] = [since_ts]

        if sentiment is not None:
            query += " AND sentiment = ?"
            params.append(sentiment)

        query += " ORDER BY sort_ts DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def parse_pub_date(pub_date: str) -> tuple[int | None, bool]:
    """Parse RSS pubDate string to a Unix timestamp (seconds).

    Returns `(timestamp, is_estimated)`. `is_estimated=True` means no real
    pubDate could be parsed and `timestamp` is `None` -- the caller is
    responsible for substituting its own real "now" (item #19 finding #1:
    this function silently returning `now()` here, with no signal that a
    substitution happened, is exactly the silent look-ahead-bias gap that
    was found and fixed)."""
    if not pub_date:
        return None, True

    try:
        dt = parsedate_to_datetime(pub_date)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp()), False
    except (TypeError, ValueError, OverflowError):
        pass

    for fmt in (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(pub_date, fmt).replace(tzinfo=timezone.utc)
            return int(dt.timestamp()), False
        except ValueError:
            continue

    return None, True


def utc_date_from_ts(sort_ts: int) -> str:
    """Return YYYY-MM-DD UTC date string from unix timestamp."""
    return datetime.fromtimestamp(sort_ts, tz=timezone.utc).strftime("%Y-%m-%d")
