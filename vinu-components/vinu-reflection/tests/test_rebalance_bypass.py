"""Tests for analysis U (Execution & Money-Flow) -- critical
rebalance-bypass justification. See missing-pieces-of-system/
maturity-agentic-system/thinking-1/02-decided-pattern/25-A-Y-details/
03-execution-money-flow.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vinu_infra.reflection import ReflectionStore, write_findings
from vinu_infra.trade_audit_log import record_entry, record_exit

from vinu_reflection.reflection import rebalance_bypass
from vinu_live.trade_plan.rebalance_intake import RebalanceRequestQueue


@pytest.fixture
def data_root(tmp_path) -> Path:
    return tmp_path


def _seed_request(queue: RebalanceRequestQueue, *, symbol: str, critical: bool) -> None:
    queue.submit(symbol, "reason", critical=critical)
    queue.consume(symbol)


def _seed_exit(log_path: Path, *, symbol: str, trade_id: str, realized_pnl: float) -> None:
    record_exit(trade_id, symbol, {"realized_pnl": realized_pnl}, log_path=log_path)


class TestRebalanceBypassRun:
    def test_no_data_returns_no_findings(self, data_root):
        RebalanceRequestQueue(data_root / "rebalance_requests.db")
        findings = rebalance_bypass.run({"vinu_live": data_root})
        assert findings == []

    def test_below_evidence_minimum_is_skipped(self, data_root):
        queue = RebalanceRequestQueue(data_root / "rebalance_requests.db")
        log_path = data_root / "trade_audit_log.jsonl"
        for i in range(2):
            _seed_request(queue, symbol="AAPL", critical=True)
            _seed_exit(log_path, symbol="AAPL", trade_id=f"crit-{i}", realized_pnl=10.0)
            _seed_request(queue, symbol="AAPL", critical=False)
            _seed_exit(log_path, symbol="AAPL", trade_id=f"noncrit-{i}", realized_pnl=10.0)

        findings = rebalance_bypass.run({"vinu_live": data_root})
        assert findings == []

    def test_finds_critical_bypass_doing_worse_system_wide(self, data_root):
        queue = RebalanceRequestQueue(data_root / "rebalance_requests.db")
        log_path = data_root / "trade_audit_log.jsonl"

        # 5 critical bypasses, all losses.
        for i in range(5):
            _seed_request(queue, symbol="AAPL", critical=True)
            _seed_exit(log_path, symbol="AAPL", trade_id=f"crit-{i}", realized_pnl=-50.0)
        # 5 non-critical requests, all wins.
        for i in range(5):
            _seed_request(queue, symbol="MSFT", critical=False)
            _seed_exit(log_path, symbol="MSFT", trade_id=f"noncrit-{i}", realized_pnl=50.0)

        findings = rebalance_bypass.run({"vinu_live": data_root})
        by_scope = {f.scope_key: f for f in findings}
        assert "critical_bypass" in by_scope
        finding = by_scope["critical_bypass"]
        assert finding.analyst_name == "rebalance_bypass"
        assert finding.scope_type == "system"
        assert finding.evidence_count == 10
        assert finding.primary_metric == pytest.approx(-1.0)  # 0% vs 100% outcome rate
        assert finding.metric_name == "critical_outcome_delta"
        assert finding.signal_json["critical_outcome_rate"] == pytest.approx(0.0)
        assert finding.signal_json["noncritical_outcome_rate"] == pytest.approx(1.0)

    def test_request_with_no_later_exit_contributes_no_label(self, data_root):
        queue = RebalanceRequestQueue(data_root / "rebalance_requests.db")
        log_path = data_root / "trade_audit_log.jsonl"
        for i in range(5):
            _seed_request(queue, symbol="AAPL", critical=True)
            # no exit ever recorded for AAPL
            _seed_request(queue, symbol="MSFT", critical=False)
            _seed_exit(log_path, symbol="MSFT", trade_id=f"noncrit-{i}", realized_pnl=10.0)

        findings = rebalance_bypass.run({"vinu_live": data_root})
        assert findings == []  # critical group has zero evidence

    def test_per_symbol_finding_emitted_when_a_single_symbol_has_enough_evidence(self, data_root):
        queue = RebalanceRequestQueue(data_root / "rebalance_requests.db")
        log_path = data_root / "trade_audit_log.jsonl"
        for i in range(5):
            _seed_request(queue, symbol="AAPL", critical=True)
            _seed_exit(log_path, symbol="AAPL", trade_id=f"crit-{i}", realized_pnl=-10.0)
            _seed_request(queue, symbol="AAPL", critical=False)
            _seed_exit(log_path, symbol="AAPL", trade_id=f"noncrit-{i}", realized_pnl=10.0)

        findings = rebalance_bypass.run({"vinu_live": data_root})
        by_scope = {(f.scope_type, f.scope_key): f for f in findings}
        assert ("ticker", "AAPL") in by_scope


class TestRebalanceBypassEndToEnd:
    def test_run_write_findings_round_trip(self, data_root):
        queue = RebalanceRequestQueue(data_root / "rebalance_requests.db")
        log_path = data_root / "trade_audit_log.jsonl"
        reflection_store = ReflectionStore(data_root / "reflection.db")
        rebalance_bypass.seed_reference_config(reflection_store)

        for i in range(5):
            _seed_request(queue, symbol="AAPL", critical=True)
            _seed_exit(log_path, symbol="AAPL", trade_id=f"crit-{i}", realized_pnl=-50.0)
            _seed_request(queue, symbol="MSFT", critical=False)
            _seed_exit(log_path, symbol="MSFT", trade_id=f"noncrit-{i}", realized_pnl=50.0)

        findings = rebalance_bypass.run({"vinu_live": data_root})
        written = write_findings(reflection_store, findings)
        assert len(written) >= 1

        belief = reflection_store.get_belief("rebalance_bypass", "system", "critical_bypass")
        assert belief is not None
        assert belief["severity"] == "significant"
