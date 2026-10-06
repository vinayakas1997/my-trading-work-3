"""Each candle load opened its own unbounded DuckDB connection, all at once; a burst exhausted the 2 GB container
("Out of buffer", HTTP 500s, restarts). Loads are now limited in number and memory."""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pandas as pd

from vinu_stock.query import engine


def test_connections_are_opened_with_a_memory_and_thread_limit(tmp_path, monkeypatch):
    seen = {}
    real = engine.duckdb.connect

    def spy(*a, **k):
        seen.update(k.get("config") or {})
        return real(*a, **k)

    monkeypatch.setattr(engine.duckdb, "connect", spy)
    d = tmp_path / "prices" / "1m" / "X" / "live"
    d.mkdir(parents=True)
    pd.DataFrame([dict(symbol="X", provider="p", bar_ts=60, open=1.0, high=1.0, low=1.0, close=1.0, volume=1.0, adj_factor=1.0)]) \
        .to_parquet(d / "X.parquet")
    engine.invalidate_symbol_cache()
    engine.fetch_candles(tmp_path, "X", interval="1m")
    assert seen.get("memory_limit") and int(seen["threads"]) >= 1


def test_only_a_few_loads_run_at_the_same_time(tmp_path, monkeypatch):
    current, peak, lock = 0, 0, threading.Lock()
    real = engine.duckdb.connect

    def slow_connect(*a, **k):
        nonlocal current, peak
        with lock:
            current += 1
            peak = max(peak, current)
        time.sleep(0.15)
        conn = real(*a, **k)

        class _Wrap:
            def execute(self, *x, **y):
                return conn.execute(*x, **y)

            def close(self):
                nonlocal current
                conn.close()
                with lock:
                    current -= 1

        return _Wrap()

    monkeypatch.setattr(engine.duckdb, "connect", slow_connect)
    for sym in ("A", "B", "C", "D", "E", "F"):
        d = tmp_path / "prices" / "1m" / sym / "live"
        d.mkdir(parents=True)
        pd.DataFrame([dict(symbol=sym, provider="p", bar_ts=60, open=1.0, high=1.0, low=1.0, close=1.0, volume=1.0, adj_factor=1.0)]) \
            .to_parquet(d / f"{sym}.parquet")
    engine.invalidate_symbol_cache()
    threads = [threading.Thread(target=engine.fetch_candles, args=(tmp_path, s), kwargs={"interval": "1m"}) for s in "ABCDEF"]
    [t.start() for t in threads]
    [t.join(30) for t in threads]
    assert 1 <= peak <= int(engine._LOAD_SLOTS._initial_value)
