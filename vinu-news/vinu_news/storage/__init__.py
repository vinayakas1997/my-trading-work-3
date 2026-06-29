"""Storage package."""

from vinu_news.storage.factory import create_storage, storage_from_config
from vinu_news.storage.sqlite_backend import SqliteBackend

__all__ = ["create_storage", "storage_from_config", "SqliteBackend"]
