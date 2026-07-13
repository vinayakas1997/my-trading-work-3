from __future__ import annotations

import threading
from pathlib import Path

import pytest

from vinu_research.storage import STATUS_DELETED, STATUS_DONE, STATUS_PENDING
from vinu_research.storage.models import ResearchRunRecord
from vinu_research.storage.sqlite_backend import ResearchStorage


class TestInsertAndGet:
    def test_insert_run_sets_id_and_timestamps(self, storage: ResearchStorage, sample_record):
        r = storage.insert_run(sample_record)
        assert r.id is not None
        assert r.id >= 0
        assert r.created_at != ""
        assert r.updated_at != ""
        assert r.status == STATUS_PENDING

    def test_get_run_returns_record(self, storage: ResearchStorage, inserted_run):
        fetched = storage.get_run(inserted_run.id)
        assert fetched is not None
        assert fetched.id == inserted_run.id
        assert fetched.user_idea == inserted_run.user_idea
        assert fetched.symbol == "AAPL"

    def test_get_run_missing_returns_none(self, storage: ResearchStorage):
        assert storage.get_run(99999) is None


class TestListRuns:
    def test_list_runs_excludes_deleted_by_default(self, storage: ResearchStorage, inserted_run):
        storage.delete_run(inserted_run.id)
        runs = storage.list_runs()
        assert len(runs) == 0

    def test_list_runs_filters_by_symbol(self, storage: ResearchStorage):
        Record = ResearchRunRecord
        storage.insert_run(Record(user_idea="test", symbol="AAPL", from_date="2024-01-01", to_date="2024-12-31"))
        storage.insert_run(Record(user_idea="test", symbol="MSFT", from_date="2024-01-01", to_date="2024-12-31"))
        runs = storage.list_runs(symbol="AAPL")
        assert len(runs) == 1
        assert runs[0].symbol == "AAPL"

    def test_list_runs_filters_by_status(self, storage: ResearchStorage):
        Record = ResearchRunRecord
        storage.insert_run(Record(user_idea="test", symbol="AAPL", from_date="2024-01-01", to_date="2024-12-31"))
        r2 = Record(user_idea="test", symbol="AAPL", from_date="2024-01-01", to_date="2024-12-31", status=STATUS_DONE)
        storage.insert_run(r2)
        runs = storage.list_runs(status=STATUS_DONE)
        assert len(runs) == 1
        assert runs[0].status == STATUS_DONE

    def test_list_runs_respects_limit(self, storage: ResearchStorage):
        Record = ResearchRunRecord
        for _ in range(5):
            storage.insert_run(Record(user_idea="test", symbol="AAPL", from_date="2024-01-01", to_date="2024-12-31"))
        runs = storage.list_runs(limit=3)
        assert len(runs) == 3

    def test_list_runs_orders_by_created_at_desc(self, storage: ResearchStorage):
        Record = ResearchRunRecord
        ids = []
        for i in range(3):
            r = storage.insert_run(Record(user_idea=f"test-{i}", symbol="AAPL", from_date="2024-01-01", to_date="2024-12-31"))
            ids.append(r.id)
        runs = storage.list_runs(limit=10)
        assert [r.id for r in runs] == list(reversed(ids))


class TestUpdateAndDelete:
    def test_update_run_modifies_fields(self, storage: ResearchStorage, inserted_run):
        old_updated_at = inserted_run.updated_at
        inserted_run.status = STATUS_DONE
        inserted_run.total_iterations = 5
        inserted_run.best_sharpe = 1.5
        storage.update_run(inserted_run)
        assert inserted_run.updated_at != old_updated_at

        fetched = storage.get_run(inserted_run.id)
        assert fetched.status == STATUS_DONE
        assert fetched.total_iterations == 5
        assert fetched.best_sharpe == 1.5

    def test_delete_soft_deletes(self, storage: ResearchStorage, inserted_run):
        assert storage.delete_run(inserted_run.id) is True
        run = storage.get_run(inserted_run.id)
        assert run.status == STATUS_DELETED

    def test_delete_is_idempotent(self, storage: ResearchStorage, inserted_run):
        assert storage.delete_run(inserted_run.id) is True
        assert storage.delete_run(inserted_run.id) is False

    def test_delete_missing_returns_false(self, storage: ResearchStorage):
        assert storage.delete_run(99999) is False


class TestHealthInfo:
    def test_health_info_returns_expected_keys(self, storage: ResearchStorage):
        info = storage.health_info()
        assert "db_path" in info
        assert "db_size_bytes" in info
        assert "total_runs" in info
        assert "status_counts" in info
        assert info["total_runs"] == 0

    def test_health_info_counts_runs(self, storage: ResearchStorage):
        Record = ResearchRunRecord
        storage.insert_run(Record(user_idea="test", symbol="AAPL", from_date="2024-01-01", to_date="2024-12-31"))
        storage.insert_run(Record(user_idea="test", symbol="AAPL", from_date="2024-01-01", to_date="2024-12-31", status=STATUS_DONE))
        info = storage.health_info()
        assert info["total_runs"] == 2


class TestThreadSafety:
    def test_concurrent_writes(self, storage: ResearchStorage, tmp_db_path: Path, sample_record):
        errors: list[Exception] = []

        def writer():
            try:
                s2 = ResearchStorage(tmp_db_path)
                for i in range(10):
                    rec = sample_record
                    rec.user_idea = f"thread-{i}"
                    s2.insert_run(rec)
                s2.close()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        info = storage.health_info()
        assert info["total_runs"] == 40


class TestContextManager:
    def test_context_manager_closes(self, tmp_db_path: Path):
        with ResearchStorage(tmp_db_path) as s:
            s.insert_run(ResearchRunRecord(user_idea="ctx", symbol="TEST", from_date="2024-01-01", to_date="2024-12-31"))
            info = s.health_info()
            assert info["total_runs"] == 1
        # After __exit__, connection is closed; verify we can still open via a new instance
        s2 = ResearchStorage(tmp_db_path)
        info = s2.health_info()
        assert info["total_runs"] == 1
        s2.close()
