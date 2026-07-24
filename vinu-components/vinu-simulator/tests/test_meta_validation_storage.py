from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from vinu_simulator.storage.meta import MetaStorage


def _make_store(tmp: str) -> MetaStorage:
    return MetaStorage(Path(tmp) / "meta.db")


def test_insert_run_persists_validation_and_symbols():
    with TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        validation = {
            "monte_carlo": {"p_value": 0.02, "minimum_met": True},
            "verdict": {"passed": True, "reasons": ["ok"]},
        }
        store.insert_run(
            run_id="run-1",
            strategy_name="ma_crossover",
            timestamp=datetime.now(timezone.utc),
            config={"strategy_name": "ma_crossover"},
            metrics={"sharpe_ratio": 1.5},
            validation=validation,
            symbols=["AAPL", "MSFT"],
        )
        row = store.get_run("run-1")
        assert row is not None
        assert row["validation"] == validation
        assert row["symbols"] == ["AAPL", "MSFT"]


def test_insert_run_without_validation_stores_none():
    with TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        store.insert_run(
            run_id="run-2",
            strategy_name="ma_crossover",
            timestamp=datetime.now(timezone.utc),
            config={},
            metrics={},
        )
        row = store.get_run("run-2")
        assert row is not None
        assert row["validation"] is None
        assert row["symbols"] == []


def test_list_runs_filters_by_symbol():
    with TemporaryDirectory() as tmp:
        store = _make_store(tmp)
        store.insert_run(
            run_id="run-aapl",
            strategy_name="s1",
            timestamp=datetime.now(timezone.utc),
            config={},
            metrics={},
            symbols=["AAPL"],
        )
        store.insert_run(
            run_id="run-msft",
            strategy_name="s1",
            timestamp=datetime.now(timezone.utc),
            config={},
            metrics={},
            symbols=["MSFT"],
        )
        aapl_runs = store.list_runs(symbol="AAPL")
        assert {r["run_id"] for r in aapl_runs} == {"run-aapl"}

        # case-insensitive
        aapl_runs_lower = store.list_runs(symbol="aapl")
        assert {r["run_id"] for r in aapl_runs_lower} == {"run-aapl"}


def test_migration_adds_validation_columns_to_existing_db():
    # Simulate a pre-Phase-1 database: schema without validation/symbols columns.
    with TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "meta.db"
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.executescript(
            """
            CREATE TABLE simulation_runs (
                run_id TEXT PRIMARY KEY,
                strategy_name TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                config TEXT NOT NULL,
                metrics TEXT NOT NULL,
                benchmark_metrics TEXT,
                equity_points INTEGER DEFAULT 0,
                trade_count INTEGER DEFAULT 0
            );
            """
        )
        conn.execute(
            "INSERT INTO simulation_runs "
            "(run_id, strategy_name, timestamp, config, metrics, benchmark_metrics) "
            "VALUES ('old-run', 's1', '2026-01-01T00:00:00', '{}', '{}', '{}')"
        )
        conn.commit()
        conn.close()

        store = MetaStorage(db_path)
        row = store.get_run("old-run")
        assert row is not None
        assert row["validation"] is None
        assert row["symbols"] == []
