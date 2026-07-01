"""SQLite repository for enriched news articles and thread analytics."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

from vinu_news.analysis.storage.fts import init_fts
from vinu_news.analysis.storage.models import ArticleRecord, EnrichedArticle, TickerMention

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "news.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

ARTICLE_COLUMNS = (
    "id", "headline", "summary", "source", "link", "sort_ts", "region", "tier",
    "category", "priority", "sentiment", "sentiment_score", "impact", "tickers",
    "lang", "threat_level", "threat_cat", "threat_conf", "source_flag",
    "entities_json", "cluster_id", "is_lead", "thread_id",
)

_MIGRATION_COLUMNS = (
    ("entities_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("cluster_id", "TEXT"),
    ("is_lead", "INTEGER NOT NULL DEFAULT 1"),
    ("thread_id", "TEXT"),
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


class NewsRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.init_schema()

    def init_schema(self) -> None:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        self._conn.executescript(schema)
        self._migrate_schema()
        init_fts(self._conn)
        self._conn.commit()

    def _migrate_schema(self) -> None:
        """Add columns to existing databases."""
        existing = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(articles)").fetchall()
        }
        for col_name, col_def in _MIGRATION_COLUMNS:
            if col_name not in existing:
                self._conn.execute(
                    f"ALTER TABLE articles ADD COLUMN {col_name} {col_def}"
                )

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> NewsRepository:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def link_exists(self, link: str) -> bool:
        normalized = normalize_link(link)
        row = self._conn.execute(
            "SELECT 1 FROM articles WHERE link = ? OR link = ? LIMIT 1",
            (link, normalized),
        ).fetchone()
        return row is not None

    def get_thread_id_for_link(self, link: str) -> str | None:
        normalized = normalize_link(link)
        row = self._conn.execute(
            "SELECT thread_id FROM articles WHERE link = ? OR link = ? LIMIT 1",
            (link, normalized),
        ).fetchone()
        if row and row["thread_id"]:
            return row["thread_id"]
        return None

    def upsert_article(self, enriched: EnrichedArticle) -> bool:
        """Insert article and mentions; returns True if article was inserted."""
        article = enriched.article
        placeholders = ", ".join("?" for _ in ARTICLE_COLUMNS)
        columns = ", ".join(ARTICLE_COLUMNS)

        with self._conn:
            cursor = self._conn.execute(
                f"INSERT OR IGNORE INTO articles ({columns}) VALUES ({placeholders})",
                tuple(getattr(article, col) for col in ARTICLE_COLUMNS),
            )
            inserted = cursor.rowcount > 0

            if enriched.mentions:
                self._conn.executemany(
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
        rows = self._conn.execute(
            """
            SELECT * FROM story_threads
            WHERE last_seen_at >= ?
            ORDER BY last_seen_at DESC
            LIMIT ?
            """,
            (since_ts, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_thread(self, thread_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM story_threads WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_thread_articles(
        self, thread_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT * FROM articles
            WHERE thread_id = ?
            ORDER BY sort_ts DESC
            LIMIT ?
            """,
            (thread_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_thread_timeline(self, thread_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT * FROM thread_daily_snapshots
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
        rows = self._conn.execute(
            """
            SELECT * FROM ticker_daily_stats
            WHERE ticker = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
            """,
            (ticker.upper(), start_date, end_date),
        ).fetchall()
        return [dict(row) for row in rows]

    def search_articles(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT a.*, n.analysis_json AS llm_analysis
            FROM articles a
            JOIN articles_fts ON a.rowid = articles_fts.rowid
            LEFT JOIN news_analysis n ON a.link = n.url
            WHERE articles_fts MATCH ?
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
        query = """
            SELECT a.*, m.ticker AS mention_ticker, m.dominance, m.is_primary, n.analysis_json AS llm_analysis
            FROM article_ticker_mentions m
            JOIN articles a ON a.id = m.article_id
            LEFT JOIN news_analysis n ON a.link = n.url
            WHERE m.ticker = ?
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

        rows = self._conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_news_for_date(self, date_str: str, limit: int = 500) -> list[dict[str, Any]]:
        """Return articles for calendar date YYYY-MM-DD (UTC)."""
        start = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_ts = start.replace(hour=23, minute=59, second=59)
        start_ts = int(start.timestamp())
        end_ts_int = int(end_ts.timestamp())

        rows = self._conn.execute(
            """
            SELECT * FROM articles
            WHERE sort_ts >= ? AND sort_ts <= ?
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
        query = """
            SELECT * FROM articles
            WHERE impact = 'HIGH' AND sort_ts >= ?
        """
        params: list[Any] = [since_ts]

        if sentiment is not None:
            query += " AND sentiment = ?"
            params.append(sentiment)

        query += " ORDER BY sort_ts DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def parse_pub_date(pub_date: str) -> int:
    """Parse RSS pubDate string to Unix timestamp (seconds)."""
    if not pub_date:
        return int(datetime.now(timezone.utc).timestamp())

    try:
        dt = parsedate_to_datetime(pub_date)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except (TypeError, ValueError, OverflowError):
        pass

    for fmt in (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(pub_date, fmt).replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except ValueError:
            continue

    return int(datetime.now(timezone.utc).timestamp())


def utc_date_from_ts(sort_ts: int) -> str:
    """Return YYYY-MM-DD UTC date string from unix timestamp."""
    return datetime.fromtimestamp(sort_ts, tz=timezone.utc).strftime("%Y-%m-%d")
