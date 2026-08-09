import sqlite3

import pytest

from vinu_infra.db import migrate_schema


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE items (id TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    return conn


def test_migrate_schema_runs_pending_migrations_and_bumps_version():
    conn = _conn()
    migrate_schema(
        conn, version=1,
        migrations=[("ALTER TABLE items ADD COLUMN extra TEXT", "add extra")],
        current_version=0,
    )
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    assert any(row[1] == "extra" for row in conn.execute("PRAGMA table_info(items)"))


def test_migrate_schema_skips_when_already_at_target_version():
    conn = _conn()
    migrate_schema(conn, version=1, migrations=[("BOGUS SQL", "never runs")], current_version=1)
    # No exception, migration never even attempted.


def test_migrate_schema_swallows_duplicate_column_idempotency_error():
    conn = _conn()
    conn.execute("ALTER TABLE items ADD COLUMN extra TEXT")
    conn.commit()
    # Re-running the same migration (simulating two processes racing, or a
    # retry after a partial failure) must not raise -- "duplicate column
    # name" is the real, expected idempotency case.
    migrate_schema(
        conn, version=1,
        migrations=[("ALTER TABLE items ADD COLUMN extra TEXT", "add extra")],
        current_version=0,
    )
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1


def test_migrate_schema_does_not_silently_swallow_a_real_error():
    # Real bug this guards against: a bare `except OperationalError: pass`
    # used to swallow every real failure (bad table name, bad column type,
    # etc.), not just "already applied" -- and still bumped user_version to
    # "fully migrated" regardless. A genuinely broken migration must raise.
    conn = _conn()
    with pytest.raises(sqlite3.OperationalError):
        migrate_schema(
            conn, version=1,
            migrations=[("ALTER TABLE items_that_do_not_exist ADD COLUMN x TEXT", "bad table")],
            current_version=0,
        )
    # Version must NOT have been bumped -- the migration genuinely failed.
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
