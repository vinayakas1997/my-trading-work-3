"""Shared SQLite schema migration utilities.

Usage:
    from vinu_lib.db import migrate_schema

    migrate_schema(
        conn,
        version=2,
        migrations=[
            ("ALTER TABLE feature_requests ADD COLUMN ml_model TEXT", "1.1.0"),
            ("ALTER TABLE feature_requests ADD COLUMN ml_label TEXT", "1.1.0"),
        ],
    )
"""

from __future__ import annotations

import sqlite3
from typing import Any


def migrate_schema(
    conn: sqlite3.Connection,
    version: int,
    migrations: list[tuple[str, str]],
    *,
    current_version: int | None = None,
) -> None:
    """Run pending migrations using PRAGMA user_version.

    Args:
        conn: Open SQLite connection.
        version: Target schema version after all migrations.
        migrations: List of (sql_statement, description) tuples.
        current_version: Override the detected version (used for testing).
    """
    if current_version is None:
        current_version = conn.execute("PRAGMA user_version").fetchone()[0]

    if current_version >= version:
        return

    for sql, desc in migrations:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass

    conn.execute(f"PRAGMA user_version={version}")
    conn.commit()


def ensure_wal(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")


def table_has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(
        row[1] == column
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    )


def add_columns(
    conn: sqlite3.Connection,
    table: str,
    columns: list[tuple[str, str]],
) -> None:
    for col_name, col_def in columns:
        if not table_has_column(conn, table, col_name):
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
            except sqlite3.OperationalError:
                pass