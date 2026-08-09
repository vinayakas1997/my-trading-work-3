"""Tests for SQLite registry."""

import threading

from vinu_tools.storage.models import STATUS_DONE, STATUS_PENDING, STATUS_RUNNING, SubmitRequest
from vinu_tools.storage.sqlite_backend import SqliteBackend


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
    running = backend.claim_next_pending()
    assert running is not None
    assert running.status == STATUS_RUNNING

    # second call should return None (no more pending)
    assert backend.claim_next_pending() is None


def test_close_closes_connections_opened_by_other_threads(tmp_path):
    backend = SqliteBackend(tmp_path / "meta.db")

    other_thread_error: list[BaseException] = []

    def touch_from_other_thread() -> None:
        try:
            backend._get_conn()
        except BaseException as exc:  # noqa: BLE001
            other_thread_error.append(exc)

    t = threading.Thread(target=touch_from_other_thread)
    t.start()
    t.join()
    assert not other_thread_error

    assert len(backend._all_conns) == 2  # main-thread conn (from __init__) + the other thread's

    backend.close()  # must not raise despite one connection belonging to a dead thread


def test_get_conn_reopens_after_another_threads_close(tmp_path):
    backend = SqliteBackend(tmp_path / "meta.db")
    conn_before = backend._get_conn()

    backend.close()

    conn_after = backend._get_conn()
    assert conn_after is not conn_before
    # Usable again (no sqlite3.ProgrammingError from the closed original).
    conn_after.execute("SELECT 1").fetchone()

    backend.close()
