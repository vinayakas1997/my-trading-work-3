from __future__ import annotations

from vinu_infra.calibration_log import read_all, record


class TestRecordAndReadAll:
    def test_round_trip(self, tmp_path) -> None:
        log_path = tmp_path / "calibration_log.jsonl"
        record("rebalance_protect", {"symbol": "AAPL", "threshold_pct": 0.08}, log_path=log_path)

        entries = read_all(log_path=log_path)
        assert len(entries) == 1
        assert entries[0]["checkpoint"] == "rebalance_protect"
        assert entries[0]["symbol"] == "AAPL"
        assert entries[0]["threshold_pct"] == 0.08
        assert "timestamp" in entries[0]

    def test_filters_by_checkpoint(self, tmp_path) -> None:
        log_path = tmp_path / "calibration_log.jsonl"
        record("rebalance_protect", {"symbol": "AAPL"}, log_path=log_path)
        record("bracket_partial", {"symbol": "MSFT"}, log_path=log_path)

        rebalance_only = read_all("rebalance_protect", log_path=log_path)
        assert len(rebalance_only) == 1
        assert rebalance_only[0]["symbol"] == "AAPL"

    def test_missing_file_returns_empty_list(self, tmp_path) -> None:
        assert read_all(log_path=tmp_path / "never_written.jsonl") == []

    def test_multiple_records_all_readable(self, tmp_path) -> None:
        log_path = tmp_path / "calibration_log.jsonl"
        for i in range(5):
            record("bracket_partial", {"seq": i}, log_path=log_path)

        entries = read_all("bracket_partial", log_path=log_path)
        assert [e["seq"] for e in entries] == [0, 1, 2, 3, 4]

    def test_write_failure_is_swallowed_not_raised(self, tmp_path) -> None:
        # Point at a path whose parent can't be created (a file, not a dir).
        blocker = tmp_path / "not_a_dir"
        blocker.write_text("x")
        bad_path = blocker / "calibration_log.jsonl"

        record("rebalance_protect", {"symbol": "AAPL"}, log_path=bad_path)  # must not raise
