from pathlib import Path
import pytest
from vinu_research.judgment_store import JudgmentRecord, JudgmentStore


def test_record_and_count():
    store = JudgmentStore()
    assert store.total_records == 0
    store.record(JudgmentRecord(
        ts="2025-01-01T00:00:00Z", symbol="AAPL", iteration=1,
        verdict="PASS", in_sample_sharpe=1.5, out_of_sample_sharpe=None,
        holdout_sharpe=1.2, verdict_correct=None, llm_calls_used=5,
    ))
    assert store.total_records == 1


def test_calibration_summary_empty():
    store = JudgmentStore()
    s = store.calibration_summary()
    assert s["total"] == 0
    assert s["with_outcome"] == 0


def test_calibration_summary_with_outcomes():
    store = JudgmentStore()
    for _ in range(4):
        store.record(JudgmentRecord(
            ts="", symbol="AAPL", iteration=1, verdict="PASS",
            in_sample_sharpe=1.5, out_of_sample_sharpe=None,
            holdout_sharpe=1.2, verdict_correct=True, llm_calls_used=5,
        ))
    for _ in range(2):
        store.record(JudgmentRecord(
            ts="", symbol="AAPL", iteration=2, verdict="PASS",
            in_sample_sharpe=0.8, out_of_sample_sharpe=None,
            holdout_sharpe=0.3, verdict_correct=False, llm_calls_used=3,
        ))
    s = store.calibration_summary()
    assert s["total"] == 6
    assert s["with_outcome"] == 6
    assert s["by_verdict"]["PASS"]["count"] == 6
    assert s["by_verdict"]["PASS"]["correct"] == 4
    assert s["by_verdict"]["PASS"]["accuracy"] == pytest.approx(4 / 6, abs=0.001)


def test_calibration_skips_none_outcomes():
    store = JudgmentStore()
    store.record(JudgmentRecord(
        ts="", symbol="AAPL", iteration=1, verdict="PASS",
        in_sample_sharpe=1.5, out_of_sample_sharpe=None,
        holdout_sharpe=None, verdict_correct=None, llm_calls_used=5,
    ))
    s = store.calibration_summary()
    assert s["total"] == 1
    assert s["with_outcome"] == 0


def test_persist_and_load(tmp_path: Path):
    """item #12 finding #1: now a real SQLite file (WAL mode), not a
    hand-rolled JSONL append with no lock around the actual write --
    load() is kept callable (a no-op now) purely for API compatibility
    with any existing caller of the old JSONL-era contract."""
    db_path = tmp_path / "judgments.db"
    store1 = JudgmentStore(db_path)
    store1.record(JudgmentRecord(
        ts="2025-01-01T00:00:00Z", symbol="AAPL", iteration=1,
        verdict="PASS", in_sample_sharpe=1.5, out_of_sample_sharpe=None,
        holdout_sharpe=1.2, verdict_correct=True, llm_calls_used=5, run_id=42,
        model="gpt-4", strategy_code_hash="abc123",
    ))
    store2 = JudgmentStore(db_path)
    store2.load()
    assert store2.total_records == 1
    s = store2.calibration_summary()
    assert s["total"] == 1
    assert s["with_outcome"] == 1


def test_a_second_store_sees_writes_immediately_without_calling_load(tmp_path: Path):
    """The real property this migration buys: a second instance pointed
    at the same file sees committed writes live, unlike the old JSONL
    mode which required an explicit load() to see anything written by a
    different instance/process."""
    db_path = tmp_path / "judgments.db"
    store1 = JudgmentStore(db_path)
    store1.record(JudgmentRecord(
        ts="", symbol="AAPL", iteration=1, verdict="PASS",
        in_sample_sharpe=1.0, out_of_sample_sharpe=None,
        holdout_sharpe=None, verdict_correct=None, llm_calls_used=1,
    ))
    store2 = JudgmentStore(db_path)
    assert store2.total_records == 1  # no store2.load() call at all


def test_sequential_writes_from_two_instances_both_land(tmp_path: Path):
    """item #12 finding #1's actual concern: concurrent writers to the
    same file. The old JSONL `_persist()` ran its file append outside the
    module's own lock -- real interleaved writers risked a corrupted or
    interleaved line. Two separate JudgmentStore instances (the same
    "multiple concurrent loops" shape the finding names) writing to the
    same path now both durably land through SQLiteBackend's real
    connection instead.

    Not exercised here with real concurrent threads: `SQLiteBackend`'s
    own connection-setup race under many simultaneous first-time
    connections to one fresh file (`PRAGMA journal_mode=WAL` racing
    itself) is a separate, pre-existing, already-flagged flakiness at
    the base-class level (`vinu-infra/tests/test_sqlite_backend.py`'s
    own `TestThreadSafety::test_concurrent_writes`), not something this
    migration needs to re-prove or fix in every subclass's own suite."""
    db_path = tmp_path / "judgments.db"
    store_a = JudgmentStore(db_path)
    store_b = JudgmentStore(db_path)

    store_a.record(JudgmentRecord(
        ts="", symbol="AAPL", iteration=1, verdict="PASS",
        in_sample_sharpe=1.0, out_of_sample_sharpe=None,
        holdout_sharpe=None, verdict_correct=None, llm_calls_used=1,
    ))
    store_b.record(JudgmentRecord(
        ts="", symbol="MSFT", iteration=1, verdict="PASS",
        in_sample_sharpe=1.0, out_of_sample_sharpe=None,
        holdout_sharpe=None, verdict_correct=None, llm_calls_used=1,
    ))

    assert store_a.total_records == 2
    assert store_b.total_records == 2


def test_reset():
    store = JudgmentStore()
    store.record(JudgmentRecord(
        ts="", symbol="AAPL", iteration=1, verdict="PASS",
        in_sample_sharpe=1.5, out_of_sample_sharpe=None,
        holdout_sharpe=1.2, verdict_correct=None, llm_calls_used=5,
    ))
    assert store.total_records == 1
    store.reset()
    assert store.total_records == 0
