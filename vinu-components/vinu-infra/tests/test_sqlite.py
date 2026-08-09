import threading
from pathlib import Path
from tempfile import TemporaryDirectory

from vinu_infra.sqlite import SQLiteBackend


class TestBackend(SQLiteBackend):
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS items (
        id TEXT PRIMARY KEY,
        value TEXT
    );
    """
    SCHEMA_VERSION = 1


class CompositeKeyBackend(SQLiteBackend):
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS composite_items (
        key1 TEXT NOT NULL,
        key2 TEXT NOT NULL,
        value TEXT,
        PRIMARY KEY (key1, key2)
    );
    """
    SCHEMA_VERSION = 1


def test_sqlite_backend_init():
    with TemporaryDirectory() as tmp:
        db = TestBackend(Path(tmp) / "test.db")
        conn = db._get_conn()
        assert conn is not None
        db.close()


def test_sqlite_backend_write_read():
    with TemporaryDirectory() as tmp:
        db = TestBackend(Path(tmp) / "test.db")
        conn = db._get_conn()
        conn.execute("INSERT INTO items (id, value) VALUES (?, ?)", ("a1", "hello"))
        conn.commit()
        row = conn.execute("SELECT * FROM items WHERE id=?", ("a1",)).fetchone()
        assert row["value"] == "hello"
        db.close()


def test_sqlite_backend_multiple_connections():
    with TemporaryDirectory() as tmp:
        db1 = TestBackend(Path(tmp) / "test.db")
        db2 = TestBackend(Path(tmp) / "test.db")
        conn1 = db1._get_conn()
        conn1.execute("INSERT INTO items (id, value) VALUES (?, ?)", ("shared", "val"))
        conn1.commit()
        conn2 = db2._get_conn()
        row = conn2.execute("SELECT * FROM items WHERE id=?", ("shared",)).fetchone()
        assert row["value"] == "val"
        db1.close()
        db2.close()


def test_sqlite_backend_health():
    with TemporaryDirectory() as tmp:
        db = TestBackend(Path(tmp) / "test.db")
        info = db.health_info()
        assert "db_path" in info
        assert info["tables"] >= 1
        db.close()


def test_sqlite_backend_context_manager():
    with TemporaryDirectory() as tmp:
        with TestBackend(Path(tmp) / "test.db") as db:
            conn = db._get_conn()
            conn.execute("INSERT INTO items (id, value) VALUES (?, ?)", ("ctx", "ok"))
            conn.commit()


def test_upsert_inserts_new_row():
    with TemporaryDirectory() as tmp:
        db = TestBackend(Path(tmp) / "test.db")
        db.upsert("items", {"id": "u1", "value": "first"}, conflict_columns=["id"])
        row = db._get_conn().execute("SELECT * FROM items WHERE id=?", ("u1",)).fetchone()
        assert row["value"] == "first"
        db.close()


def test_upsert_updates_existing_row():
    with TemporaryDirectory() as tmp:
        db = TestBackend(Path(tmp) / "test.db")
        db.upsert("items", {"id": "u2", "value": "original"}, conflict_columns=["id"])
        db.upsert("items", {"id": "u2", "value": "updated"}, conflict_columns=["id"])
        row = db._get_conn().execute("SELECT * FROM items WHERE id=?", ("u2",)).fetchone()
        assert row["value"] == "updated"
        db.close()


def test_upsert_empty_conflict_columns_raises():
    with TemporaryDirectory() as tmp:
        db = TestBackend(Path(tmp) / "test.db")
        try:
            db.upsert("items", {"id": "e1", "value": "x"}, conflict_columns=[])
            assert False, "should have raised"
        except ValueError:
            pass
        db.close()


def test_insert_or_ignore_skips_on_conflict():
    with TemporaryDirectory() as tmp:
        db = TestBackend(Path(tmp) / "test.db")
        db.insert_or_ignore("items", {"id": "i1", "value": "first"}, conflict_columns=["id"])
        db.insert_or_ignore("items", {"id": "i1", "value": "second"}, conflict_columns=["id"])
        row = db._get_conn().execute("SELECT * FROM items WHERE id=?", ("i1",)).fetchone()
        assert row["value"] == "first"
        db.close()


def test_upsert_composite_key():
    with TemporaryDirectory() as tmp:
        db = CompositeKeyBackend(Path(tmp) / "composite.db")
        db.upsert("composite_items", {"key1": "a", "key2": "b", "value": "v1"},
                  conflict_columns=["key1", "key2"])
        db.upsert("composite_items", {"key1": "a", "key2": "b", "value": "v2"},
                  conflict_columns=["key1", "key2"])
        row = db._get_conn().execute(
            "SELECT * FROM composite_items WHERE key1=? AND key2=?", ("a", "b")
        ).fetchone()
        assert row["value"] == "v2"
        db.close()


def test_upsert_many_inserts_all_rows_in_one_transaction():
    with TemporaryDirectory() as tmp:
        db = TestBackend(Path(tmp) / "test.db")
        db.upsert_many(
            "items",
            [{"id": f"b{i}", "value": f"v{i}"} for i in range(5)],
            conflict_columns=["id"],
        )
        rows = db._get_conn().execute("SELECT * FROM items ORDER BY id").fetchall()
        assert [r["id"] for r in rows] == [f"b{i}" for i in range(5)]
        assert [r["value"] for r in rows] == [f"v{i}" for i in range(5)]
        db.close()


def test_upsert_many_updates_on_conflict():
    with TemporaryDirectory() as tmp:
        db = TestBackend(Path(tmp) / "test.db")
        db.upsert_many("items", [{"id": "c1", "value": "first"}], conflict_columns=["id"])
        db.upsert_many("items", [{"id": "c1", "value": "second"}], conflict_columns=["id"])
        row = db._get_conn().execute("SELECT * FROM items WHERE id=?", ("c1",)).fetchone()
        assert row["value"] == "second"
        db.close()


def test_upsert_many_empty_list_is_a_noop():
    with TemporaryDirectory() as tmp:
        db = TestBackend(Path(tmp) / "test.db")
        db.upsert_many("items", [], conflict_columns=["id"])  # must not raise
        db.close()


def test_upsert_many_empty_conflict_columns_raises():
    with TemporaryDirectory() as tmp:
        db = TestBackend(Path(tmp) / "test.db")
        try:
            db.upsert_many("items", [{"id": "x", "value": "y"}], conflict_columns=[])
            assert False, "should have raised"
        except ValueError:
            pass
        db.close()


def test_close_closes_connections_opened_by_other_threads():
    # Real bug this guards against: threading.local() means close() called
    # from one thread could only ever see that thread's own connection --
    # a connection opened by a different thread (e.g. a request-handling
    # worker thread in a real web server) leaked silently on shutdown.
    # ignore_cleanup_errors=True: Windows can hold the WAL/-shm sidecar
    # files briefly after a real, successful sqlite3 close() -- a known OS-
    # level race in cleanup, not a real failure of the code under test
    # (confirmed separately: the ProgrammingError assertion below already
    # proves the connection was genuinely closed).
    with TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = TestBackend(Path(tmp) / "test.db")
        opened: list = []

        def open_from_worker_thread():
            opened.append(db._get_conn())

        t = threading.Thread(target=open_from_worker_thread)
        t.start()
        t.join()
        assert len(opened) == 1

        db.close()  # called from the main thread, not the worker thread

        import sqlite3
        try:
            opened[0].execute("SELECT 1")
            assert False, "worker thread's connection should have been closed"
        except sqlite3.ProgrammingError:
            pass


def test_get_conn_reopens_after_another_threads_close():
    # A thread whose cached connection was closed by a *different* thread's
    # close() call must transparently reopen on its next _get_conn(), not
    # reuse (and crash on) the stale closed connection object.
    with TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = TestBackend(Path(tmp) / "test.db")
        results: dict = {}

        def worker():
            conn1 = db._get_conn()
            results["conn1_id"] = id(conn1)
            barrier.wait()  # let main thread close() while we hold conn1
            barrier2.wait()  # wait until close() has happened
            conn2 = db._get_conn()  # must reopen, not reuse the closed one
            conn2.execute("SELECT 1")  # must not raise
            results["conn2_id"] = id(conn2)

        barrier = threading.Barrier(2)
        barrier2 = threading.Barrier(2)
        t = threading.Thread(target=worker)
        t.start()
        barrier.wait()
        db.close()
        barrier2.wait()
        t.join()

        assert results["conn1_id"] != results["conn2_id"]
        db.close()


def test_insert_or_ignore_composite_key():
    with TemporaryDirectory() as tmp:
        db = CompositeKeyBackend(Path(tmp) / "composite.db")
        db.insert_or_ignore("composite_items", {"key1": "a", "key2": "b", "value": "v1"},
                            conflict_columns=["key1", "key2"])
        db.insert_or_ignore("composite_items", {"key1": "a", "key2": "b", "value": "v2"},
                            conflict_columns=["key1", "key2"])
        row = db._get_conn().execute(
            "SELECT * FROM composite_items WHERE key1=? AND key2=?", ("a", "b")
        ).fetchone()
        assert row["value"] == "v1"
        db.close()
