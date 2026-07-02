"""Tests for SQLite registry."""

from vinu_features.storage.models import STATUS_DONE, STATUS_PENDING, SubmitRequest
from vinu_features.storage.sqlite_backend import SqliteBackend


def _submit(backend: SqliteBackend, title: str = "test_run") -> int:
    req = SubmitRequest(
        title=title,
        symbols=["AAPL"],
        from_ts=1_700_000_000,
        to_ts=1_700_086_400,
        interval="1d",
        preset="basic_ta",
        features=[],
    )
    row = backend.insert_request(req, request_hash="hash1", features=["sma_20", "rsi_14"])
    assert row.id is not None
    return row.id


def test_insert_and_get(backend: SqliteBackend):
    rid = _submit(backend)
    row = backend.get_request(rid)
    assert row is not None
    assert row.status == STATUS_PENDING
    assert row.title == "test_run"


def test_mark_done(backend: SqliteBackend):
    rid = _submit(backend)
    backend.mark_running(rid)
    done = backend.mark_done(rid, file_path="/tmp/run", row_count=10)
    assert done is not None
    assert done.status == STATUS_DONE
    assert done.file_path == "/tmp/run"
    assert done.row_count == 10


def test_get_latest_by_title(backend: SqliteBackend):
    _submit(backend, "alpha")
    row = backend.get_latest_by_title("alpha")
    assert row is not None
    assert row.title == "alpha"


def test_claim_next_pending(backend: SqliteBackend):
    _submit(backend)
    pending = backend.claim_next_pending()
    assert pending is not None
    assert pending.status == STATUS_PENDING
