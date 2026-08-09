import sqlite3
import threading
from pathlib import Path
from tempfile import TemporaryDirectory

from vinu_infra.llm.cache import LlmCache


def test_set_and_get_roundtrip():
    with TemporaryDirectory() as tmp:
        cache = LlmCache(Path(tmp) / "cache.db")
        cache.set("k1", {"answer": 42})
        assert cache.get("k1") == {"answer": 42}
        cache.close()


def test_get_missing_key_returns_none():
    with TemporaryDirectory() as tmp:
        cache = LlmCache(Path(tmp) / "cache.db")
        assert cache.get("missing") is None
        cache.close()


def test_ttl_zero_disables_cache():
    with TemporaryDirectory() as tmp:
        cache = LlmCache(Path(tmp) / "cache.db", ttl_sec=0)
        cache.set("k1", {"a": 1})
        assert cache.get("k1") is None
        cache.close()


def test_close_closes_connections_opened_by_other_threads():
    # ignore_cleanup_errors=True: Windows can hold the WAL/-shm sidecar
    # files briefly after a real, successful sqlite3 close() -- a known OS-
    # level cleanup race, not a real failure of the code under test.
    with TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        cache = LlmCache(Path(tmp) / "cache.db")
        opened: list = []

        def open_from_worker_thread():
            opened.append(cache._get_conn())

        t = threading.Thread(target=open_from_worker_thread)
        t.start()
        t.join()

        cache.close()  # called from the main thread

        try:
            opened[0].execute("SELECT 1")
            assert False, "worker thread's connection should have been closed"
        except sqlite3.ProgrammingError:
            pass


def test_get_conn_reopens_after_another_threads_close():
    with TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        cache = LlmCache(Path(tmp) / "cache.db")
        results: dict = {}
        barrier = threading.Barrier(2)
        barrier2 = threading.Barrier(2)

        def worker():
            conn1 = cache._get_conn()
            results["conn1_id"] = id(conn1)
            barrier.wait()
            barrier2.wait()
            conn2 = cache._get_conn()
            conn2.execute("SELECT 1")  # must not raise
            results["conn2_id"] = id(conn2)

        t = threading.Thread(target=worker)
        t.start()
        barrier.wait()
        cache.close()
        barrier2.wait()
        t.join()

        assert results["conn1_id"] != results["conn2_id"]
        cache.close()
