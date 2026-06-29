"""FTS5 full-text search setup for articles."""

from __future__ import annotations

import sqlite3


def init_fts(conn: sqlite3.Connection) -> None:
    """Create FTS5 virtual table, triggers, and backfill if needed."""
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
            headline, summary,
            content='articles', content_rowid='rowid',
            tokenize='porter unicode61'
        )
        """
    )

    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS articles_fts_insert AFTER INSERT ON articles BEGIN
            INSERT INTO articles_fts(rowid, headline, summary)
            VALUES (new.rowid, new.headline, new.summary);
        END
        """
    )
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS articles_fts_delete AFTER DELETE ON articles BEGIN
            INSERT INTO articles_fts(articles_fts, rowid, headline, summary)
            VALUES ('delete', old.rowid, old.headline, old.summary);
        END
        """
    )
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS articles_fts_update AFTER UPDATE ON articles BEGIN
            INSERT INTO articles_fts(articles_fts, rowid, headline, summary)
            VALUES ('delete', old.rowid, old.headline, old.summary);
            INSERT INTO articles_fts(rowid, headline, summary)
            VALUES (new.rowid, new.headline, new.summary);
        END
        """
    )

    row = conn.execute("SELECT COUNT(*) FROM articles_fts").fetchone()
    fts_count = row[0] if row else 0
    row = conn.execute("SELECT COUNT(*) FROM articles").fetchone()
    article_count = row[0] if row else 0

    if article_count > 0 and fts_count == 0:
        conn.execute(
            """
            INSERT INTO articles_fts(rowid, headline, summary)
            SELECT rowid, headline, summary FROM articles
            """
        )
