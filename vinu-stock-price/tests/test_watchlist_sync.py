"""Tests for shared watchlist sync (TASK-X01)."""

import json
from pathlib import Path

import pytest
import sqlite3

from vinu_stock.watchlist.shared import read_shared, sync_from_shared, write_shared
from vinu_stock.watchlist.store import WatchlistStore


@pytest.fixture
def watchlist_store() -> WatchlistStore:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    store = WatchlistStore(conn)
    schema = (Path(__file__).resolve().parents[1] / "vinu_stock" / "watchlist" / "schema.sql")
    store.init_schema(schema.read_text(encoding="utf-8"))
    return store


def test_write_and_read_shared(tmp_path: Path):
    path = tmp_path / "watchlist.json"
    write_shared(path, ["spy", "qqq"])
    assert read_shared(path) == ["QQQ", "SPY"]


def test_sync_from_shared_merges(watchlist_store: WatchlistStore, tmp_path: Path):
    watchlist_store.add_tickers(["AAPL"])
    path = tmp_path / "shared.json"
    write_shared(path, ["NVDA", "AAPL"])
    added = sync_from_shared(watchlist_store, path)
    assert set(added) == {"NVDA"}
    assert set(watchlist_store.list_tickers()) == {"AAPL", "NVDA"}
