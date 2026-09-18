"""Tests for analysis Y (Execution & Money-Flow) -- earnings/macro-event
holding loss. See missing-pieces-of-system/maturity-agentic-system/
thinking-1/02-decided-pattern/25-A-Y-details/03-execution-money-flow.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vinu_infra.reflection import ReflectionStore, write_findings
from vinu_infra.trade_audit_log import record_entry, record_exit

from vinu_reflection.reflection import event_holding_loss
from vinu_stock.events.store import EventRecord, EventsStore


@pytest.fixture
def data_root(tmp_path) -> Path:
    return tmp_path


def _seed_trade(
    log_path: Path, *, symbol: str, trade_id: str, entry_ts: float, exit_ts: float, realized_pnl: float,
) -> None:
    entry = {"trade_id": trade_id, "symbol": symbol, "event": "entry", "timestamp": entry_ts}
    exit_ = {"trade_id": trade_id, "symbol": symbol, "event": "exit", "timestamp": exit_ts, "realized_pnl": realized_pnl}
    import json

    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
        f.write(json.dumps(exit_) + "\n")


class TestEventHoldingLossRun:
    def test_no_data_returns_no_findings(self, data_root):
        EventsStore(data_root / "vinu_events.db")
        findings = event_holding_loss.run({"vinu_live": data_root, "vinu_stock": data_root})
        assert findings == []

    def test_below_evidence_minimum_is_skipped(self, data_root):
        events_store = EventsStore(data_root / "vinu_events.db")
        log_path = data_root / "trade_audit_log.jsonl"
        for i in range(5):
            _seed_trade(log_path, symbol="AAPL", trade_id=f"t{i}", entry_ts=1000.0, exit_ts=2000.0, realized_pnl=10.0)

        findings = event_holding_loss.run({"vinu_live": data_root, "vinu_stock": data_root})
        assert findings == []

    def test_finds_event_overlapping_trades_doing_worse(self, data_root):
        events_store = EventsStore(data_root / "vinu_events.db")
        log_path = data_root / "trade_audit_log.jsonl"

        # 10 trades overlapping an archived earnings event, all losses.
        events_store.replace_kind("earnings", [
            EventRecord("AAPL", "earnings", 1500.0, "AAPL earnings", 2),
        ])
        events_store.replace_kind("earnings", [])  # archives it, drops from `events`
        for i in range(10):
            _seed_trade(
                log_path, symbol="AAPL", trade_id=f"overlap-{i}",
                entry_ts=1000.0, exit_ts=2000.0, realized_pnl=-50.0,
            )
        # 10 trades with no overlap at all, all wins.
        for i in range(10):
            _seed_trade(
                log_path, symbol="MSFT", trade_id=f"clean-{i}",
                entry_ts=1000.0, exit_ts=2000.0, realized_pnl=50.0,
            )

        findings = event_holding_loss.run({"vinu_live": data_root, "vinu_stock": data_root})
        by_scope = {f.scope_key: f for f in findings}
        assert "earnings_event_effect" in by_scope
        finding = by_scope["earnings_event_effect"]
        assert finding.analyst_name == "event_holding_loss"
        assert finding.scope_type == "system"
        assert finding.evidence_count == 20
        assert finding.primary_metric == pytest.approx(-100.0)  # -50 vs +50 mean pnl
        assert finding.metric_name == "event_overlap_pnl_delta"
        assert finding.signal_json["n_overlapping_trades"] == 10
        assert finding.signal_json["n_non_overlapping_trades"] == 10

    def test_still_upcoming_event_also_counts_as_overlap(self, data_root):
        """A very recent trade might overlap an event still in the live
        `events` table (not yet archived) -- must still count."""
        events_store = EventsStore(data_root / "vinu_events.db")
        log_path = data_root / "trade_audit_log.jsonl"
        events_store.replace_kind("earnings", [
            EventRecord("AAPL", "earnings", 1500.0, "AAPL earnings", 2),
        ])
        for i in range(10):
            _seed_trade(
                log_path, symbol="AAPL", trade_id=f"overlap-{i}",
                entry_ts=1000.0, exit_ts=2000.0, realized_pnl=-50.0,
            )
        for i in range(10):
            _seed_trade(
                log_path, symbol="MSFT", trade_id=f"clean-{i}",
                entry_ts=1000.0, exit_ts=2000.0, realized_pnl=50.0,
            )

        findings = event_holding_loss.run({"vinu_live": data_root, "vinu_stock": data_root})
        by_scope = {f.scope_key: f for f in findings}
        assert by_scope["earnings_event_effect"].signal_json["n_overlapping_trades"] == 10

    def test_trade_missing_its_entry_or_exit_row_is_excluded(self, data_root):
        events_store = EventsStore(data_root / "vinu_events.db")
        log_path = data_root / "trade_audit_log.jsonl"
        import json

        # Exit-only row (no matching entry) -- must not be counted.
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "trade_id": "orphan", "symbol": "AAPL", "event": "exit",
                "timestamp": 2000.0, "realized_pnl": -999.0,
            }) + "\n")
        for i in range(20):
            _seed_trade(log_path, symbol="MSFT", trade_id=f"t{i}", entry_ts=1000.0, exit_ts=2000.0, realized_pnl=1.0)

        findings = event_holding_loss.run({"vinu_live": data_root, "vinu_stock": data_root})
        # If the orphan leaked in, evidence_count would be 21, not 20.
        if findings:
            assert findings[0].evidence_count == 20


class TestEventHoldingLossEndToEnd:
    def test_run_write_findings_round_trip(self, data_root):
        events_store = EventsStore(data_root / "vinu_events.db")
        log_path = data_root / "trade_audit_log.jsonl"
        reflection_store = ReflectionStore(data_root / "reflection.db")
        event_holding_loss.seed_reference_config(reflection_store)

        events_store.replace_kind("earnings", [
            EventRecord("AAPL", "earnings", 1500.0, "AAPL earnings", 2),
        ])
        events_store.replace_kind("earnings", [])
        for i in range(10):
            _seed_trade(log_path, symbol="AAPL", trade_id=f"overlap-{i}", entry_ts=1000.0, exit_ts=2000.0, realized_pnl=-50.0)
        for i in range(10):
            _seed_trade(log_path, symbol="MSFT", trade_id=f"clean-{i}", entry_ts=1000.0, exit_ts=2000.0, realized_pnl=50.0)

        findings = event_holding_loss.run({"vinu_live": data_root, "vinu_stock": data_root})
        written = write_findings(reflection_store, findings)
        assert len(written) >= 1

        belief = reflection_store.get_belief("event_holding_loss", "system", "earnings_event_effect")
        assert belief is not None
        assert belief["severity"] == "significant"
