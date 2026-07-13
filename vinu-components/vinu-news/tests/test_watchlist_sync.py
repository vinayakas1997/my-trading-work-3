"""Tests for shared watchlist sync (TASK-X01)."""

import json
from pathlib import Path

import pytest

from vinu_news.watchlist.shared import read_shared, sync_from_shared, write_shared
from vinu_news.watchlist.store import WatchlistStore
import sqlite3


@pytest.fixture
def watchlist_store(tmp_path: Path) -> WatchlistStore:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    store = WatchlistStore(conn)
    schema = (Path(__file__).resolve().parents[1] / "vinu_news" / "watchlist" / "schema.sql")
    store.init_schema(schema.read_text(encoding="utf-8"))
    return store


def test_write_and_read_shared(tmp_path: Path):
    path = tmp_path / "watchlist.json"
    write_shared(path, ["aapl", "nvda", "aapl"])
    assert read_shared(path) == ["AAPL", "NVDA"]
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "updated_at" in data


def test_sync_from_shared_merges(watchlist_store: WatchlistStore, tmp_path: Path):
    watchlist_store.add_tickers(["MSFT"])
    path = tmp_path / "shared.json"
    write_shared(path, ["AAPL", "MSFT"])
    added = sync_from_shared(watchlist_store, path)
    assert set(added) == {"AAPL"}
    assert set(watchlist_store.list_tickers()) == {"AAPL", "MSFT"}
