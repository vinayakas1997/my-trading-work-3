"""Tests for analysis F (Governance & Freshness) -- human-in-the-loop as
a measured variable. See missing-pieces-of-system/maturity-agentic-
system/thinking-1/02-decided-pattern/25-A-Y-details/
05-governance-freshness.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vinu_agent.agent.significance_triage import SignificanceFlagStore
from vinu_infra.reflection import ReflectionStore, write_findings
from vinu_infra.trade_audit_log import record_exit

from vinu_reflection.reflection import significance_response_outcome


@pytest.fixture
def data_root(tmp_path) -> Path:
    return tmp_path


def _seed_flag(store: SignificanceFlagStore, *, ticker: str, reason: str, resolved: bool):
    flag = store.create_flag(ticker, reason, "detail")
    if resolved:
        store.mark_responded(flag.flag_id, "handled")
    return flag


def _seed_exit(log_path: Path, *, symbol: str, trade_id: str, realized_pnl: float) -> None:
    record_exit(trade_id, symbol, {"realized_pnl": realized_pnl}, log_path=log_path)


class TestSignificanceResponseOutcomeRun:
    def test_no_data_returns_no_findings(self, data_root):
        SignificanceFlagStore(data_root / "significance_flags.db")
        findings = significance_response_outcome.run({"vinu_agent": data_root, "vinu_live": data_root})
        assert findings == []

    def test_below_evidence_minimum_is_skipped(self, data_root):
        flag_store = SignificanceFlagStore(data_root / "significance_flags.db")
        log_path = data_root / "trade_audit_log.jsonl"
        for i in range(2):
            _seed_flag(flag_store, ticker="AAPL", reason="repeated_risk_gatekeeper_rejection", resolved=True)
            _seed_exit(log_path, symbol="AAPL", trade_id=f"resp-{i}", realized_pnl=10.0)
            _seed_flag(flag_store, ticker="AAPL", reason="repeated_risk_gatekeeper_rejection", resolved=False)
            _seed_exit(log_path, symbol="AAPL", trade_id=f"unresp-{i}", realized_pnl=10.0)

        findings = significance_response_outcome.run({"vinu_agent": data_root, "vinu_live": data_root})
        assert findings == []

    def test_finds_unresponded_flags_doing_worse(self, data_root):
        flag_store = SignificanceFlagStore(data_root / "significance_flags.db")
        log_path = data_root / "trade_audit_log.jsonl"

        # 5 responded flags, all followed by profitable exits.
        for i in range(5):
            _seed_flag(flag_store, ticker="AAPL", reason="large_funding_decision", resolved=True)
            _seed_exit(log_path, symbol="AAPL", trade_id=f"resp-{i}", realized_pnl=50.0)
        # 5 unresponded flags, all followed by losing exits.
        for i in range(5):
            _seed_flag(flag_store, ticker="MSFT", reason="large_funding_decision", resolved=False)
            _seed_exit(log_path, symbol="MSFT", trade_id=f"unresp-{i}", realized_pnl=-50.0)

        findings = significance_response_outcome.run({"vinu_agent": data_root, "vinu_live": data_root})
        by_scope = {f.scope_key: f for f in findings}
        assert "large_funding_decision" in by_scope
        finding = by_scope["large_funding_decision"]
        assert finding.analyst_name == "significance_response_outcome"
        assert finding.scope_type == "system"
        assert finding.evidence_count == 10
        assert finding.metric_name == "response_outcome_delta"
        assert finding.primary_metric == pytest.approx(1.0)  # 100% vs 0% outcome rate
        assert finding.signal_json["responded_outcome_rate"] == pytest.approx(1.0)
        assert finding.signal_json["unresponded_outcome_rate"] == pytest.approx(0.0)

    def test_flag_with_no_later_exit_contributes_no_label(self, data_root):
        flag_store = SignificanceFlagStore(data_root / "significance_flags.db")
        log_path = data_root / "trade_audit_log.jsonl"
        for i in range(5):
            _seed_flag(flag_store, ticker="AAPL", reason="thesis_contradicting_close", resolved=True)
            # no exit ever recorded for AAPL
            _seed_flag(flag_store, ticker="MSFT", reason="thesis_contradicting_close", resolved=False)
            _seed_exit(log_path, symbol="MSFT", trade_id=f"unresp-{i}", realized_pnl=10.0)

        findings = significance_response_outcome.run({"vinu_agent": data_root, "vinu_live": data_root})
        assert findings == []  # responded group has zero evidence

    def test_sentinel_ticker_flags_never_accumulate_evidence(self, data_root):
        # llm_failure_rate flags use ticker="SYSTEM" (LLM_FAILURE_SENTINEL_
        # TICKER) -- never a real tradable symbol in trade_audit_log.jsonl,
        # so no exit ever exists to join against. No special-casing needed
        # in the analyst itself: the weak join just naturally finds nothing.
        flag_store = SignificanceFlagStore(data_root / "significance_flags.db")
        for i in range(10):
            _seed_flag(flag_store, ticker="SYSTEM", reason="llm_failure_rate", resolved=(i % 2 == 0))

        findings = significance_response_outcome.run({"vinu_agent": data_root, "vinu_live": data_root})
        assert not any(f.scope_key == "llm_failure_rate" for f in findings)


class TestSignificanceResponseOutcomeEndToEnd:
    def test_run_write_findings_round_trip(self, data_root):
        flag_store = SignificanceFlagStore(data_root / "significance_flags.db")
        log_path = data_root / "trade_audit_log.jsonl"
        reflection_store = ReflectionStore(data_root / "reflection.db")
        significance_response_outcome.seed_reference_config(reflection_store)

        for i in range(5):
            _seed_flag(flag_store, ticker="AAPL", reason="large_funding_decision", resolved=True)
            _seed_exit(log_path, symbol="AAPL", trade_id=f"resp-{i}", realized_pnl=50.0)
            _seed_flag(flag_store, ticker="MSFT", reason="large_funding_decision", resolved=False)
            _seed_exit(log_path, symbol="MSFT", trade_id=f"unresp-{i}", realized_pnl=-50.0)

        findings = significance_response_outcome.run({"vinu_agent": data_root, "vinu_live": data_root})
        written = write_findings(reflection_store, findings)
        assert len(written) >= 1

        belief = reflection_store.get_belief(
            "significance_response_outcome", "system", "large_funding_decision",
        )
        assert belief is not None
