from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from vinu_agent.storage.injected_context_log import InjectedContextLogStore


@pytest.fixture
def store() -> InjectedContextLogStore:
    tmp = tempfile.mktemp(suffix=".db")
    s = InjectedContextLogStore(tmp)
    yield s
    s.close()
    Path(tmp).unlink(missing_ok=True)


class TestInjectedContextLogStore:
    def test_record_then_list_by_session_id(self, store: InjectedContextLogStore) -> None:
        store.record("sess-1", fact_ids=["fact-a"], memory_ids=["mem-a", "mem-b"])
        rows = store.list_by_session_id("sess-1")
        assert len(rows) == 1
        assert rows[0].fact_ids == ["fact-a"]
        assert rows[0].memory_ids == ["mem-a", "mem-b"]

    def test_no_row_written_when_nothing_was_injected(self, store: InjectedContextLogStore) -> None:
        store.record("sess-1", fact_ids=[], memory_ids=[])
        assert store.list_by_session_id("sess-1") == []

    def test_sessions_are_independent(self, store: InjectedContextLogStore) -> None:
        store.record("sess-1", fact_ids=["fact-a"], memory_ids=[])
        store.record("sess-2", fact_ids=["fact-b"], memory_ids=[])
        assert [r.fact_ids for r in store.list_by_session_id("sess-1")] == [["fact-a"]]
        assert [r.fact_ids for r in store.list_by_session_id("sess-2")] == [["fact-b"]]

    def test_multiple_turns_in_one_session_accumulate(self, store: InjectedContextLogStore) -> None:
        store.record("sess-1", fact_ids=["fact-a"], memory_ids=[])
        store.record("sess-1", fact_ids=["fact-b"], memory_ids=[])
        rows = store.list_by_session_id("sess-1")
        assert len(rows) == 2

    def test_distinct_session_ids(self, store: InjectedContextLogStore) -> None:
        store.record("sess-1", fact_ids=["fact-a"], memory_ids=[])
        store.record("sess-2", fact_ids=[], memory_ids=["mem-a"])
        assert set(store.distinct_session_ids()) == {"sess-1", "sess-2"}

    def test_persists_across_instances(self, tmp_path: Path) -> None:
        db_path = tmp_path / "injected.db"
        writer = InjectedContextLogStore(str(db_path))
        writer.record("sess-1", fact_ids=["fact-a"], memory_ids=[])
        writer.close()

        reader = InjectedContextLogStore(str(db_path))
        rows = reader.list_by_session_id("sess-1")
        reader.close()

        assert len(rows) == 1
        assert rows[0].fact_ids == ["fact-a"]
