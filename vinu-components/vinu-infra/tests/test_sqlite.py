from pathlib import Path
from tempfile import TemporaryDirectory

from vinu_lib.sqlite import SQLiteBackend


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
