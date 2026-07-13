"""Storage backend factory."""

from __future__ import annotations

from pathlib import Path

from vinu_news.config import VinuConfig, load_config
from vinu_news.storage.base import StorageBackend
from vinu_news.storage.postgres_backend import POSTGRES_STUB_MESSAGE, PostgresBackend
from vinu_news.storage.sqlite_backend import SqliteBackend


def create_storage(
    *,
    storage: str | None = None,
    db_path: str | Path | None = None,
    database_url: str | None = None,
) -> StorageBackend:
    cfg = load_config()
    backend = (storage or cfg.storage).lower()

    if backend == "sqlite":
        path = db_path or cfg.db_path
        return SqliteBackend(path)

    if backend == "postgres":
        url = database_url or cfg.database_url
        if not url:
            raise ValueError(
                f"{POSTGRES_STUB_MESSAGE} Set VINU_NEWS_DATABASE_URL when Postgres is available."
            )
        return PostgresBackend(url)

    raise ValueError(f"Unknown VINU_NEWS_STORAGE={backend!r}. Use 'sqlite' or 'postgres'.")


def storage_from_config(config: VinuConfig | None = None) -> StorageBackend:
    cfg = config or load_config()
    return create_storage(
        storage=cfg.storage,
        db_path=cfg.db_path,
        database_url=cfg.database_url,
    )
