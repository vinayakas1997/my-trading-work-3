from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from vinu_research.storage.sqlite_backend import ResearchStorage


def test_update_catalog_creates_entry():
    with TemporaryDirectory() as tmp:
        with ResearchStorage(Path(tmp) / "test.db") as db:
            db.update_catalog_after_run("AAPL", run_id=1, trial_count=5, sharpe=1.2, validated=True)
            entry = db.get_catalog_entry("AAPL")
            assert entry is not None
            assert entry["symbol"] == "AAPL"
            assert entry["lifetime_trial_count"] == 5
            assert entry["last_run_id"] == 1
            assert entry["best_sharpe_ever"] == 1.2
            assert entry["last_validated_ts"] is not None
            assert entry["status"] == "active"


def test_update_catalog_updates_existing():
    with TemporaryDirectory() as tmp:
        with ResearchStorage(Path(tmp) / "test.db") as db:
            db.update_catalog_after_run("AAPL", run_id=1, trial_count=5, sharpe=1.2)
            db.update_catalog_after_run("AAPL", run_id=2, trial_count=10, sharpe=1.5, validated=True)
            entry = db.get_catalog_entry("AAPL")
            assert entry is not None
            assert entry["lifetime_trial_count"] == 10
            assert entry["last_run_id"] == 2
            assert entry["best_sharpe_ever"] == 1.5
            assert entry["last_validated_ts"] is not None


def test_update_catalog_best_sharpe_ever_does_not_regress():
    # trial_count is always the caller-computed lifetime total (see
    # cumulative_trial_count), so it's a plain overwrite — but best_sharpe_ever
    # must never regress just because the *latest* run happened to score lower.
    with TemporaryDirectory() as tmp:
        with ResearchStorage(Path(tmp) / "test.db") as db:
            db.update_catalog_after_run("AAPL", run_id=1, trial_count=5, sharpe=2.0)
            db.update_catalog_after_run("AAPL", run_id=2, trial_count=8, sharpe=0.5)
            entry = db.get_catalog_entry("AAPL")
            assert entry is not None
            assert entry["best_sharpe_ever"] == 2.0
            assert entry["lifetime_trial_count"] == 8
            assert entry["last_run_id"] == 2


def test_get_catalog_entry_missing():
    with TemporaryDirectory() as tmp:
        with ResearchStorage(Path(tmp) / "test.db") as db:
            entry = db.get_catalog_entry("NONEXISTENT")
            assert entry is None


def test_list_catalog():
    with TemporaryDirectory() as tmp:
        with ResearchStorage(Path(tmp) / "test.db") as db:
            db.update_catalog_after_run("AAPL", run_id=1, trial_count=5, sharpe=1.2)
            db.update_catalog_after_run("MSFT", run_id=2, trial_count=3, sharpe=0.9)
            entries = db.list_catalog()
            assert len(entries) == 2
            symbols = [e["symbol"] for e in entries]
            assert "AAPL" in symbols
            assert "MSFT" in symbols


def test_list_stale_catalog():
    from datetime import datetime, timedelta, timezone
    with TemporaryDirectory() as tmp:
        with ResearchStorage(Path(tmp) / "test.db") as db:
            db.update_catalog_after_run("FRESH", run_id=1, trial_count=5, sharpe=1.2, validated=True)
            db.update_catalog_after_run("STALE", run_id=2, trial_count=3, sharpe=0.9, validated=False)
            db.update_catalog_after_run("OLD", run_id=3, trial_count=1, sharpe=0.5, validated=True)
            db._get_conn().execute(
                "UPDATE research_catalog SET last_validated_ts = ? WHERE symbol = ?",
                ((datetime.now(timezone.utc) - timedelta(days=60)).isoformat(), "OLD"),
            )
            db._get_conn().commit()
            stale = db.list_stale_catalog(days=30)
            stale_symbols = {e["symbol"] for e in stale}
            assert "STALE" in stale_symbols
            assert "OLD" in stale_symbols
            assert "FRESH" not in stale_symbols


def test_save_and_get_last_checkpoint():
    with TemporaryDirectory() as tmp:
        with ResearchStorage(Path(tmp) / "test.db") as db:
            db.save_checkpoint(run_id=1, iteration=1, code="code_v1", metrics={"sharpe": 0.5}, critic_verdict="REFINE")
            db.save_checkpoint(run_id=1, iteration=2, code="code_v2", metrics={"sharpe": 1.2}, critic_verdict="PASS")
            last = db.get_last_checkpoint(1)
            assert last is not None
            assert last["iteration"] == 2
            assert last["code"] == "code_v2"
            assert last["critic_verdict"] == "PASS"
            assert last["metrics"]["sharpe"] == 1.2


def test_save_checkpoint_insert_or_ignore():
    with TemporaryDirectory() as tmp:
        with ResearchStorage(Path(tmp) / "test.db") as db:
            db.save_checkpoint(run_id=1, iteration=1, code="original", metrics={}, critic_verdict="REFINE")
            db.save_checkpoint(run_id=1, iteration=1, code="overwritten", metrics={}, critic_verdict="PASS")
            last = db.get_last_checkpoint(1)
            assert last is not None
            assert last["code"] == "original"


def test_list_checkpoints():
    with TemporaryDirectory() as tmp:
        with ResearchStorage(Path(tmp) / "test.db") as db:
            db.save_checkpoint(run_id=1, iteration=1, code="v1", metrics={}, critic_verdict="REFINE")
            db.save_checkpoint(run_id=1, iteration=2, code="v2", metrics={}, critic_verdict="PASS")
            db.save_checkpoint(run_id=2, iteration=1, code="other", metrics={}, critic_verdict="REFINE")
            checkpoints = db.list_checkpoints(1)
            assert len(checkpoints) == 2
            assert checkpoints[0]["iteration"] == 1
            assert checkpoints[1]["iteration"] == 2


def test_delete_checkpoints():
    with TemporaryDirectory() as tmp:
        with ResearchStorage(Path(tmp) / "test.db") as db:
            db.save_checkpoint(run_id=1, iteration=1, code="v1", metrics={}, critic_verdict="REFINE")
            db.save_checkpoint(run_id=1, iteration=2, code="v2", metrics={}, critic_verdict="PASS")
            db.delete_checkpoints(1)
            remaining = db.list_checkpoints(1)
            assert len(remaining) == 0


def test_checkpoints_different_runs_independent():
    with TemporaryDirectory() as tmp:
        with ResearchStorage(Path(tmp) / "test.db") as db:
            db.save_checkpoint(run_id=1, iteration=1, code="run1_v1", metrics={}, critic_verdict="REFINE")
            db.save_checkpoint(run_id=2, iteration=1, code="run2_v1", metrics={}, critic_verdict="PASS")
            c1 = db.get_last_checkpoint(1)
            c2 = db.get_last_checkpoint(2)
            assert c1 is not None and c2 is not None
            assert c1["code"] == "run1_v1"
            assert c2["code"] == "run2_v1"
