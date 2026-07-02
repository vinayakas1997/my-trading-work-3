"""Storage factory."""

from __future__ import annotations

from pathlib import Path

from vinu_features.config import load_config
from vinu_features.storage.sqlite_backend import SqliteBackend


def create_storage(db_path: Path | None = None) -> SqliteBackend:
    path = db_path or load_config().meta_db_path
    return SqliteBackend(path)
