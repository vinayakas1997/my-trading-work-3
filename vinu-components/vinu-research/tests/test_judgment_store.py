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
    log = tmp_path / "judgments.jsonl"
    store1 = JudgmentStore(log)
    store1.record(JudgmentRecord(
        ts="2025-01-01T00:00:00Z", symbol="AAPL", iteration=1,
        verdict="PASS", in_sample_sharpe=1.5, out_of_sample_sharpe=None,
        holdout_sharpe=1.2, verdict_correct=True, llm_calls_used=5, run_id=42,
        model="gpt-4", strategy_code_hash="abc123",
    ))
    store2 = JudgmentStore(log)
    store2.load()
    assert store2.total_records == 1
    s = store2.calibration_summary()
    assert s["total"] == 1
    assert s["with_outcome"] == 1


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
