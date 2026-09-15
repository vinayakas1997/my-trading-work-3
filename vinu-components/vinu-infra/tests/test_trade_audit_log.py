from __future__ import annotations

from vinu_infra.trade_audit_log import (
    read_all,
    read_by_trade_id,
    record_entry,
    record_exit,
    slippage_stats,
)


class TestRecordEntryAndExit:
    def test_entry_round_trip(self, tmp_path) -> None:
        log_path = tmp_path / "trade_audit_log.jsonl"
        record_entry(
            "trade_1", "AAPL",
            {"entry_decision": "BUY", "trade_score_tier": "strong", "fill_price": 150.0, "fill_qty": 10.0},
            log_path=log_path,
        )

        entries = read_all(log_path=log_path)
        assert len(entries) == 1
        assert entries[0]["trade_id"] == "trade_1"
        assert entries[0]["symbol"] == "AAPL"
        assert entries[0]["event"] == "entry"
        assert entries[0]["entry_decision"] == "BUY"
        assert entries[0]["trade_score_tier"] == "strong"
        assert "timestamp" in entries[0]

    def test_exit_round_trip(self, tmp_path) -> None:
        log_path = tmp_path / "trade_audit_log.jsonl"
        record_exit(
            "trade_1", "AAPL", {"exit_reason": "invalidation_exit", "realized_pnl": -42.5},
            log_path=log_path,
        )

        entries = read_all(log_path=log_path)
        assert len(entries) == 1
        assert entries[0]["event"] == "exit"
        assert entries[0]["exit_reason"] == "invalidation_exit"

    def test_missing_file_returns_empty_list(self, tmp_path) -> None:
        assert read_all(log_path=tmp_path / "never_written.jsonl") == []

    def test_write_failure_is_swallowed_not_raised(self, tmp_path) -> None:
        blocker = tmp_path / "not_a_dir"
        blocker.write_text("x")
        bad_path = blocker / "trade_audit_log.jsonl"

        record_entry("trade_1", "AAPL", {}, log_path=bad_path)  # must not raise


class TestReadByTradeId:
    def test_joins_entry_and_exit_rows_for_same_trade(self, tmp_path) -> None:
        log_path = tmp_path / "trade_audit_log.jsonl"
        record_entry("trade_1", "AAPL", {"fill_price": 150.0}, log_path=log_path)
        record_entry("trade_2", "MSFT", {"fill_price": 300.0}, log_path=log_path)
        record_exit("trade_1", "AAPL", {"realized_pnl": 12.0}, log_path=log_path)

        rows = read_by_trade_id("trade_1", log_path=log_path)
        assert [r["event"] for r in rows] == ["entry", "exit"]
        assert all(r["trade_id"] == "trade_1" for r in rows)

    def test_no_matching_rows_returns_empty_list(self, tmp_path) -> None:
        log_path = tmp_path / "trade_audit_log.jsonl"
        record_entry("trade_1", "AAPL", {}, log_path=log_path)

        assert read_by_trade_id("trade_nonexistent", log_path=log_path) == []

    def test_missing_file_returns_empty_list(self, tmp_path) -> None:
        assert read_by_trade_id("trade_1", log_path=tmp_path / "never_written.jsonl") == []


class TestSlippageStats:
    """slippage_bps was already recorded per-entry-row but nothing
    aggregated it past the boolean slippage_exceeded threshold -- see the
    foundation-fixes audit in missing-pieces-of-system/narating-agents/."""

    def test_empty_log_returns_zero_count_and_none_stats(self, tmp_path) -> None:
        stats = slippage_stats(log_path=tmp_path / "never_written.jsonl")
        assert stats == {
            "count": 0, "mean_bps": None, "median_bps": None,
            "max_abs_bps": None, "exceeded_count": 0,
        }

    def test_aggregates_across_entry_rows_only(self, tmp_path) -> None:
        log_path = tmp_path / "trade_audit_log.jsonl"
        record_entry("t1", "AAPL", {"slippage_bps": 10.0, "slippage_exceeded": False}, log_path=log_path)
        record_entry("t2", "AAPL", {"slippage_bps": -30.0, "slippage_exceeded": True}, log_path=log_path)
        record_exit("t1", "AAPL", {"realized_pnl": 5.0}, log_path=log_path)  # no slippage_bps, must be ignored

        stats = slippage_stats(log_path=log_path)
        assert stats["count"] == 2
        assert stats["mean_bps"] == -10.0
        assert stats["median_bps"] == -10.0
        assert stats["max_abs_bps"] == 30.0
        assert stats["exceeded_count"] == 1

    def test_filters_by_symbol(self, tmp_path) -> None:
        log_path = tmp_path / "trade_audit_log.jsonl"
        record_entry("t1", "AAPL", {"slippage_bps": 10.0}, log_path=log_path)
        record_entry("t2", "MSFT", {"slippage_bps": 50.0}, log_path=log_path)

        stats = slippage_stats("AAPL", log_path=log_path)
        assert stats["count"] == 1
        assert stats["mean_bps"] == 10.0

    def test_rows_missing_slippage_bps_are_skipped_not_counted(self, tmp_path) -> None:
        log_path = tmp_path / "trade_audit_log.jsonl"
        record_entry("t1", "AAPL", {"fill_price": 150.0}, log_path=log_path)  # no slippage_bps

        assert slippage_stats(log_path=log_path)["count"] == 0
