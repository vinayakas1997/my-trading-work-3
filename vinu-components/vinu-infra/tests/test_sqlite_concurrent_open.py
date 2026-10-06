"""Many threads opening the same SQLite file at the same moment must all succeed. Each new connection switches the
file to WAL and runs the schema; those statements need locks the busy timeout does not cover, so concurrent opens
raised `database is locked` straight away. That killed the stock ingest cycle and failed the research
concurrent-writes test one run in three."""
from __future__ import annotations

import threading
from pathlib import Path

from vinu_infra.sqlite import SQLiteBackend


class _Backend(SQLiteBackend):
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY AUTOINCREMENT, v TEXT);
    CREATE TABLE IF NOT EXISTS u (id INTEGER PRIMARY KEY AUTOINCREMENT, v TEXT);
    CREATE INDEX IF NOT EXISTS ix_t_v ON t(v);
    """


def _open_together(db: Path, n_threads: int) -> list[Exception]:
    errors: list[Exception] = []
    barrier = threading.Barrier(n_threads)

    def worker() -> None:
        try:
            b = _Backend(db)
            barrier.wait()  # every thread opens (WAL switch + schema) in the same instant
            conn = b._get_conn()
            conn.execute("INSERT INTO t (v) VALUES ('x')")
            conn.commit()
            b.close()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return errors


def test_concurrent_opens_of_a_fresh_database_all_succeed(tmp_path):
    for round_ in range(10):  # a fresh file each round: the WAL switch only races on a file not yet in WAL
        errors = _open_together(tmp_path / f"fresh_{round_}.db", n_threads=12)
        assert errors == [], f"round {round_}: {errors[:3]}"
