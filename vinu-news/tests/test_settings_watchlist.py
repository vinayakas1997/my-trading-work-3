"""Tests for settings and watchlist stores."""

from pathlib import Path

import pytest

from vinu_news.storage.sqlite_backend import SqliteBackend


@pytest.fixture
def backend(tmp_path: Path) -> SqliteBackend:
    db = tmp_path / "test.db"
    with SqliteBackend(db) as b:
        yield b


def test_settings_defaults(backend: SqliteBackend):
    settings = backend.get_settings()
    assert settings.mode == "ticker"
    assert settings.poll_interval_sec == 600


def test_init_schema_respects_env_mode(tmp_path: Path, monkeypatch):
    import vinu_news.config as config_module

    monkeypatch.setenv("VINU_NEWS_MODE", "all")
    monkeypatch.setenv("VINU_NEWS_POLL_INTERVAL_SEC", "300")
    config_module._ENV_LOADED = False

    db = tmp_path / "env_mode.db"
    with SqliteBackend(db) as backend:
        settings = backend.get_settings()
        assert settings.mode == "all"
        assert settings.poll_interval_sec == 300


def test_settings_patch_mode(backend: SqliteBackend):
    updated = backend.patch_settings(mode="ticker")
    assert updated.mode == "ticker"
    assert backend.get_settings().mode == "ticker"


def test_settings_patch_invalid_mode(backend: SqliteBackend):
    with pytest.raises(ValueError):
        backend.patch_settings(mode="invalid")


def test_watchlist_crud(backend: SqliteBackend):
    added = backend.add_watchlist_tickers(["aapl", "nvda", ""])
    assert added == ["AAPL", "NVDA"]
    assert backend.get_watchlist() == ["AAPL", "NVDA"]
    assert backend.remove_watchlist_ticker("aapl") is True
    assert backend.get_watchlist() == ["NVDA"]
    assert backend.remove_watchlist_ticker("ZZZZ") is False


def test_storage_factory_sqlite(tmp_path: Path):
    from vinu_news.storage.factory import create_storage

    db = tmp_path / "news.db"
    with create_storage(storage="sqlite", db_path=db) as storage:
        assert storage.health_info()["storage"] == "sqlite"
        assert storage.article_count() == 0


def test_postgres_stub_raises():
    from vinu_news.storage.factory import create_storage
    from vinu_news.storage.postgres_backend import POSTGRES_STUB_MESSAGE

    with pytest.raises(NotImplementedError, match="v1.1"):
        create_storage(storage="postgres", database_url="postgresql://localhost/test")

    with pytest.raises(ValueError, match="v1.1"):
        create_storage(storage="postgres", database_url=None)
