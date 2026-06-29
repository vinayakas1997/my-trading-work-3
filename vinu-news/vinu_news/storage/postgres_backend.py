"""Postgres storage backend (v1.1 stub)."""

from __future__ import annotations

POSTGRES_STUB_MESSAGE = (
    "Postgres support is planned for v1.1. "
    "Use VINU_NEWS_STORAGE=sqlite or omit VINU_NEWS_STORAGE for the default SQLite backend."
)


class PostgresBackend:
    """Placeholder for future Postgres implementation."""

    def __init__(self, database_url: str) -> None:
        raise NotImplementedError(POSTGRES_STUB_MESSAGE)
