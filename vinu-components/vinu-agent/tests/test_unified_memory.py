"""Tests for the unified agent-memory layer."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from vinu_agent.memory.unified_store import (
    MemoryEntry,
    UnifiedMemoryStore,
    _now,
)


@pytest.fixture
def store() -> UnifiedMemoryStore:
    tmp = tempfile.mktemp(suffix=".db")
    s = UnifiedMemoryStore(tmp)
    yield s
    s.close()
    Path(tmp).unlink(missing_ok=True)


import uuid as _uuid


def make_entry(
    source: str = "test",
    source_id: str = "",
    symbol: str = "",
    memory_type: str = "note",
    title: str = "",
    content: str = "",
) -> MemoryEntry:
    uid = _uuid.uuid4().hex[:8]
    return MemoryEntry(
        id=f"{source}-{symbol}-{uid}",
        source=source,
        source_id=source_id or f"test-id-{uid}",
        symbol=symbol,
        memory_type=memory_type,
        title=title,
        content=content,
        summary=content[:100] if content else title[:100],
        created_at=_now(),
        updated_at=_now(),
    )


class TestUnifiedMemoryStore:
    def test_init_creates_tables(self, store: UnifiedMemoryStore) -> None:
        conn = store._get_conn()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r[0] for r in tables}
        assert "memory_entries" in names
        assert "sync_watermarks" in names

    def test_init_creates_fts(self, store: UnifiedMemoryStore) -> None:
        conn = store._get_conn()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r[0] for r in tables}
        assert "memory_fts" in names

    def test_add_entry(self, store: UnifiedMemoryStore) -> None:
        entry = make_entry(source="agent", memory_type="finding", title="test-memory", content="important finding about momentum")
        eid = store.add_entry(entry)
        assert eid == entry.id

        fetched = store.get_entry(eid)
        assert fetched is not None
        assert fetched.source == "agent"
        assert fetched.title == "test-memory"
        assert fetched.content == "important finding about momentum"

    def test_get_entry_not_found(self, store: UnifiedMemoryStore) -> None:
        assert store.get_entry("nonexistent") is None

    def test_delete_entry(self, store: UnifiedMemoryStore) -> None:
        entry = make_entry(title="delete-me")
        store.add_entry(entry)
        assert store.get_entry(entry.id) is not None
        assert store.delete_entry(entry.id) is True
        assert store.get_entry(entry.id) is None

    def test_delete_entry_not_found(self, store: UnifiedMemoryStore) -> None:
        assert store.delete_entry("nonexistent") is False

    def test_search_by_text(self, store: UnifiedMemoryStore) -> None:
        store.add_entry(make_entry(title="AAPL momentum", content="Apple stock has strong momentum"))
        store.add_entry(make_entry(title="TSLA volatility", content="Tesla stock is very volatile"))

        results = store.search("momentum")
        assert len(results) >= 1
        assert any("momentum" in r.title or "momentum" in r.content for r in results)

    def test_search_by_symbol(self, store: UnifiedMemoryStore) -> None:
        store.add_entry(make_entry(symbol="AAPL", title="AAPL analysis", content="AAPL is a good stock"))
        store.add_entry(make_entry(symbol="TSLA", title="TSLA analysis", content="TSLA is volatile"))

        results = store.search("", symbol="AAPL")
        assert len(results) >= 1
        assert all(r.symbol == "AAPL" for r in results)

    def test_search_by_source(self, store: UnifiedMemoryStore) -> None:
        store.add_entry(make_entry(source="research", title="Research run", content="sharpe 1.5"))
        store.add_entry(make_entry(source="news", title="News article", content="market update"))

        results = store.search("", source="research")
        assert len(results) >= 1
        assert all(r.source == "research" for r in results)

    def test_search_by_type(self, store: UnifiedMemoryStore) -> None:
        store.add_entry(make_entry(memory_type="research_run", title="Run 1", content="result"))
        store.add_entry(make_entry(memory_type="news_article", title="News 1", content="article"))

        results = store.search("", memory_type="research_run")
        assert len(results) >= 1
        assert all(r.memory_type == "research_run" for r in results)

    def test_search_limit(self, store: UnifiedMemoryStore) -> None:
        for i in range(10):
            store.add_entry(make_entry(title=f"Entry {i}", content=f"content {i}"))
        results = store.search("", limit=3)
        assert len(results) <= 3

    def test_list_by_symbol(self, store: UnifiedMemoryStore) -> None:
        store.add_entry(make_entry(symbol="AAPL", title="A1", content="a"))
        store.add_entry(make_entry(symbol="AAPL", title="A2", content="b"))
        store.add_entry(make_entry(symbol="TSLA", title="T1", content="c"))

        results = store.list_by_symbol("AAPL")
        assert len(results) == 2

    def test_recent_entries(self, store: UnifiedMemoryStore) -> None:
        for i in range(5):
            store.add_entry(make_entry(title=f"Entry {i}", content=f"content {i}"))
        recent = store.recent_entries(limit=3)
        assert len(recent) <= 3
        assert recent[0].updated_at >= recent[-1].updated_at

    def test_recent_entries_by_source(self, store: UnifiedMemoryStore) -> None:
        store.add_entry(make_entry(source="research", title="R1", content="r1"))
        store.add_entry(make_entry(source="news", title="N1", content="n1"))
        results = store.recent_entries(source="research")
        assert len(results) == 1
        assert results[0].source == "research"

    def test_count(self, store: UnifiedMemoryStore) -> None:
        assert store.count() == 0
        store.add_entry(make_entry(title="E1", content="x"))
        assert store.count() == 1
        store.add_entry(make_entry(title="E2", content="y"))
        assert store.count() == 2

    def test_count_by_source(self, store: UnifiedMemoryStore) -> None:
        store.add_entry(make_entry(source="research", title="R1", content="r1"))
        store.add_entry(make_entry(source="news", title="N1", content="n1"))
        assert store.count(source="research") == 1
        assert store.count(source="news") == 1
        assert store.count() == 2

    def test_watermarks(self, store: UnifiedMemoryStore) -> None:
        wm = store.get_watermark("research")
        assert wm["source"] == "research"
        assert wm["last_sync_at"] == ""

        store.set_watermark("research", last_id="run-123")
        wm = store.get_watermark("research")
        assert wm["last_id"] == "run-123"
        assert wm["last_sync_at"] != ""

    def test_watermark_new_source(self, store: UnifiedMemoryStore) -> None:
        wm = store.get_watermark("nonexistent_source")
        assert wm["source"] == "nonexistent_source"

    def test_bulk_add(self, store: UnifiedMemoryStore) -> None:
        entries = [
            make_entry(title=f"Bulk {i}", content=f"bulk content {i}")
            for i in range(5)
        ]
        count = store.bulk_add(entries)
        assert count == 5
        assert store.count() == 5

    def test_bulk_add_empty_list(self, store: UnifiedMemoryStore) -> None:
        assert store.bulk_add([]) == 0
        assert store.count() == 0

    def test_bulk_add_stamps_ids_and_timestamps(self, store: UnifiedMemoryStore) -> None:
        entries = [MemoryEntry(id="", source="test", title=f"No id {i}", content="x") for i in range(3)]
        assert all(not e.id for e in entries)
        store.bulk_add(entries)
        assert all(e.id for e in entries)
        assert all(e.created_at and e.updated_at for e in entries)
        assert len({e.id for e in entries}) == 3  # every id is real and distinct

    def test_bulk_add_upserts_on_conflicting_id(self, store: UnifiedMemoryStore) -> None:
        entry = make_entry(title="Original", content="v1")
        store.add_entry(entry)
        entry.title = "Updated via bulk_add"
        store.bulk_add([entry])
        assert store.count() == 1
        assert store.get_entry(entry.id).title == "Updated via bulk_add"

    def test_bulk_add_rows_are_searchable_via_fts(self, store: UnifiedMemoryStore) -> None:
        # Real risk area of batching the FTS sync (_sync_fts_rows_many): a
        # real rowid-subquery-per-row INSERT via executemany must still
        # resolve each entry's own real rowid correctly, not just the
        # entries table's own upsert.
        entries = [
            make_entry(title="Zebra crossing report", content="unrelated"),
            make_entry(title="unrelated", content="Giraffe sighting report"),
        ]
        store.bulk_add(entries)
        assert any("Zebra" in r.title for r in store.search("zebra"))
        assert any("Giraffe" in r.content for r in store.search("giraffe"))

    def test_clear_and_rebuild(self, store: UnifiedMemoryStore) -> None:
        store.add_entry(make_entry(source="research", title="R1", content="r1"))
        store.add_entry(make_entry(source="news", title="N1", content="n1"))
        assert store.count() == 2

        store.clear_and_rebuild(source="research")
        assert store.count() == 1
        assert store.count(source="research") == 0

    def test_clear_and_rebuild_all(self, store: UnifiedMemoryStore) -> None:
        store.add_entry(make_entry(title="E1", content="x"))
        store.add_entry(make_entry(title="E2", content="y"))
        store.clear_and_rebuild()
        assert store.count() == 0

    def test_entry_with_metadata(self, store: UnifiedMemoryStore) -> None:
        entry = make_entry(title="With meta", content="test")
        entry.metadata = {"sharpe": 1.5, "symbols": ["AAPL"]}
        store.add_entry(entry)
        fetched = store.get_entry(entry.id)
        assert fetched is not None
        assert fetched.metadata["sharpe"] == 1.5
        assert fetched.metadata["symbols"] == ["AAPL"]

    def test_delete_entries_by_source(self, store: UnifiedMemoryStore) -> None:
        store.add_entry(make_entry(source="research", title="R1", content="r1"))
        store.add_entry(make_entry(source="research", title="R2", content="r2"))
        store.add_entry(make_entry(source="news", title="N1", content="n1"))
        deleted = store.delete_entries_by_source("research")
        assert deleted >= 2
        assert store.count(source="research") == 0
        assert store.count(source="news") == 1

    def test_rebuild_fts(self, store: UnifiedMemoryStore) -> None:
        store.add_entry(make_entry(title="FTS test", content="rebuild this content"))
        store.rebuild_fts()
        results = store.search("rebuild")
        assert len(results) >= 1
